"""
Protocol interfaces for the Volume Pumper strategy.

These protocols define the contracts that implementations must follow,
enabling dependency injection and easy testing with mocks.

Using Protocol (structural subtyping) instead of ABC:
- No inheritance required - any class with matching methods works
- Better IDE support and type checking
- More Pythonic approach to interfaces
"""

from decimal import Decimal
from typing import Dict, List, Optional, Protocol, Tuple, runtime_checkable

import pandas as pd

from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig

# =============================================================================
# Adapter Protocols
# =============================================================================


@runtime_checkable
class IMarketDataProvider(Protocol):
    """
    Protocol for accessing market data.

    Implementations wrap exchange connectors to provide a clean interface
    for market data access.
    """

    def get_mid_price(self) -> Decimal:
        """Get the current mid price for the trading pair."""
        ...

    def get_best_bid(self) -> Decimal:
        """Get the best bid price from the order book."""
        ...

    def get_best_ask(self) -> Decimal:
        """Get the best ask price from the order book."""
        ...

    def get_last_trade_price(self) -> Decimal:
        """Get the last traded price."""
        ...

    def get_order_book_snapshot(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get a snapshot of the order book.

        Returns:
            Tuple of (bids_df, asks_df)
        """
        ...

    def get_price_tick_size(self) -> Decimal:
        """Get the minimum price increment for the trading pair."""
        ...

    def get_amount_tick_size(self) -> Decimal:
        """Get the minimum amount increment for the trading pair."""
        ...

    def get_min_notional_size(self) -> Decimal:
        """Get the minimum notional order size."""
        ...


@runtime_checkable
class IOrderAdapter(Protocol):
    """
    Protocol for order operations.

    Handles placing, cancelling, and tracking orders.
    """

    def get_in_flight_orders(self) -> Dict[str, InFlightOrder]:
        """Get all currently active orders."""
        ...

    async def get_open_orders(self) -> Dict[str, InFlightOrder]:
        """Fetch and track all open orders from the exchange."""
        ...

    def cancel_order(self, order_id: str) -> None:
        """Cancel a specific order."""
        ...

    async def cancel_all_orders(self, timeout: int = 20) -> None:
        """Cancel all active orders."""
        ...

    def stop_tracking_order(self, order_id: str) -> None:
        """Stop tracking an order without cancelling it."""
        ...

    def create_order_candidate(
        self,
        price: Decimal,
        amount: Decimal,
        is_buy: bool,
    ) -> OrderCandidate:
        """Create an order candidate for execution."""
        ...


@runtime_checkable
class IPersistenceAdapter(Protocol):
    """
    Protocol for database operations.

    Handles loading and saving market configuration.
    """

    def config_exists(self) -> bool:
        """Check if a configuration exists for this trading pair/strategy."""
        ...

    def load_config(self) -> Optional[VolumePumperMarketConfig]:
        """Load the market configuration from the database."""
        ...

    def save_config(self, config: VolumePumperMarketConfig) -> bool:
        """Save the market configuration to the database."""
        ...

    def get_last_updated(self) -> float:
        """Get the timestamp of the last configuration update."""
        ...


@runtime_checkable
class IBalanceProvider(Protocol):
    """
    Protocol for balance information.

    Provides access to account balances.
    """

    def get_balance_df(self) -> pd.DataFrame:
        """Get balance information as a DataFrame."""
        ...

    def get_available_balance(self, is_quote: bool) -> Decimal:
        """Get available balance for base or quote asset."""
        ...


# =============================================================================
# Service Protocols
# =============================================================================


@runtime_checkable
class IVolumeOrderService(Protocol):
    """
    Protocol for volume order generation.

    Responsible for creating matched buy/sell order pairs
    to generate trading volume.
    """

    def calculate_order_price(self) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate the optimal order price.

        Returns:
            Tuple of (ask_price, bid_price, order_price)
        """
        ...

    def calculate_order_amount(self, order_price: Decimal) -> Decimal:
        """
        Calculate the order amount within configured limits.

        Args:
            order_price: The price at which the order will be placed

        Returns:
            The calculated order amount
        """
        ...

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
            List containing buy and sell OrderCandidates
        """
        ...

    def is_spread_acceptable(self, ask: Decimal, bid: Decimal) -> bool:
        """Check if the current spread meets minimum requirements."""
        ...

    def is_price_in_spread(
        self,
        price: Decimal,
        ask: Decimal,
        bid: Decimal,
    ) -> bool:
        """Check if a price is within the bid-ask spread."""
        ...


@runtime_checkable
class IBoundaryService(Protocol):
    """
    Protocol for boundary (paywall) management.

    Handles the calculation and management of flexible and static
    price boundaries for order placement.
    """

    def calculate_boundaries(
        self,
        current_price: Decimal,
        spread_percent: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate flexible support and resistance boundaries.

        Args:
            current_price: The current market price
            spread_percent: The desired spread percentage

        Returns:
            Tuple of (support, resistance)
        """
        ...

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
        ...

    def generate_boundary_orders(
        self,
        config: VolumePumperMarketConfig,
    ) -> List[OrderCandidate]:
        """
        Generate orders for the boundary levels.

        Args:
            config: Current market configuration

        Returns:
            List of OrderCandidates for boundary levels
        """
        ...

    def is_order_book_valid(self, config: VolumePumperMarketConfig) -> bool:
        """Check if the current order book state is valid."""
        ...


@runtime_checkable
class IArchitectService(Protocol):
    """
    Protocol for phase decision making.

    The "architect" decides when to change phases and what
    the new phase parameters should be.
    """

    def should_make_decision(self, config: VolumePumperMarketConfig) -> bool:
        """Check if it's time to make a new phase decision."""
        ...

    def should_update_boundaries(
        self,
        config: VolumePumperMarketConfig,
        last_updated: float,
    ) -> bool:
        """Check if it's time to update boundaries."""
        ...

    def make_decision(
        self,
        config: VolumePumperMarketConfig,
        current_price: Decimal,
        current_time: float,
    ) -> VolumePumperMarketConfig:
        """
        Make a new phase decision.

        Args:
            config: Current market configuration
            current_price: Current market price
            current_time: Current timestamp

        Returns:
            Updated market configuration for the new phase
        """
        ...

    def create_initial_config(self) -> VolumePumperMarketConfig:
        """Create the initial market configuration."""
        ...


@runtime_checkable
class IRiskService(Protocol):
    """
    Protocol for risk management.

    Monitors balance changes and enforces risk thresholds.
    """

    def is_balance_safe(self) -> Tuple[bool, str]:
        """
        Check if the current balance is within safe thresholds.

        Returns:
            Tuple of (is_safe, notification_message)
        """
        ...

    def has_balance_returned(self) -> bool:
        """Check if balance has returned to starting levels."""
        ...

    def is_amount_sufficient(self, amount: Decimal) -> bool:
        """Check if an amount meets minimum requirements."""
        ...


@runtime_checkable
class IReportService(Protocol):
    """
    Protocol for reporting and statistics.

    Tracks trading statistics and generates reports.
    """

    def track_trade(self, amount: Decimal, price: Decimal) -> None:
        """Record a completed trade."""
        ...

    def track_tight_spread(self) -> None:
        """Record a tight spread occurrence."""
        ...

    def track_out_of_spread(self) -> None:
        """Record an out-of-spread occurrence."""
        ...

    def generate_summary(self) -> str:
        """Generate a summary report."""
        ...

    def generate_periodic_report(self) -> str:
        """Generate a periodic interval report and reset interval counters."""
        ...

    def is_report_due(self) -> bool:
        """Check if a periodic report is due."""
        ...
