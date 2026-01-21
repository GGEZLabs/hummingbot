"""
Order adapter for the Volume Pumper strategy.

This adapter wraps the ConnectorBase to provide a clean interface
for order operations including placing, cancelling, and tracking orders.
"""

from decimal import Decimal
from typing import Dict, List

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.utils.async_utils import safe_ensure_future


class OrderAdapter:
    """
    Adapter for order operations on an exchange connector.

    This class implements the IOrderAdapter protocol and wraps
    a ConnectorBase instance to provide a clean interface for
    order management.

    Attributes:
        connector: The underlying exchange connector
        trading_pair: The trading pair (e.g., "BTC-USDT")
    """

    def __init__(
        self,
        connector: ConnectorBase,
        trading_pair: str,
    ):
        """
        Initialize the order adapter.

        Args:
            connector: The exchange connector
            trading_pair: The trading pair
        """
        self._connector = connector
        self._trading_pair = trading_pair

    @property
    def connector(self) -> ConnectorBase:
        """Get the underlying connector."""
        return self._connector

    @property
    def trading_pair(self) -> str:
        """Get the trading pair."""
        return self._trading_pair

    def get_in_flight_orders(self) -> Dict[str, InFlightOrder]:
        """
        Get all currently active orders.

        Returns:
            Dictionary mapping order_id to InFlightOrder
        """
        return self._connector.in_flight_orders

    async def get_open_orders(self) -> Dict[str, InFlightOrder]:
        """
        Fetch and track all open orders from the exchange.

        This method synchronizes local order tracking with exchange state.

        Returns:
            Dictionary mapping order_id to InFlightOrder
        """
        await self._connector.track_all_open_orders(self._trading_pair)
        return self._connector.in_flight_orders

    def cancel_order(self, order_id: str) -> None:
        """
        Cancel a specific order.

        Args:
            order_id: The client order ID to cancel
        """
        self._connector.cancel(self._trading_pair, order_id)

    async def cancel_all_orders(self, timeout: int = 20) -> None:
        """
        Cancel all active orders.

        Args:
            timeout: Timeout in seconds for the cancellation
        """
        await self._connector.cancel_all(timeout)

    def cancel_all_orders_async(self, timeout: int = 20) -> None:
        """
        Cancel all active orders asynchronously.

        Args:
            timeout: Timeout in seconds for the cancellation
        """
        safe_ensure_future(self._connector.cancel_all(timeout))

    def stop_tracking_order(self, order_id: str) -> None:
        """
        Stop tracking an order without cancelling it.

        This is useful for orders that are outside the trading range.

        Args:
            order_id: The client order ID to stop tracking
        """
        self._connector._order_tracker.stop_tracking_order(order_id)

    def create_order_candidate(
        self,
        price: Decimal,
        amount: Decimal,
        is_buy: bool,
    ) -> OrderCandidate:
        """
        Create an order candidate for execution.

        Args:
            price: The order price
            amount: The order amount
            is_buy: True for buy order, False for sell

        Returns:
            An OrderCandidate ready for execution
        """
        return OrderCandidate(
            trading_pair=self._trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=Decimal(str(amount)),
            price=Decimal(str(price)),
        )

    def get_orders_by_price(self) -> Dict[str, List[InFlightOrder]]:
        """
        Group in-flight orders by price.

        Returns:
            Dictionary mapping price string to list of orders
        """
        from collections import defaultdict

        orders_by_price = defaultdict(list)
        for order in self._connector.in_flight_orders.values():
            orders_by_price[str(order.price)].append(order)
        return dict(orders_by_price)

    def get_buy_orders(self) -> List[InFlightOrder]:
        """
        Get all buy orders.

        Returns:
            List of buy orders sorted by price (descending)
        """
        orders = [
            o for o in self._connector.in_flight_orders.values()
            if o.trade_type == TradeType.BUY
        ]
        return sorted(orders, key=lambda x: x.price, reverse=True)

    def get_sell_orders(self) -> List[InFlightOrder]:
        """
        Get all sell orders.

        Returns:
            List of sell orders sorted by price (ascending)
        """
        orders = [
            o for o in self._connector.in_flight_orders.values()
            if o.trade_type == TradeType.SELL
        ]
        return sorted(orders, key=lambda x: x.price)

    def organize_orders(
        self,
        static_support: Decimal,
        static_resistance: Decimal,
    ) -> tuple[List[InFlightOrder], List[InFlightOrder], List[InFlightOrder]]:
        """
        Organize orders into bids, asks, and out-of-range orders.

        Args:
            static_support: The static support price
            static_resistance: The static resistance price

        Returns:
            Tuple of (bids, asks, out_of_range_orders)
        """
        bids = []
        asks = []
        out_of_range = []

        for order in self._connector.in_flight_orders.values():
            if order.trade_type == TradeType.BUY:
                if order.price > static_support:
                    bids.append(order)
                else:
                    out_of_range.append(order)
            else:  # SELL
                if order.price < static_resistance:
                    asks.append(order)
                else:
                    out_of_range.append(order)

        # Sort bids descending (highest first), asks ascending (lowest first)
        bids.sort(key=lambda x: x.price, reverse=True)
        asks.sort(key=lambda x: x.price)

        return bids, asks, out_of_range

    def has_order_at_price(
        self,
        price: Decimal,
        tolerance_ticks: int = 10,
        tick_size: Decimal = None,
    ) -> bool:
        """
        Check if there's an order near a specific price.

        Args:
            price: The target price
            tolerance_ticks: Number of ticks tolerance
            tick_size: The price tick size

        Returns:
            True if an order exists near the price
        """
        if tick_size is None:
            tick_size = Decimal("0.0001")  # Default fallback

        tolerance = tick_size * tolerance_ticks

        for order in self._connector.in_flight_orders.values():
            if abs(order.price - price) <= tolerance:
                return True
        return False

    def count_active_orders(self) -> int:
        """
        Count the number of active orders.

        Returns:
            The count of active orders
        """
        return len(self._connector.in_flight_orders)

    def untrack_out_of_boundaries_orders(self, orders_to_untrack: list) -> None:
        """
        Stop tracking orders that are outside the trading boundaries.

        These orders are not cancelled - they're just removed from local tracking
        since they're outside our management range.

        Args:
            orders_to_untrack: List of InFlightOrder objects to stop tracking
        """
        for order in orders_to_untrack:
            self._connector._order_tracker.stop_tracking_order(order.client_order_id)

    async def sync_open_orders(self) -> None:
        """
        Synchronize local order tracking with exchange state.

        IMPORTANT: This must be called before conflict detection to ensure
        we have an accurate view of all account orders.

        This fetches all open orders from the exchange and adds them to
        the in_flight_orders tracking.
        """
        await self._connector.track_all_open_orders(self._trading_pair)

    async def get_organized_orders(
        self,
        static_support,
        static_resistance,
    ) -> tuple:
        """
        Fetch all open orders, organize them, and untrack out-of-range orders.

        This is the main entry point for getting orders before conflict detection:
        1. Syncs all open orders from exchange
        2. Organizes into bids, asks, out_of_range
        3. Untracks out_of_range orders (we don't manage those)
        4. Returns bids and asks for processing

        Args:
            static_support: The static support price boundary
            static_resistance: The static resistance price boundary

        Returns:
            Tuple of (bids, asks) - sorted lists of InFlightOrder
        """
        # Step 1: Sync with exchange
        await self.sync_open_orders()

        # Step 2: Organize orders
        bids, asks, out_of_range = self.organize_orders(static_support, static_resistance)

        # Step 3: Untrack out-of-range orders
        if out_of_range:
            self.untrack_out_of_boundaries_orders(out_of_range)

        return bids, asks
