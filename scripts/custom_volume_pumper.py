import time
from decimal import Decimal
from random import randint
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from scripts.utils.custom_volume_pumper_config import CustomVolumePumperConfig
from scripts.utils.custom_volume_pumper_utils import CustomVolumePumperUtils
from scripts.utils.report_management import ReportManagement
from scripts.utils.risk_management import RiskManagement


class CustomVolumePumper(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: CustomVolumePumperConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CustomVolumePumperConfig):
        super().__init__(connectors)
        # config data
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.order_lower_amount = config.order_lower_amount
        self.order_upper_amount = config.order_upper_amount
        self.delay_order_time = config.delay_order_time
        self.balance_loss_threshold = config.balance_loss_threshold
        self.minimum_ask_bid_spread_BS = config.minimum_ask_bid_spread
        self.max_random_delay = config.max_random_delay
        self.periodic_report_interval = config.periodic_report_interval
        # strategy data
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        self.status = "NOT_INITIALIZED"

    @property
    def connector(self) -> ConnectorBase:
        return self.connectors[self.exchange]

    def init_strategy(self):
        """
        Initialize strategy
        - Query and set tick price (price quantum)
        - Query and set taker & maker fees for specific trading pair (just fetches
          it now, because it looks like HB just reads it from defaults instead of querying the exchange)
        """
        self.logger().info("Initializing strategy...")
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        self.tick_size = self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.logger().info(f"Tick size for {self.trading_pair} on {self.exchange}: {self.tick_size}")
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.last_trade_price = self.connector.get_order_book(self.trading_pair).last_trade_price
        self.starting_balance = self.get_balance_df()
        self.status = "RUNNING"
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
            exchange=self.exchange,
            trading_pair=self.trading_pair,
            base=self.base,
            quote=self.quote,
        )
        self.minimum_ask_bid_spread = self.utils.convert_from_basis_point(self.minimum_ask_bid_spread_BS)

    def on_tick(self):
        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        if self.status == "STOPPED":
            # check if balance return to the starting balance
            if self.risk_management.check_balance_returned(current_balance=self.get_balance_df()):
                notification = "\nNOTIFICATION : Balance has returned to starting balance.\nResuming strategy."
                self.logger().notify(notification)
                self.status = "RUNNING"

            return

        #  cancel all orders active orders
        self.cancel_all_orders()

        if (
            self.periodic_report_interval > 0
            and self.current_timestamp - self.report_management.last_report_timestamp
            >= self.report_management.report_frequency
        ):
            report = self.report_management.generate_periodic_summary()
            self.logger().notify(report)

        # check if last mid price timestamp is less than delay order time
        if self.current_timestamp - self.last_mid_price_timestamp < self.delay_order_time + self.random_delay:
            return

        # risk management
        is_below_threshold, stop_loss_notification = self.risk_management.is_balance_below_thresholds(
            current_balance=self.get_balance_df()
        )
        if is_below_threshold:
            self.logger().notify(stop_loss_notification)
            self.cancel_all_orders()
            self.logger().notify("\nNOTIFICATION : Stopping strategy initiated.\nCanceling all orders")
            self.status = "STOPPED"
            return

        # calculate order price
        best_ask_price, best_bid_price, order_price = self.utils.calculate_order_price()

        # check if spread is too low
        bid_ask_spread = best_ask_price - best_bid_price
        if bid_ask_spread < self.minimum_ask_bid_spread:
            self.report_management.increase_total_tight_spread_count()
            if self.report_management.interval_tight_spread_count % 5 == 0:
                notification = "\nWARNING : Tight Spread."
                notification += f"\nTight spread count: {self.report_management.interval_tight_spread_count}"
                notification += f"\nSpread {bid_ask_spread}"
                notification += f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
                self.logger().notify(notification)
            self.start_orders_delay()
            return

        # check if last trade price has changed
        order_book = self.connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price
        if last_trade_price_new != float(self.last_trade_price):
            # if last trade price has changed, update last trade price and timestamp
            self.last_trade_price = last_trade_price_new
            self.start_orders_delay()
            notification = "\nNOTIFICATION : Last Traded Price Has Changed."
            notification += f"\nLast trade price: {self.last_trade_price}"
            notification += f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
            self.logger().info(notification)
            return

        # TODO get last trade time
        # check if order price is within spread
        if order_price < best_ask_price and order_price > best_bid_price:
            # generate random order amount
            order_amount = randint(self.order_lower_amount, self.order_upper_amount)  # in base (GGEZ1)

            # check if we have enough balance to place order
            order_amount = self.utils.adjust_order_amount_for_balance(order_price, order_amount, self.get_balance_df())

            # create order proposals and place them
            sell_order_proposal = self.generate_order_candidate(order_price, order_amount, False)
            self.place_order(self.exchange, sell_order_proposal)

            buy_order_proposal = self.generate_order_candidate(order_price, order_amount, True)
            self.place_order(self.exchange, buy_order_proposal)
            self.last_trade_price = order_price
            # update total and interval trade data
            self.report_management.add_new_order(order_amount, order_price)

        # update last mid price timestamp
        self.start_orders_delay()
        self.logger().info(f"\nNext order is delayed by {self.random_delay+self.delay_order_time} seconds")

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        if order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def generate_order_candidate(self, order_price, order_amount, is_buy=True):
        buy_order_proposal = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=Decimal(order_amount),
            price=order_price,
        )

        return buy_order_proposal

    def cancel_all_orders(self):
        active_orders = self.get_active_orders(connector_name=self.exchange)
        for order in active_orders:
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def start_orders_delay(self):
        self.random_delay = randint(0, self.max_random_delay)
        self.last_mid_price_timestamp = self.current_timestamp

    def on_stop(self):
        self.cancel_all_orders()
        notification = "\nNOTIFICATION : Stopping strategy initiated."
        notification += f"\n{self.format_status()}"
        self.logger().notify(notification)
        return super().on_stop()

    def format_status(self) -> str:
        text = super().format_status()
        order_info = (
            f"\nStrategy Config :"
            f"\nBot Status: {self.status}"
            f"\nExchange: {self.exchange} Trading Pair: {self.trading_pair}"
            f"\nOrder Amount Range: {self.order_lower_amount} - {self.order_upper_amount} {self.base}"
            f"\nDelay Order Time: {self.delay_order_time} seconds + Random Delay: 0 - {self.max_random_delay} seconds"
            f"\nMinimum Ask Bid Spread: {self.minimum_ask_bid_spread_BS} basis points"
            f"\nBalance Loss Threshold: {self.balance_loss_threshold} {self.quote}"
            f"\nPeriodic Report Interval: {self.periodic_report_interval} hour(s)"
        )
        return text + f"\n\n{order_info}\n\n{self.report_management.generate_report()}"
