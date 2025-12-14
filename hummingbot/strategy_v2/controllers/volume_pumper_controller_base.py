import time
from enum import Enum
from random import randint
from typing import List

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.utils.custom_volume_pumper_utils import CustomVolumePumperUtils
from hummingbot.strategy_v2.utils.market_config_manager import MarketConfigManager
from hummingbot.strategy_v2.utils.order_action_plan import OrderActionPlan
from hummingbot.strategy_v2.utils.report_management import ReportManagement
from hummingbot.strategy_v2.utils.risk_management import RiskManagement
from hummingbot.strategy_v2.utils.volume_pumper_config import VolumePumperConfigBase
from hummingbot.strategy_v2.utils.volume_pumper_paywalls_architect import VolumePumperPaywallsArchitect
from hummingbot.strategy_v2.utils.volume_pumper_paywalls_manager import VolumePumperPaywallsManager


class StrategyStatus(Enum):
    NOT_INITIALIZED = 0
    RUNNING = 1
    STOPPED = 2
    UNDERBALANCED = 3
    ARCHITECT_ON_COOLDOWN = 4
    # Handles conflicting orders at the current price
    # (switches to volume filling only until conflicts are resolved)


class VolumePumperControllerBase(ControllerBase):
    def __init__(self, config: VolumePumperConfigBase, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        # config data
        self.skip_order_cancellation = True
        self.config = config
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
        self.active_order_total_lifespan = 20
        # strategy data
        self.strategy_status = StrategyStatus.NOT_INITIALIZED
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        self.next_architect_update_timestamp = 0
        # rate sources
        self.market_data_provider.initialize_rate_sources(
            [ConnectorPair(connector_name=config.exchange, trading_pair=config.trading_pair)]
        )
        client_config_map = HummingbotApplication.main_application().client_config_map

        self._sql_manager = SQLConnectionManager(
            client_config_map=client_config_map, connection_type=SQLConnectionType.TRADE_FILLS
        )
        self.session = self._sql_manager.get_new_session()

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

    @property
    def is_architect_on_cooldown(self):
        if self.next_architect_update_timestamp > self.current_timestamp:
            return True
        return False

    async def update_processed_data(self):
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
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading
            and x.is_active
            and self.current_timestamp - x.timestamp > self.active_order_total_lifespan
            and not x.config.is_paywall_order,  # and not a paywalls order
        )
        return [
            StopExecutorAction(controller_id=self.config.id, executor_id=executor.id)
            for executor in executors_to_refresh
        ]

    def initialize_strategy(self):
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        self.tick_size = self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.last_trade_price = self.connector.get_order_book(self.trading_pair).last_trade_price
        self.strategy_status = StrategyStatus.RUNNING
        # utils
        self.utils = CustomVolumePumperUtils(
            connector=self.connector,
            trading_pair=self.trading_pair,
            base=self.base,
            quote=self.quote,
        )
        self.minimum_ask_bid_spread = self.utils.convert_from_basis_point(self.minimum_ask_bid_spread_BS)
        self.starting_balance = self.utils.get_balance_df()
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
        # market config manager
        self.market_config_manager = MarketConfigManager(self.session)
        # Paywalls Architect
        self.paywalls_architect = VolumePumperPaywallsArchitect(
            self.market_config_manager,
            self.config,
            connector=self.connector,
        )
        self.paywalls_manager = VolumePumperPaywallsManager(
            self.market_config_manager,
            self.config,
            connector=self.connector,
        )
        # initialize market config
        self.market_conf = self.paywalls_architect.initializing_market_config()
        # check starting balance
        self.check_starting_balance()

    def check_starting_balance(self):
        current_price = float(self.connector.get_mid_price(self.trading_pair))
        available_balance_quote = self.utils.get_available_balance(self.starting_balance, True)
        available_balance_base = self.utils.get_available_balance(self.starting_balance, False)
        minimum_available_balance = min(
            available_balance_quote / current_price, available_balance_base
        )  # in terms of base

        total_required_base = self.order_upper_amount + self.config.max_allowed_depth

        if minimum_available_balance < total_required_base:
            # Calculate the proportion of available balance to total required balance
            proportion = minimum_available_balance / total_required_base

            # calculate the new amounts
            new_order_upper_amount = round(self.order_upper_amount * proportion)
            new_order_lower_amount = round(self.order_lower_amount * proportion)
            new_max_allowed_depth = round(self.config.max_allowed_depth * proportion)
            # notify user
            self.logger().notify(
                f"⚠️ INSUFFICIENT BALANCE DETECTED ⚠️\n"
                f"Adjusting Config :\n"
                f"  * order_upper_amount from {self.config.order_upper_amount} to {new_order_upper_amount}\n"
                f"  * order_lower_amount from {self.config.order_lower_amount} to {new_order_lower_amount}\n"
                f"  * max_allowed_depth from {self.config.max_allowed_depth} to {new_max_allowed_depth}"
            )
            # Apply the proportion to adjust order_upper_amount and max_allowed_depth
            self.order_upper_amount = new_order_upper_amount
            self.config.order_upper_amount = new_order_upper_amount

            self.order_lower_amount = new_order_lower_amount
            self.config.order_lower_amount = new_order_lower_amount

            self.config.max_allowed_depth = new_max_allowed_depth

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
            current_balance=self.utils.get_balance_df()
        )
        if not is_below_threshold:
            return False
        self.logger().notify(stop_loss_notification)
        # self.cancel_all_orders()
        self.logger().notify("\nNOTIFICATION : Stopping strategy initiated.\nCanceling all orders")
        self.strategy_status = StrategyStatus.STOPPED
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
            notification += f"\nOrder placing is delayed by {self.random_delay + self.delay_order_time} seconds"
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
            f"\nOrder placing is delayed by {self.random_delay + self.delay_order_time} seconds"
        )
        self.logger().info(notification)
        return True

    def is_order_price_out_of_spread(self, order_price, ask_price, bid_price):
        if bid_price < order_price < ask_price:
            return False

        self.report_management.increase_total_out_of_spread_count()
        self.logger().info(f"Order price {order_price} is not within spread {ask_price} - {bid_price}")
        return True

    def is_order_amount_below_minimum_order_amount(self, order_amount):
        if order_amount >= self.order_lower_amount:
            return False
        notification = (
            f"\nNOTIFICATION : Stopping strategy initiated"
            "\nBalance is not enough to place order."
            "\nPlease Increase Your Balance, Then Restart The Bot."
            f"\nOrder amount: {order_amount}"
            f"\nAdjusted order amount: {order_amount}"
            f"\nMinimum order amount: {self.order_lower_amount}"
            f"\nBalance: {self.utils.get_balance_df()}"
        )
        self.strategy_status = StrategyStatus.UNDERBALANCED
        self.logger().notify(notification)
        return True

    def generate_order_amount(self, order_price):
        order_amount = randint(self.order_lower_amount, self.order_upper_amount)  # in base (GGEZ1)
        adjusted_sell_order_amount = self.utils.adjust_order_amount_for_balance(
            order_price, order_amount, self.utils.get_balance_df(), self.exchange, TradeType.SELL
        )
        adjusted_buy_order_amount = self.utils.adjust_order_amount_for_balance(
            order_price, order_amount, self.utils.get_balance_df(), self.exchange, TradeType.BUY
        )
        return min(adjusted_sell_order_amount, adjusted_buy_order_amount)

    def generate_volume(self, order_price, order_amount):
        sell_order_proposal = self.utils.generate_order_candidate(order_price, order_amount, False)
        buy_order_proposal = self.utils.generate_order_candidate(order_price, order_amount, True)

        return [
            CreateExecutorAction(
                controller_id=self.controller_id, executor_config=self.get_executor_config(sell_order_proposal)
            ),
            CreateExecutorAction(
                controller_id=self.controller_id, executor_config=self.get_executor_config(buy_order_proposal)
            ),
        ]

    def cancel_all_orders(self):
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

    def start_architect_delay(self):
        update_interval = self.paywalls_manager.market_config_json.current_boundaries_update_interval
        self.next_architect_update_timestamp = self.current_timestamp + update_interval
        self.strategy_status = StrategyStatus.ARCHITECT_ON_COOLDOWN

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions proposal based on the current state of the controller.

        # cancel active orders
        # self.cancel_all_orders()
        """
        if not self.strategy_validations():
            return []

        if self.is_ready_to_create_periodic_summary:
            self.create_periodic_summary()
        architect_actions = self.generate_architect_actions()
        if architect_actions:
            return architect_actions

        return self.generate_volume_actions()

    def strategy_validations(self):
        # if the strategy status is running
        if not self.is_strategy_ready():
            return False

        # generate periodic summary report if needed
        if self.paywalls_manager.is_task_running:
            return False

        # check if last mid price timestamp is less than delay order time (time interval between orders)
        if not self.is_ready_to_create_order:
            return False

        # risk management check if the balance has changed
        if self.is_balance_changed():
            return False

        if self.paywalls_manager.is_task_running:
            return False

        return True

    def generate_architect_actions(self) -> List[ExecutorAction]:
        if self.is_architect_on_cooldown:
            return []

        if self.paywalls_manager.to_be_handled_orders and self.strategy_status != StrategyStatus.ARCHITECT_ON_COOLDOWN:
            notification = (
                f"\n⚠️ Warning ⚠️: Architect Paused\nExchange:{self.exchange}\nOrders Interfering with Architect:"
            )
            for order in self.paywalls_manager.to_be_handled_orders:
                notification += f"\na {order.order_side} Order at {self.utils.round_price_to_tick_size(order.price)} with amount: {self.utils.round_amount_to_tick_size(order.amount)}"
            self.logger().notify(notification)
            self.start_architect_delay()
            return []

        # cooldown is over so we need to recheck if there is a new order to be handled
        if self.strategy_status == StrategyStatus.ARCHITECT_ON_COOLDOWN:
            self.strategy_status = StrategyStatus.RUNNING
            self.paywalls_manager.to_be_handled_orders = []
            return []

        # if there is an action plan, execute it
        if self.paywalls_manager.orders_action_plan:
            action_plan = self.paywalls_manager.orders_action_plan
            self.paywalls_manager.orders_action_plan = None
            executor_actions: List[ExecutorAction] = self.generate_paywalls_executor_actions(action_plan)
            return executor_actions

        if self.paywalls_architect.is_time_to_make_decision():
            self.market_conf = self.paywalls_architect.make_decision()
            self.logger().info(f"Market Config Updated: {self.market_conf}")
            return []

        if self.paywalls_architect.is_time_to_update_boundaries():
            self.paywalls_architect.update_boundaries_config()
            self.paywalls_manager.update_orderbook_boundaries()
            """
            this delay the next check so may be the data will be up to date

            """
            self.start_orders_delay()

            return []
        # this could get an old data just before the has update_orderbook_boundaries
        elif not self.paywalls_manager.is_current_order_book_valid():
            executors_to_refresh = self.filter_executors(
                executors=self.executors_info, filter_func=lambda x: x.status == RunnableStatus.SHUTTING_DOWN
            )
            if not executors_to_refresh:
                self.paywalls_manager.update_orderbook_boundaries()
                self.start_orders_delay()

            return []

        if self.strategy_status == StrategyStatus.ARCHITECT_ON_COOLDOWN:
            self.strategy_status = StrategyStatus.RUNNING

    def generate_volume_actions(self) -> List[ExecutorAction]:
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

    def generate_paywalls_executor_actions(self, order_action_plan: OrderActionPlan) -> List[ExecutorAction]:
        """
        Generates a list of executor actions based on the provided action plan.
        - Creates StopExecutorAction for orders with an active executor.
        - Cancels orders directly if no executor is found.
        - Creates CreateExecutorAction for all order candidates.
        """
        executors_by_order_id = {executor.custom_info["order_id"]: executor for executor in (self.executors_info or [])}

        actions: List[ExecutorAction] = []

        # Handle cancellations
        for order_id in order_action_plan.cancellations_ids:
            if order_id in executors_by_order_id:
                executor_id = executors_by_order_id[order_id].id
                actions.append(
                    StopExecutorAction(executor_id=executor_id, controller_id=self.config.id, keep_position=True)
                )
            else:
                # This order doesn't have an executor, so we cancel it directly.
                self.connector.cancel(self.trading_pair, order_id)

        # Handle creations using a list comprehension for conciseness
        create_actions = [
            CreateExecutorAction(controller_id=self.config.id, executor_config=self.get_executor_config(order, True))
            for order in order_action_plan.creations_candidates
        ]
        actions.extend(create_actions)

        return actions

    def on_stop(self):
        print("STOP ")
        pass
