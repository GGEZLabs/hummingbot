import time
from decimal import Decimal
from enum import Enum
from random import randint
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from scripts.utils.custom_volume_pumper_utils import CustomVolumePumperUtils
from scripts.utils.report_management import ReportManagement
from scripts.utils.risk_management import RiskManagement


class StrategyStatus(Enum):
    NOT_INITIALIZED = 0
    RUNNING = 1
    STOPPED = 2
    UNDERBALANCED = 3


class VolumePumperConfig(ControllerConfigBase):
    controller_type: str = "market_making"
    # candles_config: List[CandlesConfig] = []
    exchange: str = Field(
        "coinstore",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"),
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Trading pair in which the bot will place orders"
        ),
    )
    order_lower_amount: int = Field(
        500,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Lower value for order amount (in base asset , GGEZ1)"
        ),
    )
    order_upper_amount: int = Field(
        2000,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Upper value for order amount (in base asset , GGEZ1)"
        ),
    )
    delay_order_time: int = Field(
        120, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Delay time between orders (in seconds)")
    )
    max_random_delay: int = Field(
        120,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Maximum random delay to be add to delay_order_time (in seconds)"
        ),
    )
    balance_loss_threshold: Decimal = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Balance loss threshold (in quote asset , USDT)"
        ),
    )
    minimum_ask_bid_spread: Decimal = Field(
        10,
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Minimum ask bid spread (basis points)"),
    )
    periodic_report_interval: float = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "The interval for periodic report (in hours)"
        ),
    )

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.exchange not in markets:
            markets[self.exchange] = set()
        markets[self.exchange].add(self.trading_pair)
        return markets


