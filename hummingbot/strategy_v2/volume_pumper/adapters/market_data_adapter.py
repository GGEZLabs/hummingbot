"""
Market data adapter for the Volume Pumper strategy.

This adapter wraps the ConnectorBase to provide a clean interface
for accessing market data. It abstracts away connector-specific
details and provides caching where appropriate.
"""

import functools
from decimal import Decimal
from typing import Tuple

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType


class MarketDataAdapter:
    """
    Adapter for accessing market data from an exchange connector.

    This class implements the IMarketDataProvider protocol and wraps
    a ConnectorBase instance to provide a clean interface for market
    data access.

    Attributes:
        connector: The underlying exchange connector
        trading_pair: The trading pair (e.g., "BTC-USDT")
        base: The base asset (e.g., "BTC")
        quote: The quote asset (e.g., "USDT")
    """

    def __init__(
        self,
        connector: ConnectorBase,
        trading_pair: str,
        base: str = None,
        quote: str = None,
    ):
        """
        Initialize the market data adapter.

        Args:
            connector: The exchange connector
            trading_pair: The trading pair
            base: Base asset (optional, extracted from trading_pair)
            quote: Quote asset (optional, extracted from trading_pair)
        """
        self._connector = connector
        self._trading_pair = trading_pair
        self._base = base or trading_pair.split("-")[0]
        self._quote = quote or trading_pair.split("-")[1]

    @property
    def connector(self) -> ConnectorBase:
        """Get the underlying connector."""
        return self._connector

    @property
    def trading_pair(self) -> str:
        """Get the trading pair."""
        return self._trading_pair

    @property
    def base(self) -> str:
        """Get the base asset."""
        return self._base

    @property
    def quote(self) -> str:
        """Get the quote asset."""
        return self._quote

    def get_mid_price(self) -> Decimal:
        """
        Get the current mid price for the trading pair.

        Returns:
            The mid price as a Decimal
        """
        try:
            return self._connector.get_mid_price(self._trading_pair)
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_mid_price: {type(e).__name__}: {e}"
            )
            raise

    def get_best_bid(self) -> Decimal:
        """
        Get the best bid price from the order book.

        Returns:
            The best bid price as a Decimal

        """
        try:
            return self._connector.get_price(self._trading_pair, is_buy=False)
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_best_bid: {type(e).__name__}: {e}"
            )
            raise

    def get_best_ask(self) -> Decimal:
        """
        Get the best ask price from the order book.

        Returns:
            The best ask price as a Decimal
        """
        try:
            return self._connector.get_price(self._trading_pair, is_buy=True)
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_best_ask: {type(e).__name__}: {e}"
            )
            raise

    def get_last_trade_price(self) -> Decimal:
        """
        Get the last traded price.

        Returns:
            The last trade price, or mid price if unavailable
        """
        try:
            order_book = self._connector.get_order_book(self._trading_pair)
            last_trade = Decimal(str(order_book.last_trade_price))

            # Validate last trade price is within the spread
            best_bid = self.get_best_bid()
            best_ask = self.get_best_ask()

            # Check for NaN values before comparing - NaN comparisons raise InvalidOperation
            if last_trade.is_nan() or best_bid.is_nan() or best_ask.is_nan():
                return self.get_mid_price()

            if last_trade < best_bid or last_trade > best_ask:
                return self.get_mid_price()

            return last_trade
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_last_trade_price: {type(e).__name__}: {e}"
            )
            raise

    def get_order_book_snapshot(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get a snapshot of the order book.

        Returns:
            Tuple of (bids_df, asks_df)
        """
        try:
            order_book = self._connector.get_order_book(self._trading_pair)
            snapshot = order_book.snapshot
            return snapshot[0], snapshot[1]  # bids, asks
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_order_book_snapshot: {type(e).__name__}: {e}"
            )
            raise

    @functools.cached_property
    def price_tick_size(self) -> Decimal:
        """
        Get the minimum price increment for the trading pair.

        This value is cached since it doesn't change.

        Returns:
            The price tick size as a Decimal
        """
        try:
            return self._connector.get_order_price_quantum(
                self._trading_pair, Decimal("0")
            )
        except Exception as e:
            self._connector.logger().error(
                f"Error in price_tick_size: {type(e).__name__}: {e}"
            )
            raise

    @functools.cached_property
    def amount_tick_size(self) -> Decimal:
        """
        Get the minimum amount increment for the trading pair.

        This value is cached since it doesn't change.

        Returns:
            The amount tick size as a Decimal
        """
        try:
            return self._connector.get_order_size_quantum(
                self._trading_pair, Decimal("0")
            )
        except Exception as e:
            self._connector.logger().error(
                f"Error in amount_tick_size: {type(e).__name__}: {e}"
            )
            raise

    def get_price_tick_size(self) -> Decimal:
        """Get the price tick size (protocol method)."""
        return self.price_tick_size

    def get_amount_tick_size(self) -> Decimal:
        """Get the amount tick size (protocol method)."""
        return self.amount_tick_size

    def get_min_notional_size(self) -> Decimal:
        """
        Get the minimum notional order size.

        Returns:
            The minimum notional size as a Decimal
        """
        try:
            trading_rules = self._connector._trading_rules.get(self._trading_pair)
            if trading_rules:
                return trading_rules.min_notional_size
            return Decimal("0")
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_min_notional_size: {type(e).__name__}: {e}"
            )
            raise

    def get_balance(self, asset: str) -> Decimal:
        """
        Get the total balance for an asset.

        Args:
            asset: The asset symbol

        Returns:
            The total balance
        """
        try:
            return Decimal(str(self._connector.get_balance(asset)))
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_balance for {asset}: {type(e).__name__}: {e}"
            )
            raise

    def get_available_balance(self, asset: str) -> Decimal:
        """
        Get the available balance for an asset.

        Args:
            asset: The asset symbol

        Returns:
            The available balance
        """
        try:
            return Decimal(str(self._connector.get_available_balance(asset)))
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_available_balance for {asset}: {type(e).__name__}: {e}"
            )
            raise

    def get_balance_df(self) -> pd.DataFrame:
        """
        Get balance information as a DataFrame.

        Returns:
            DataFrame with columns: Exchange, Asset, Total Balance, Available Balance
        """
        try:
            columns = ["Exchange", "Asset", "Total Balance", "Available Balance"]
            data = []

            for asset in [self._base, self._quote]:
                data.append([
                    self._connector.display_name,
                    asset,
                    float(self.get_balance(asset)),
                    float(self.get_available_balance(asset)),
                ])

            df = pd.DataFrame(data=data, columns=columns)
            df.sort_values(by=["Exchange", "Asset"], inplace=True)
            return df
        except Exception as e:
            self._connector.logger().error(
                f"Error in get_balance_df: {type(e).__name__}: {e}"
            )
            raise

    def get_available_base_balance(self) -> Decimal:
        """Get available balance for the base asset."""
        return self.get_available_balance(self._base)

    def get_available_quote_balance(self) -> Decimal:
        """Get available balance for the quote asset."""
        return self.get_available_balance(self._quote)

    def adjust_amount_for_balance(
        self,
        order_price: Decimal,
        order_amount: Decimal,
        trade_type: TradeType,
    ) -> Decimal:
        """
        Adjust order amount based on available balance.

        Args:
            order_price: The order price
            order_amount: The desired order amount
            trade_type: BUY or SELL

        Returns:
            The adjusted amount that fits within available balance
        """
        import math

        try:
            if trade_type == TradeType.BUY:
                quote_balance = self.get_available_quote_balance()
                max_amount = quote_balance / order_price
                return min(order_amount, Decimal(str(math.floor(float(max_amount)))))
            else:
                base_balance = self.get_available_base_balance()
                return min(order_amount, base_balance)
        except Exception as e:
            self._connector.logger().error(
                f"Error in adjust_amount_for_balance: {type(e).__name__}: {e}"
            )
            raise
