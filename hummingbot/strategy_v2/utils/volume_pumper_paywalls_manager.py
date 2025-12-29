from copy import copy
from decimal import Decimal
from typing import Dict, List

import numpy as np
from cachetools import TTLCache, cachedmethod

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.model.market_config import MarketConfig
from hummingbot.strategy_v2.utils.custom_volume_pumper_utils import CustomVolumePumperUtils
from hummingbot.strategy_v2.utils.market_config_manager import MarketConfigManager
from hummingbot.strategy_v2.utils.order_action_plan import OrderActionPlan
from hummingbot.strategy_v2.utils.volume_pumper_config import VolumePumperConfigBase

from .market_config_types import VolumePumperMarketConfig


class VolumePumperPaywallsManager:
    def __init__(
        self,
        market_config_manager: MarketConfigManager,
        config: VolumePumperConfigBase,
        connector: ConnectorBase,
    ):
        self._market_config_manager = market_config_manager
        self.volume_pumper_config = config
        self.connector = connector
        self.trading_pair = config.trading_pair
        self.strategy_name = config.strategy_name
        self.is_task_running = False
        self._market_config_cache = TTLCache(maxsize=10, ttl=10.0)
        self.utils = CustomVolumePumperUtils(self.connector, self.trading_pair)
        self.orders_action_plan: OrderActionPlan | None = None

        self.quote = config.trading_pair.split("-")[1]
        self.base = config.trading_pair.split("-")[0]

        self.to_be_handled_orders: List[OrderCandidate] = []

    @property
    @cachedmethod(lambda self: self._market_config_cache)
    def market_config(self) -> MarketConfig:
        return self._market_config_manager.get_market_config(self.trading_pair, self.strategy_name)

    @property
    def market_config_json(self) -> VolumePumperMarketConfig:
        return VolumePumperMarketConfig(**self.market_config.config)

    def update_orderbook_boundaries(self):
        if not self.is_task_running:
            safe_ensure_future(self.update_boundaries_task())

        return []

    def calculate_order_amount(
        self,
        order_level: float,
        all_levels: list[float],
        total_balance: float,
        common_ratio: float = 1.5,
    ) -> Decimal:
        """
        Calculate order amount using geometric progression.
        Formula: amount_i = base_amount x r^(position)
        where base_amount = total x (r - 1) / (r^n - 1)
        """
        # Validate inputs
        if order_level not in all_levels:
            raise ValueError(f"Order level {order_level} not in levels list")

        if common_ratio <= 1.0:
            raise ValueError("Common ratio must be > 1.0")

        if total_balance <= 0:
            raise ValueError("Total balance must be > 0")

        # Get position index (0-based)
        n = len(all_levels)
        position = all_levels.index(order_level)

        # Calculate base amount: total × (r - 1) / (r^n - 1)
        base_amount = total_balance * (common_ratio - 1) / (common_ratio**n - 1)

        # Calculate geometric amount: base × r^position
        amount = base_amount * (common_ratio**position)

        return self.utils.round_amount_to_tick_size(Decimal(amount))

    async def update_boundaries_task(self):
        self.is_task_running = True
        orders_action_plan = OrderActionPlan()
        orders_action_plan.cancellations_ids = await self._get_cancel_orders_id()
        orders_action_plan.creations_candidates = self.generate_orders_candidates()
        # check if similar orders are already in the order book
        orders_action_plan = self.remove_already_existing_orders(orders_action_plan)
        # check if the suggested new order book is exposed to balance loss
        # if there is an order that could effect the paywalls
        # if so , notify the user and keep everything as it is
        if self._check_if_action_plan_needs_adjustment(orders_action_plan):
            self.orders_action_plan = None
            self.is_task_running = False
            return

        self.orders_action_plan = orders_action_plan
        self.is_task_running = False

    def remove_already_existing_orders(self, orders_action_plan: OrderActionPlan):
        """
        check if similar orders are already placed and active in the order book
        if so i should remove them from the action plan
            (remove from creation candidates and from the cancellations ids)
            to archive this i need to check my current active orders (in flight orders)
            and check if any of them are similar to the orders in the action plan
            if so i should remove them from the action plan (the cancellation id and the order candidate )
            and return True
        """
        action_plan_copy = copy(orders_action_plan)
        current_orders = self.connector.in_flight_orders
        for order_candidate in action_plan_copy.creations_candidates:
            for current_order in current_orders.values():
                # check if the order is similar to the order in the action plan
                if self.utils.compare_numbers(
                    order_candidate.price, "==", current_order.price
                ) and self.utils.compare_numbers(order_candidate.amount, "==", current_order.amount):
                    action_plan_copy.cancellations_ids.remove(current_order.client_order_id)
                    action_plan_copy.creations_candidates.remove(order_candidate)

        return action_plan_copy

    def _check_if_action_plan_needs_adjustment(self, orders_action_plan: OrderActionPlan):
        bids, asks = self._conflicting_orders(orders_action_plan.creations_candidates)

        if len(bids) != 0 or len(asks) != 0:
            self.to_be_handled_orders = [
                self.utils.generate_order_candidate(order.price, order.amount, True) for order in bids.itertuples()
            ] + [self.utils.generate_order_candidate(order.price, order.amount, False) for order in asks.itertuples()]
            return True
        return False

    def _conflicting_orders(self, order_candidates: List[OrderCandidate]):
        """
        Check if there is any order ( not mine ) could result with balance loss
        if the suggested new order book is applied
        """
        # i should see the order book with out my orders
        # and check if there
        order_book = self.connector.get_order_book(self.trading_pair).snapshot
        bids = copy(order_book[0])
        asks = copy(order_book[1])
        current_orders = self.connector.in_flight_orders
        if not current_orders:
            return False
        my_bids, my_asks = self.organize_orders(current_orders)

        for i, bid in enumerate(bids.itertuples()):
            # check if the bid is not mine
            if self.utils.compare_numbers(bid.price, "<=", self.market_config_json.flexible_support):
                bids.drop(i, inplace=True)
                continue
            for my_bid in my_bids:
                if self.utils.compare_numbers(bid.price, "==", my_bid.price):
                    if self.utils.compare_numbers(bid.amount, "==", my_bid.amount) or self.utils.compare_numbers(
                        bid.amount, "==", "0"
                    ):
                        bids.drop(i, inplace=True)
                        break
                    elif self.utils.compare_numbers(bid.amount, ">", my_bid.amount):
                        bids.loc[i, ["amount"]] = [float(bid.amount) - float(my_bid.amount)]

        for i, ask in enumerate(asks.itertuples()):
            if self.utils.compare_numbers(ask.price, ">=", self.market_config_json.flexible_resistance):
                asks.drop(i, inplace=True)
                continue
            # check if the ask is not mine
            for j, my_ask in enumerate(my_asks):
                if self.utils.compare_numbers(ask.price, "==", my_ask.price):
                    if self.utils.compare_numbers(ask.amount, "==", my_ask.amount) or self.utils.compare_numbers(
                        ask.amount, "==", "0"
                    ):
                        asks.drop(i, inplace=True)
                        break
                    elif self.utils.compare_numbers(ask.amount, ">", my_ask.amount):
                        asks.loc[i, ["amount"]] = [float(ask.amount) - float(my_ask.amount)]

        return bids, asks

    def generate_orders_candidates(self):
        create_orders_candidates: List[OrderCandidate] = []
        config = self.market_config_json

        # Generate sell orders between flexible and static resistance
        create_orders_candidates.extend(
            self._generate_level_orders(config.flexible_resistance, config.static_resistance, is_buy=False)
        )

        # Generate buy orders between flexible and static support
        create_orders_candidates.extend(
            self._generate_level_orders(config.flexible_support, config.static_support, is_buy=True)
        )

        return create_orders_candidates

    async def _get_open_bids_asks(self):
        open_orders = await self.get_open_orders()
        return self.organize_orders(open_orders)

    async def _get_cancel_orders_id(self):
        bids, asks = await self._get_open_bids_asks()
        cancel_orders_ids: List[str] = []
        # my best bid is should be equal to market_config.flexible_support
        # else cancel all orders
        if not self.is_open_orders_aligned_with_boundaries(bids, asks):
            cancel_orders_ids = [order.client_order_id for order in bids + asks]

        return cancel_orders_ids

    def _generate_level_orders(self, start_price, end_price, is_buy):
        spread_perc = self.utils.get_spread(end_price if is_buy else start_price, start_price if is_buy else end_price)
        levels = list(np.arange(0, float(spread_perc), float(self.market_config_json.order_levels_steps)))

        orders = []
        for level in levels:
            price_adjustment = start_price * Decimal(level) / 100
            price = start_price - price_adjustment if is_buy else start_price + price_adjustment
            price = self.utils.round_price_to_tick_size(price)
            amount = self.calculate_order_amount(level, levels, self.volume_pumper_config.max_allowed_depth)
            order_min_amount = self.utils.round_amount_to_tick_size(
                self.connector._trading_rules[self.trading_pair].min_notional_size / price
            )
            orders.append(self.utils.generate_order_candidate(price, max(amount, order_min_amount), is_buy))

        return orders

    def is_open_orders_aligned_with_boundaries(self, bids: List[InFlightOrder], asks: List[InFlightOrder]) -> bool:
        config = self.market_config_json
        # my best ask is should be equal to market_config.flexible_resistance

        if not len(asks) or asks[0].price != config.flexible_resistance:
            return False

        # my best bid is should be equal to market_config.flexible_support
        if not len(bids) or bids[0].price != config.flexible_support:
            return False

        return True

    def is_current_order_book_valid(self):
        """
        Check if the order book has active order at price.
        check if my flexible walls orders are active and shown in the order book.
        """
        if not self.order_book_has_active_order_at_price() and not self.are_flexible_wall_active():
            return False

        return True

    def are_flexible_wall_active(self) -> bool:
        """
        Check if my flexible walls orders are active.
        """
        current_orders = self.connector.in_flight_orders.values()
        if not current_orders:
            return False
        # table schema
        return any(
            abs(float(order.price) - float(self.market_config_json.flexible_resistance))
            < float(self.utils.price_tick_size) * 10
            for order in current_orders
        ) and any(
            abs(float(order.price) - float(self.market_config_json.flexible_support))
            < float(self.utils.price_tick_size) * 10
            for order in current_orders
        )

    def order_book_has_active_order_at_price(self) -> bool:
        """
        Check if the order book has active order at price.
        """
        order_book = self.connector.get_order_book(self.trading_pair).snapshot
        bids = order_book[0]
        asks = order_book[1]

        return any(
            abs(float(order.price) - float(self.market_config_json.flexible_support))
            <= float(self.utils.price_tick_size) * 10
            for order in bids.itertuples()
        ) and any(
            abs(float(order.price) - float(self.market_config_json.flexible_resistance))
            <= float(self.utils.price_tick_size) * 10
            for order in asks.itertuples()
        )

    def organize_orders(self, open_orders: Dict[str, InFlightOrder]):
        config = self.market_config_json
        bids = []
        asks = []
        orders_to_untrack = []
        for order in open_orders.values():
            if order.trade_type == TradeType.BUY and order.price > config.static_support:
                bids.append(order)
            elif order.trade_type == TradeType.SELL and order.price < config.static_resistance:
                asks.append(order)
            else:
                orders_to_untrack.append(order)

        self.untrack_out_of_boundaries_orders(orders_to_untrack)

        # sort bids in descending order (highest price first)
        bids.sort(key=lambda x: x.price, reverse=True)
        # sort asks in ascending order (lowest price first)
        asks.sort(key=lambda x: x.price)

        return bids, asks

    def untrack_out_of_boundaries_orders(self, orders_to_untrack: List[InFlightOrder]):
        for order in orders_to_untrack:
            self.connector._order_tracker.stop_tracking_order(order.client_order_id)

    async def get_open_orders(self) -> Dict[str, InFlightOrder]:
        await self.connector.track_all_open_orders(self.trading_pair)
        return self.connector.in_flight_orders
