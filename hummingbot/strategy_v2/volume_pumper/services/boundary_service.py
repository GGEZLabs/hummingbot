"""
Boundary service for the Volume Pumper strategy.

This service handles the calculation and management of price boundaries
(paywalls) - the flexible and static support/resistance levels that
define where orders are placed.
"""

from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from typing import List, Tuple

import numpy as np
import pandas as pd

from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.order_adapter import OrderAdapter
from hummingbot.strategy_v2.volume_pumper.domain.enums import MovementType
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig
from hummingbot.strategy_v2.volume_pumper.domain.order_plan import OrderActionPlan
from hummingbot.strategy_v2.volume_pumper.utils.math_utils import geometric_amount
from hummingbot.strategy_v2.volume_pumper.utils.price_utils import (
    calculate_spread_percent,
    clamp_price,
    compare_numbers,
    round_to_tick_size,
)


class BoundaryService:
    """
    Service for managing price boundaries.

    This service is responsible for:
    - Calculating flexible support/resistance boundaries
    - Applying drift to boundaries based on market movement
    - Generating orders at boundary levels
    - Validating order book state against boundaries

    Single Responsibility: Boundary calculation and order generation.
    """

    def __init__(
        self,
        market_data: MarketDataAdapter,
        order_adapter: OrderAdapter,
        max_allowed_depth: float,
        order_levels_steps: Decimal,
    ):
        """
        Initialize the boundary service.

        Args:
            market_data: Market data adapter for price information
            order_adapter: Order adapter for creating order candidates
            max_allowed_depth: Maximum total order depth in base currency
            order_levels_steps: Price step between order levels (percentage)
        """
        self._market_data = market_data
        self._order_adapter = order_adapter
        self._max_allowed_depth = max_allowed_depth
        self._order_levels_steps = order_levels_steps

    @property
    def price_tick_size(self) -> Decimal:
        """Get the price tick size."""
        return self._market_data.price_tick_size

    @property
    def amount_tick_size(self) -> Decimal:
        """Get the amount tick size."""
        return self._market_data.amount_tick_size

    def calculate_boundaries(
        self,
        current_price: Decimal,
        spread_percent: Decimal,
        static_support: Decimal,
        static_resistance: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate flexible support and resistance boundaries.

        Args:
            current_price: The current market price
            spread_percent: The desired spread percentage
            static_support: The static support floor
            static_resistance: The static resistance ceiling

        Returns:
            Tuple of (support, resistance)
        """
        half_spread = current_price * (spread_percent / Decimal("200"))

        support = current_price - half_spread
        resistance = current_price + half_spread

        # Clamp to static boundaries
        support = clamp_price(support, static_support, static_resistance)
        resistance = clamp_price(resistance, static_support, static_resistance)

        # Round to tick size
        support = round_to_tick_size(support, self.price_tick_size)
        resistance = round_to_tick_size(resistance, self.price_tick_size)

        return support, resistance

    def apply_drift(
        self,
        config: VolumePumperMarketConfig,
    ) -> Tuple[Decimal, Decimal]:
        """
        Apply drift to boundaries based on movement type.

        Args:
            config: Current market configuration

        Returns:
            Tuple of (new_support, new_resistance)
        """
        drift = config.target_drift_per_interval
        movement = config.movement

        if movement == MovementType.SIDEWAYS:
            # No drift for sideways movement
            return config.flexible_support, config.flexible_resistance

        # Apply drift to both boundaries
        new_support = config.flexible_support + drift
        new_resistance = config.flexible_resistance + drift

        # Clamp to static boundaries
        new_support = clamp_price(
            new_support,
            config.static_support,
            config.static_resistance,
        )
        new_resistance = clamp_price(
            new_resistance,
            config.static_support,
            config.static_resistance,
        )

        # Round to tick size
        new_support = round_to_tick_size(new_support, self.price_tick_size)
        new_resistance = round_to_tick_size(new_resistance, self.price_tick_size)

        return new_support, new_resistance

    def generate_boundary_orders(
        self,
        config: VolumePumperMarketConfig,
    ) -> List[OrderCandidate]:
        """
        Generate orders for all boundary levels.

        Creates sell orders from flexible_resistance to static_resistance
        and buy orders from flexible_support to static_support.

        Args:
            config: Current market configuration

        Returns:
            List of OrderCandidates for all boundary levels
        """
        orders = []

        # Generate sell orders (resistance side)
        orders.extend(
            self._generate_level_orders(
                start_price=config.flexible_resistance,
                end_price=config.static_resistance,
                is_buy=False,
                order_levels_steps=config.order_levels_steps,
            )
        )

        # Generate buy orders (support side)
        orders.extend(
            self._generate_level_orders(
                start_price=config.flexible_support,
                end_price=config.static_support,
                is_buy=True,
                order_levels_steps=config.order_levels_steps,
            )
        )

        return orders

    def _generate_level_orders(
        self,
        start_price: Decimal,
        end_price: Decimal,
        is_buy: bool,
        order_levels_steps: Decimal,
    ) -> List[OrderCandidate]:
        """
        Generate orders for a range of price levels.

        Args:
            start_price: Starting price (closest to current)
            end_price: Ending price (farthest from current)
            is_buy: True for buy orders
            order_levels_steps: Step size as percentage

        Returns:
            List of OrderCandidates
        """
        # Calculate spread percentage between start and end
        spread_percent = calculate_spread_percent(
            bid=end_price if is_buy else start_price,
            ask=start_price if is_buy else end_price,
        )

        # Generate level positions
        levels = list(np.arange(0, float(spread_percent), float(order_levels_steps)))

        if not levels:
            return []

        orders = []
        for level in levels:
            # Calculate price for this level
            price_adjustment = start_price * Decimal(str(level)) / Decimal("100")

            if is_buy:
                price = start_price - price_adjustment
            else:
                price = start_price + price_adjustment

            price = round_to_tick_size(price, self.price_tick_size)

            # Calculate amount using geometric progression
            amount = geometric_amount(
                position=levels.index(level),
                total_levels=len(levels),
                total_balance=self._max_allowed_depth,
            )
            amount = round_to_tick_size(amount, self.amount_tick_size)

            # Ensure minimum notional size
            min_notional = self._market_data.get_min_notional_size()
            min_amount = round_to_tick_size(
                min_notional / price, self.amount_tick_size
            )
            amount = max(amount, min_amount)

            order = self._order_adapter.create_order_candidate(
                price=price,
                amount=amount,
                is_buy=is_buy,
            )
            orders.append(order)

        return orders

    def is_order_book_valid(self, config: VolumePumperMarketConfig) -> bool:
        """
        Check if the current order book state is valid.

        Valid means:
        - We have orders at the flexible support level
        - We have orders at the flexible resistance level

        Args:
            config: Current market configuration

        Returns:
            True if order book is valid
        """
        # tolerance = self.price_tick_size * 10

        has_support_order = self._order_adapter.has_order_at_price(
            config.flexible_support,
            tolerance_ticks=10,
            tick_size=self.price_tick_size,
        )

        has_resistance_order = self._order_adapter.has_order_at_price(
            config.flexible_resistance,
            tolerance_ticks=10,
            tick_size=self.price_tick_size,
        )

        return has_support_order and has_resistance_order

    def are_orders_aligned(
        self,
        config: VolumePumperMarketConfig,
    ) -> bool:
        """
        Check if current orders are aligned with boundary configuration.

        Args:
            config: Current market configuration

        Returns:
            True if orders are properly aligned
        """
        bids, asks, _ = self._order_adapter.organize_orders(
            static_support=config.static_support,
            static_resistance=config.static_resistance,
        )

        # Check if best ask is at flexible resistance
        if not asks or asks[0].price != config.flexible_resistance:
            return False

        # Check if best bid is at flexible support
        if not bids or bids[0].price != config.flexible_support:
            return False

        return True

    # =========================================================================
    # Conflict Detection Methods
    # =========================================================================

    def remove_already_existing_orders(
        self,
        action_plan: OrderActionPlan,
    ) -> OrderActionPlan:
        """
        Remove orders from action plan that already exist with same price/amount.

        This prevents unnecessary order churn by detecting if an order we're
        about to create already exists in the order book with the same
        price and amount. If so, it removes that order from both the
        creations list and the cancellations list (keeping the existing order).

        IMPORTANT: Handles multiple orders at the same price level by summing
        all order amounts at that price before comparison.

        Args:
            action_plan: The original action plan

        Returns:
            Optimized OrderActionPlan with existing orders removed

        Example:
            If action_plan wants to create order at price=0.5, amount=200
            and we already have orders [50, 150] at price=0.5:
            - Total existing amount at 0.5 = 200
            - This matches the creation candidate, so we skip creating it
            - We also remove the existing orders from cancellations
        """
        try:
            # Get current in-flight orders grouped by price
            current_orders = self._order_adapter.get_in_flight_orders()

            # Group orders by price (handling float prices via string conversion)
            orders_by_price = defaultdict(list)
            for order in current_orders.values():
                price_key = str(Decimal(str(order.price)))
                orders_by_price[price_key].append(order)

            # Check each creation candidate
            for order_candidate in deepcopy(action_plan.creations_candidates):
                candidate_price_key = str(Decimal(str(order_candidate.price)))

                # Get all my orders at this price
                my_orders_at_price = orders_by_price.get(candidate_price_key, [])

                if not my_orders_at_price:
                    continue

                # Check if any existing order matches this candidate
                for existing_order in my_orders_at_price:
                    # Compare amounts (both may be float or Decimal)
                    if compare_numbers(order_candidate.amount, "==", existing_order.amount):
                        # Found a matching order - remove from both lists
                        if existing_order.client_order_id in action_plan.cancellations_ids:
                            action_plan.cancellations_ids.remove(existing_order.client_order_id)

                        if order_candidate in action_plan.creations_candidates:
                            action_plan.creations_candidates.remove(order_candidate)
                        break

            return action_plan

        except Exception as e:
            # Log error but return original plan to avoid blocking
            self._market_data.connector.logger().error(
                f"Error removing already existing orders: {str(e)}"
            )
            return action_plan

    def detect_conflicting_orders(
        self,
        config: VolumePumperMarketConfig,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Detect orders from OTHER traders within the flexible boundary range.

        This method identifies third-party orders that could cause balance
        loss if our paywall orders are placed. It works by:
        1. Getting the order book snapshot
        2. Subtracting ALL of my orders at each price level
        3. Filtering to only levels within flexible boundaries
        4. Returning any remaining (third-party) orders

        IMPORTANT: Handles multiple orders at the same price by summing
        all my order amounts before subtracting from order book level.

        Args:
            config: Current market configuration with boundary levels

        Returns:
            Tuple of (conflicting_bids_df, conflicting_asks_df)
            Each DataFrame has columns: price, amount (with my orders subtracted)
            Empty DataFrames if no conflicts found
        """
        try:
            # Get order book snapshot
            bids_df, asks_df = self._market_data.get_order_book_snapshot()
            bids = deepcopy(bids_df)
            asks = deepcopy(asks_df)

            # Get my orders
            current_orders = self._order_adapter.get_in_flight_orders()
            if not current_orders:
                # No orders of mine, any orders in the range are conflicts
                return self._filter_orderbook_to_range(bids, asks, config)

            # Organize my orders into bids/asks
            my_bids, my_asks = self._organize_my_orders_by_side(current_orders)

            # Group my orders by price (sum amounts at each level)
            my_bids_by_price = self._sum_orders_by_price(my_bids)
            my_asks_by_price = self._sum_orders_by_price(my_asks)

            # Process BIDS: subtract my orders and filter to range
            bids = self._subtract_my_orders_from_orderbook(
                bids,
                my_bids_by_price,
                config.flexible_support,
                is_bid=True,
            )

            # Process ASKS: subtract my orders and filter to range
            asks = self._subtract_my_orders_from_orderbook(
                asks,
                my_asks_by_price,
                config.flexible_resistance,
                is_bid=False,
            )

            return bids, asks

        except Exception as e:
            self._market_data.connector.logger().error(
                f"Error detecting conflicting orders: {str(e)}"
            )
            return pd.DataFrame(), pd.DataFrame()

    def check_action_plan_conflicts(
        self,
        action_plan: OrderActionPlan,
        config: VolumePumperMarketConfig,
    ) -> Tuple[OrderActionPlan, List[OrderCandidate]]:
        """
        Optimize action plan and detect any conflicting orders.

        This is the main entry point that combines:
        1. remove_already_existing_orders - avoids order churn
        2. detect_conflicting_orders - finds third-party interference

        Args:
            action_plan: The original action plan
            config: Current market configuration

        Returns:
            Tuple of:
            - Optimized OrderActionPlan
            - List of conflicting OrderCandidates (empty if no conflicts)
        """
        # Step 1: Optimize the action plan
        optimized_plan = self.remove_already_existing_orders(action_plan)

        # Step 2: Detect conflicting orders
        conflicting_bids, conflicting_asks = self.detect_conflicting_orders(config)

        # Step 3: Convert conflicts to OrderCandidates for tracking
        conflicting_orders = []

        if not conflicting_bids.empty:
            for row in conflicting_bids.itertuples():
                conflicting_orders.append(
                    self._order_adapter.create_order_candidate(
                        price=Decimal(str(row.price)),
                        amount=Decimal(str(row.amount)),
                        is_buy=True,
                    )
                )

        if not conflicting_asks.empty:
            for row in conflicting_asks.itertuples():
                conflicting_orders.append(
                    self._order_adapter.create_order_candidate(
                        price=Decimal(str(row.price)),
                        amount=Decimal(str(row.amount)),
                        is_buy=False,
                    )
                )

        return optimized_plan, conflicting_orders

    async def async_check_action_plan_conflicts(
        self,
        action_plan: OrderActionPlan,
        config: VolumePumperMarketConfig,
    ) -> Tuple[OrderActionPlan, List[OrderCandidate]]:
        """
        Async version: Sync orders from exchange, then check for conflicts.

        IMPORTANT: This method MUST be used instead of check_action_plan_conflicts
        when you need accurate conflict detection. It:
        1. Fetches all open orders from the exchange
        2. Organizes them and untracks out-of-range orders
        3. Then performs conflict detection with accurate order state

        Args:
            action_plan: The original action plan
            config: Current market configuration

        Returns:
            Tuple of (optimized_plan, list_of_conflicting_orders)
        """
        # Step 1: Sync orders from exchange and organize them
        # This also untracks out-of-range orders
        await self._order_adapter.get_organized_orders(
            static_support=config.static_support,
            static_resistance=config.static_resistance,
        )

        # Step 2: Now perform conflict detection with accurate order state
        return self.check_action_plan_conflicts(action_plan, config)

    # =========================================================================
    # Helper Methods for Conflict Detection
    # =========================================================================

    def _organize_my_orders_by_side(self, orders: dict) -> Tuple[list, list]:
        """Separate orders into bids and asks based on trade type."""
        from hummingbot.core.data_type.common import TradeType

        bids = []
        asks = []
        for order in orders.values():
            if order.trade_type == TradeType.BUY:
                bids.append(order)
            else:
                asks.append(order)
        return bids, asks

    def _sum_orders_by_price(self, orders: list) -> dict:
        """
        Sum order amounts at each price level.

        Handles multiple orders at same price by aggregating amounts.

        Args:
            orders: List of orders

        Returns:
            Dict mapping price (as Decimal string) to total amount (as Decimal)
        """
        amounts_by_price = defaultdict(Decimal)
        for order in orders:
            price_key = str(Decimal(str(order.price)))
            amounts_by_price[price_key] += Decimal(str(order.amount))
        return dict(amounts_by_price)

    def _subtract_my_orders_from_orderbook(
        self,
        orderbook_df: pd.DataFrame,
        my_orders_by_price: dict,
        boundary_price: Decimal,
        is_bid: bool,
    ) -> pd.DataFrame:
        """
        Subtract my orders from order book and filter to boundary range.

        Args:
            orderbook_df: Order book DataFrame (price, amount columns)
            my_orders_by_price: Dict of my orders {price_str: total_amount}
            boundary_price: The flexible boundary price
            is_bid: True for bids, False for asks

        Returns:
            Filtered DataFrame with my orders subtracted
        """
        indices_to_drop = []

        for idx in orderbook_df.index:
            price = orderbook_df.at[idx, "price"]
            price_dec = Decimal(str(price))

            # Filter based on boundary
            # For bids: skip if price <= flexible_support (outside boundary)
            # For asks: skip if price >= flexible_resistance (outside boundary)
            if is_bid:
                if compare_numbers(price_dec, "<=", boundary_price):
                    indices_to_drop.append(idx)
                    continue
            else:
                if compare_numbers(price_dec, ">=", boundary_price):
                    indices_to_drop.append(idx)
                    continue

            # Check if I have orders at this price
            price_key = str(price_dec)
            if price_key in my_orders_by_price:
                my_total_amount = my_orders_by_price[price_key]
                live_amount = Decimal(str(orderbook_df.at[idx, "amount"]))

                # Subtract my amount from the order book level
                remaining_amount = live_amount - my_total_amount

                if compare_numbers(remaining_amount, "<=", Decimal("0")):
                    # My orders fully cover this level - no conflict
                    indices_to_drop.append(idx)
                else:
                    # There's remaining third-party amount - potential conflict
                    orderbook_df.at[idx, "amount"] = float(remaining_amount)

        # Drop filtered rows
        orderbook_df.drop(indices_to_drop, inplace=True)

        return orderbook_df

    def _filter_orderbook_to_range(
        self,
        bids: pd.DataFrame,
        asks: pd.DataFrame,
        config: VolumePumperMarketConfig,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Filter order book to only levels within flexible boundary range.

        Used when I have no orders - any orders in range are conflicts.
        """
        # Filter bids: keep only those > flexible_support
        bids_in_range = bids[
            bids["price"].apply(
                lambda p: compare_numbers(p, ">", config.flexible_support)
            )
        ].copy()

        # Filter asks: keep only those < flexible_resistance
        asks_in_range = asks[
            asks["price"].apply(
                lambda p: compare_numbers(p, "<", config.flexible_resistance)
            )
        ].copy()

        return bids_in_range, asks_in_range
