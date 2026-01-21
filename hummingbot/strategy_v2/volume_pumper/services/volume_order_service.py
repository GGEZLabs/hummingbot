"""
Volume order service for the Volume Pumper strategy.

This service handles the generation of volume orders - matched buy/sell
pairs that create trading volume on the exchange.
"""

import random
from decimal import Decimal
from typing import List, Tuple

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.order_adapter import OrderAdapter
from hummingbot.strategy_v2.volume_pumper.utils.math_utils import percent_distance_from_bid, random_int
from hummingbot.strategy_v2.volume_pumper.utils.price_utils import (
    basis_points_to_decimal,
    is_price_in_range,
    round_to_tick_size,
)


class VolumeOrderService:
    """
    Service for generating volume orders.

    This service is responsible for:
    - Calculating optimal order prices within the spread
    - Determining order amounts based on configuration and balance
    - Generating matched buy/sell order pairs
    - Validating spread and price conditions

    Single Responsibility: Volume order generation only.
    """

    def __init__(
        self,
        market_data: MarketDataAdapter,
        order_adapter: OrderAdapter,
        order_lower_amount: int,
        order_upper_amount: int,
        minimum_spread_bps: Decimal,
    ):
        """
        Initialize the volume order service.

        Args:
            market_data: Market data adapter for price information
            order_adapter: Order adapter for creating order candidates
            order_lower_amount: Minimum order amount in base currency
            order_upper_amount: Maximum order amount in base currency
            minimum_spread_bps: Minimum spread in basis points
        """
        self._market_data = market_data
        self._order_adapter = order_adapter
        self._order_lower_amount = order_lower_amount
        self._order_upper_amount = order_upper_amount
        self._minimum_spread_bps = minimum_spread_bps
        self._minimum_spread_decimal = basis_points_to_decimal(minimum_spread_bps)
        self._current_price_movement = "up"

    @property
    def price_tick_size(self) -> Decimal:
        """Get the price tick size."""
        return self._market_data.price_tick_size

    @property
    def amount_tick_size(self) -> Decimal:
        """Get the amount tick size."""
        return self._market_data.amount_tick_size

    def calculate_order_price(self) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate the optimal order price within the spread.

        The price is biased based on the current price movement direction
        to create natural-looking price action.

        Returns:
            Tuple of (ask_price, bid_price, order_price)
        """
        best_ask = self._market_data.get_best_ask()
        best_bid = self._market_data.get_best_bid()
        last_trade = self._market_data.get_last_trade_price()

        # Validate last trade price
        if last_trade < best_bid or last_trade > best_ask:
            last_trade = self._market_data.get_mid_price()

        # Update price movement direction
        self._update_price_movement(best_ask, best_bid, last_trade)

        # Calculate order price with random offset
        direction = 1 if self._current_price_movement == "up" else -1
        random_ticks = random_int(0, 5)
        order_price = last_trade + self.price_tick_size * Decimal(random_ticks) * direction

        # Ensure price is within spread
        if order_price < best_bid:
            order_price = best_bid + self.price_tick_size
        if order_price > best_ask:
            order_price = best_ask - self.price_tick_size

        order_price = round_to_tick_size(order_price, self.price_tick_size)

        return best_ask, best_bid, order_price

    def _update_price_movement(
        self,
        ask: Decimal,
        bid: Decimal,
        last_trade: Decimal,
    ) -> None:
        """
        Update the price movement direction based on position in spread.

        Uses probability to flip direction:
        - Near bid: more likely to flip to "up"
        - Near ask: more likely to flip to "down"
        """
        bid_distance = percent_distance_from_bid(ask, bid, last_trade)

        if self._current_price_movement == "down":
            # Lower bid distance = higher chance to flip up
            flip_probability = (1 - float(bid_distance) / 100) ** 3
        else:
            # Higher bid distance = higher chance to flip down
            flip_probability = (float(bid_distance) / 100) ** 3

        if random.uniform(0, 1) < flip_probability:
            self._current_price_movement = (
                "up" if self._current_price_movement == "down" else "down"
            )

    def calculate_order_amount(self, order_price: Decimal) -> Decimal:
        """
        Calculate the order amount within configured limits.

        Considers:
        - Configured min/max amounts
        - Available balance for both buy and sell sides

        Args:
            order_price: The price at which the order will be placed

        Returns:
            The calculated order amount
        """
        # Generate random amount within range
        random_amount = random_int(self._order_lower_amount, self._order_upper_amount)
        amount = Decimal(str(random_amount))

        # Adjust for available balance
        sell_amount = self._market_data.adjust_amount_for_balance(
            order_price, amount, TradeType.SELL
        )
        buy_amount = self._market_data.adjust_amount_for_balance(
            order_price, amount, TradeType.BUY
        )

        # Return the smaller of the two to ensure both orders can be placed
        return min(sell_amount, buy_amount)

    def generate_order_pair(
        self,
        price: Decimal,
        amount: Decimal,
    ) -> List[OrderCandidate]:
        """
        Generate a matched buy/sell order pair.

        Args:
            price: The order price
            amount: The order amount

        Returns:
            List containing [sell_order, buy_order]
        """
        sell_order = self._order_adapter.create_order_candidate(
            price=price,
            amount=amount,
            is_buy=False,
        )
        buy_order = self._order_adapter.create_order_candidate(
            price=price,
            amount=amount,
            is_buy=True,
        )

        return [sell_order, buy_order]

    def is_spread_acceptable(self, ask: Decimal, bid: Decimal) -> bool:
        """
        Check if the current spread meets minimum requirements.

        Args:
            ask: Best ask price
            bid: Best bid price

        Returns:
            True if spread is acceptable
        """
        spread = ask - bid
        return spread >= self._minimum_spread_decimal

    def is_price_in_spread(
        self,
        price: Decimal,
        ask: Decimal,
        bid: Decimal,
    ) -> bool:
        """
        Check if a price is within the bid-ask spread.

        Args:
            price: The price to check
            ask: Best ask price
            bid: Best bid price

        Returns:
            True if price is within spread (exclusive bounds)
        """
        return is_price_in_range(price, bid, ask, exclusive=True)

    def is_amount_sufficient(self, amount: Decimal) -> bool:
        """
        Check if an amount meets minimum requirements.

        Args:
            amount: The amount to check

        Returns:
            True if amount is >= order_lower_amount
        """
        return amount >= Decimal(str(self._order_lower_amount))

    @property
    def current_price_movement(self) -> str:
        """Get the current price movement direction."""
        return self._current_price_movement