class VolumePumperControllerBase(ControllerBase):
    def __init__(self, config: VolumePumperConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        # config data
        self.controller_id = config.id
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.order_lower_amount = config.order_lower_amount
        self.order_upper_amount = config.order_upper_amount
        self.delay_order_time = config.delay_order_time
        self.balance_loss_threshold = config.balance_loss_threshold
        self.minimum_ask_bid_spread_BS = config.minimum_ask_bid_spread
        self.max_random_delay = config.max_random_delay
        self.periodic_report_interval = config.periodic_report_interval
        self.active_order_total_lifespan = 40
        # strategy data
        self.strategy_status = StrategyStatus.NOT_INITIALIZED
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        # rate sources
        self.market_data_provider.initialize_rate_sources(
            [ConnectorPair(connector_name=config.exchange, trading_pair=config.trading_pair)]
        )

    @property
    def connector(self) -> ConnectorBase:
        return self.market_data_provider.connectors[self.exchange]

    @property
    def current_timestamp(self):
        return int(time.time())

    @property
    def is_ready_to_create_periodic_summary(self):
        return (
            self.periodic_report_interval > 0
            and self.current_timestamp - self.report_management.last_report_timestamp
            >= self.report_management.report_frequency
        )

    @property
    def is_ready_to_create_order(self):
        return self.current_timestamp - self.last_mid_price_timestamp >= self.delay_order_time + self.random_delay

    async def update_processed_data(self):
        pass

    def on_stop(self):
        """
        Get the executors to early stop based on the current state of market data. This method can be overridden to
        implement custom behavior.
        """
        pass

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        stop_actions = []
        stop_actions.extend(self.executors_to_cancel())
        return stop_actions

    def executors_to_cancel(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info, filter_func=lambda x: not x.is_trading and x.is_active
        )

        return [
            StopExecutorAction(controller_id=self.config.id, executor_id=executor.id)
            for executor in executors_to_refresh
        ]

    def get_balance_df(self) -> pd.DataFrame:
        """
        Returns a data frame for all asset balances for displaying purpose.
        """
        columns: List[str] = ["Exchange", "Asset", "Total Balance", "Available Balance"]
        data: List[Any] = []
        for asset in [self.base, self.quote]:
            data.append(
                [
                    self.exchange,
                    asset,
                    float(self.connector.get_balance(asset)),
                    float(self.connector.get_available_balance(asset)),
                ]
            )
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, "", regex=True)
        df.sort_values(by=["Exchange", "Asset"], inplace=True)
        return df

    def initialize_strategy(self):
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        self.tick_size = self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.last_trade_price = self.connector.get_order_book(self.trading_pair).last_trade_price
        self.starting_balance = self.get_balance_df()
        self.strategy_status = StrategyStatus.RUNNING
        # risk management
        self.risk_management = RiskManagement(
            balance_loss_threshold=self.balance_loss_threshold,
            starting_balance=self.starting_balance,
            connector=self.connector,
            base=self.base,
            quote=self.quote,
            trading_pair=self.trading_pair,
        )
        # report management
        self.report_management = ReportManagement(
            periodic_report_interval=self.periodic_report_interval,
            base=self.base,
            quote=self.quote,
        )
        # utils
        self.utils = CustomVolumePumperUtils(
            connector=self.connector,
            trading_pair=self.trading_pair,
            base=self.base,
            quote=self.quote,
        )
        self.minimum_ask_bid_spread = self.utils.convert_from_basis_point(self.minimum_ask_bid_spread_BS)

    def is_strategy_ready(self) -> bool:
        match self.strategy_status:
            case StrategyStatus.NOT_INITIALIZED:
                # initialize strategy
                self.initialize_strategy()
                return False
            case StrategyStatus.STOPPED:
                # check if balance return to the starting balance
                return False
            case StrategyStatus.UNDERBALANCED:
                return False
            case _:
                return True

    def create_periodic_summary(self):
        report = self.report_management.generate_periodic_summary()
        self.logger().notify(report)

    def is_balance_changed(self):
        is_below_threshold, stop_loss_notification = self.risk_management.is_balance_below_thresholds(
            current_balance=self.get_balance_df()
        )
        if not is_below_threshold:
            return False
        self.logger().notify(stop_loss_notification)
        self.cancel_all_orders()
        self.logger().notify("\nNOTIFICATION : Stopping strategy initiated.\nCanceling all orders")
        self.status = StrategyStatus.STOPPED
        return True

    def start_orders_delay(self):
        self.random_delay = randint(0, self.max_random_delay)
        self.last_mid_price_timestamp = self.current_timestamp

    def is_spread_below_thresholds(self, ask, bid):
        bid_ask_spread = ask - bid
        if bid_ask_spread >= self.minimum_ask_bid_spread:
            return False

        self.report_management.increase_total_tight_spread_count()
        if self.report_management.interval_tight_spread_count % 5 == 0:
            notification = "\nWARNING : Tight Spread."
            notification += f"\nTight spread count: {self.report_management.interval_tight_spread_count}"
            notification += f"\nSpread {bid_ask_spread}"
            notification += f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
            self.logger().notify(notification)
        self.start_orders_delay()
        return True

    def is_last_trade_price_changed(self):
        order_book = self.connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price

        if last_trade_price_new == float(self.last_trade_price):
            return False

        # if last trade price has changed, update last trade price and timestamp
        self.last_trade_price = last_trade_price_new
        self.start_orders_delay()
        notification = (
            "\nNOTIFICATION : Last Traded Price Has Changed."
            f"\nLast trade price: {self.last_trade_price}"
            f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
        )
        self.logger().info(notification)
        return True

    def is_order_price_out_of_spread(self, order_price, ask_price, bid_price):
        if bid_price < order_price < ask_price:
            return False

        self.report_management.increase_total_out_of_spread_count()
        self.logger().info(f"Order price {order_price} is not within spread {ask_price} - {bid_price}")
        return True

    def generate_order_candidate(self, price, amount, is_buy):
        return OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=Decimal(amount),
            price=price,
        )

    def is_order_amount_below_minimum_order_amount(self, order_amount):
        if order_amount > self.order_lower_amount:
            return False
        notification = (
            f"\nNOTIFICATION : Stopping strategy initiated"
            "\nBalance is not enough to place order."
            "\nPlease Increase Your Balance, Then Restart The Bot."
            f"\nOrder amount: {order_amount}"
            f"\nAdjusted order amount: {order_amount}"
            f"\nMinimum order amount: {self.order_lower_amount}"
            f"\nBalance: {self.get_balance_df()}"
        )
        self.status = StrategyStatus.UNDERBALANCED
        self.logger().notify(notification)
        return True

    def generate_order_amount(self, order_price):
        order_amount = randint(self.order_lower_amount, self.order_upper_amount)  # in base (GGEZ1)
        adjusted_sell_order_amount = self.utils.adjust_order_amount_for_balance(
            order_price, order_amount, self.get_balance_df(), self.exchange, TradeType.SELL
        )
        adjusted_buy_order_amount = self.utils.adjust_order_amount_for_balance(
            order_price, order_amount, self.get_balance_df(), self.exchange, TradeType.BUY
        )
        return min(adjusted_sell_order_amount, adjusted_buy_order_amount)

    def generate_volume(self, order_price, order_amount):
        sell_order_proposal = self.generate_order_candidate(order_price, order_amount, False)
        buy_order_proposal = self.generate_order_candidate(order_price, order_amount, True)

        return [
            CreateExecutorAction(
                controller_id=self.controller_id, executor_config=self.get_executor_config(sell_order_proposal)
            ),
            CreateExecutorAction(
                controller_id=self.controller_id, executor_config=self.get_executor_config(buy_order_proposal)
            ),
        ]

    def cancel_old_orders(self):
        in_flight_orders = self.connector.in_flight_orders
        if not in_flight_orders:
            return
        for client_order_id in in_flight_orders:
            if (
                self.current_timestamp - in_flight_orders[client_order_id].last_update_timestamp
                < self.active_order_total_lifespan
            ):
                return
        safe_ensure_future(self.connector.cancel_all(20))

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions proposal based on the current state of the controller.

        """
        # if the strategy status is running
        if not self.is_strategy_ready():
            return []

        # cancel active orders
        # self.cancel_old_orders()

        # generate periodic summary report if needed
        if self.is_ready_to_create_periodic_summary:
            self.create_periodic_summary()

        # check if last mid price timestamp is less than delay order time (time interval between orders)
        if not self.is_ready_to_create_order:
            return []

        # risk management check if the balance has changed
        if self.is_balance_changed():
            return []

        # calculate order price
        ask_price, bid_price, order_price = self.utils.calculate_order_price()

        # check if spread is too low
        if self.is_spread_below_thresholds(ask_price, bid_price):
            return []

        # check if last trade price has changed
        if self.is_last_trade_price_changed():
            return []

        # check if order price is within spread
        if self.is_order_price_out_of_spread(order_price, ask_price, bid_price):
            return []

        # generate random order amount and
        order_amount = self.generate_order_amount(order_price)

        # check if order amount is below the order_lower_amount
        if self.is_order_amount_below_minimum_order_amount(order_amount):
            return []

        # create orders proposals and place them (1 buy 1 sell)
        create_actions = self.generate_volume(order_price, order_amount)

        # update last traded price
        self.last_trade_price = order_price

        # update total and interval trade data for report data
        self.report_management.add_new_order(order_amount, order_price)

        # update last mid price timestamp
        self.start_orders_delay()

        return create_actions

    def formatted_strategy_config(self):
        return (
            f"\nStrategy Config :"
            f"\nBot Status: {self.strategy_status.name}"
            f"\nExchange: {self.exchange} Trading Pair: {self.trading_pair}"
            f"\nOrder Amount Range: {self.order_lower_amount} - {self.order_upper_amount} {self.base}"
            f"\nDelay Order Time: {self.delay_order_time} seconds + Random Delay: 0 - {self.max_random_delay} seconds"
            f"\nMinimum Ask Bid Spread: {self.minimum_ask_bid_spread_BS} basis points"
            f"\nBalance Loss Threshold: {self.balance_loss_threshold} {self.quote}"
            f"\nPeriodic Report Interval: {self.periodic_report_interval} hour(s)"
            f"\n\n Current Price Trend : {self.utils._current_price_movement}wards"  # upwards or downwards
        )

    def to_format_status(self):
        status = super().to_format_status()
        status.append(self.report_management.generate_report())
        status.append(self.formatted_strategy_config())
        return status
