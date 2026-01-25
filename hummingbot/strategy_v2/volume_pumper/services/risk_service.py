"""
Risk service for the Volume Pumper strategy.

This service handles risk management - monitoring balance changes
and enforcing loss thresholds to protect against excessive losses.
"""

import logging
from decimal import Decimal
from typing import Tuple

import pandas as pd

from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter

logger = logging.getLogger(__name__)


class RiskService:
    """
    Service for risk management.

    This service is responsible for:
    - Tracking starting balance
    - Monitoring balance changes
    - Enforcing loss thresholds
    - Generating risk notifications

    Single Responsibility: Risk monitoring and enforcement.
    """

    def __init__(
        self,
        market_data: MarketDataAdapter,
        balance_loss_threshold: Decimal,
        order_lower_amount: int,
    ):
        """
        Initialize the risk service.

        Args:
            market_data: Market data adapter for balance information
            balance_loss_threshold: Maximum allowed loss in quote currency
            order_lower_amount: Minimum order amount for sufficiency checks
        """
        self._market_data = market_data
        self._balance_loss_threshold = balance_loss_threshold
        self._order_lower_amount = order_lower_amount
        self._starting_balance: pd.DataFrame = None

    @property
    def base(self) -> str:
        """Get the base asset."""
        try:
            return self._market_data.base
        except Exception as e:
            logger.error(
                f"Error in base property: {type(e).__name__}: {e}"
            )
            raise

    @property
    def quote(self) -> str:
        """Get the quote asset."""
        try:
            return self._market_data.quote
        except Exception as e:
            logger.error(
                f"Error in quote property: {type(e).__name__}: {e}"
            )
            raise

    def initialize(self) -> pd.DataFrame:
        """
        Initialize the risk service by recording starting balance.

        Should be called once when the strategy starts.

        Returns:
            The starting balance DataFrame
        """
        try:
            self._starting_balance = self._market_data.get_balance_df()
            return self._starting_balance
        except Exception as e:
            logger.error(
                f"Error in initialize: {type(e).__name__}: {e}"
            )
            raise

    @property
    def starting_balance(self) -> pd.DataFrame:
        """Get the starting balance DataFrame."""
        try:
            if self._starting_balance is None:
                self.initialize()
            return self._starting_balance
        except Exception as e:
            logger.error(
                f"Error in starting_balance property: {type(e).__name__}: {e}"
            )
            raise

    def is_balance_safe(self) -> Tuple[bool, str]:
        """
        Check if the current balance is within safe thresholds.

        Compares current balance against starting balance and
        checks if the difference exceeds the loss threshold.

        Returns:
            Tuple of (is_safe, notification_message)
        """
        try:
            current_balance = self._market_data.get_balance_df()
            quote_threshold, base_threshold = self._calculate_thresholds()

            # Calculate balance differences
            diff_df = self._calculate_balance_diff(current_balance)

            # Check thresholds
            base_exceeded = self._check_threshold(diff_df, self.base, base_threshold)
            quote_exceeded = self._check_threshold(diff_df, self.quote, quote_threshold)

            is_safe = not (base_exceeded or quote_exceeded)
            notification = self._generate_notification(diff_df, base_exceeded, quote_exceeded)

            return is_safe, notification
        except Exception as e:
            logger.error(
                f"Error in is_balance_safe: {type(e).__name__}: {e}"
            )
            raise

    def _calculate_thresholds(self) -> Tuple[Decimal, Decimal]:
        """
        Calculate quote and base thresholds.

        Returns:
            Tuple of (quote_threshold, base_threshold)
        """
        try:
            quote_threshold = self._balance_loss_threshold
            mid_price = self._market_data.get_mid_price()
            base_threshold = quote_threshold / mid_price
            return quote_threshold, base_threshold
        except Exception as e:
            logger.error(
                f"Error in _calculate_thresholds: {type(e).__name__}: {e}"
            )
            raise

    def _calculate_balance_diff(self, current_balance: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the difference between current and starting balance.

        Args:
            current_balance: Current balance DataFrame

        Returns:
            DataFrame with balance differences
        """
        try:
            starting = self.starting_balance

            diff_df = pd.DataFrame({
                "Exchange": starting["Exchange"],
                "Asset": starting["Asset"],
                "Starting_Balance": starting["Total Balance"],
                "Starting_Available": starting["Available Balance"],
                "Current_Balance": current_balance["Total Balance"],
                "Current_Available": current_balance["Available Balance"],
            })

            diff_df["Difference_Balance"] = (
                diff_df["Current_Balance"] - diff_df["Starting_Balance"]
            )
            diff_df["Difference_Available"] = (
                diff_df["Current_Available"] - diff_df["Starting_Available"]
            )

            return diff_df
        except Exception as e:
            logger.error(
                f"Error in _calculate_balance_diff: {type(e).__name__}: {e}"
            )
            raise

    def _check_threshold(
        self,
        diff_df: pd.DataFrame,
        asset: str,
        threshold: Decimal,
    ) -> bool:
        """
        Check if balance difference exceeds threshold for an asset.

        Args:
            diff_df: Balance difference DataFrame
            asset: Asset to check
            threshold: Threshold value

        Returns:
            True if threshold is exceeded
        """
        try:
            row = diff_df.loc[diff_df["Asset"] == asset]
            if row.empty:
                return False

            difference = abs(Decimal(str(row["Difference_Balance"].iloc[0])))
            return difference > threshold
        except (KeyError, IndexError) as e:
            logger.error(
                f"Error in _check_threshold for {asset}: {type(e).__name__}: {e}"
            )
            return False

    def _generate_notification(
        self,
        diff_df: pd.DataFrame,
        base_exceeded: bool,
        quote_exceeded: bool,
    ) -> str:
        """
        Generate a notification message about risk status.

        Args:
            diff_df: Balance difference DataFrame
            base_exceeded: Whether base threshold was exceeded
            quote_exceeded: Whether quote threshold was exceeded

        Returns:
            Notification message string
        """
        try:
            if not base_exceeded and not quote_exceeded:
                return ""

            notification = "\nWARNING: Balance below threshold."

            if base_exceeded:
                base_row = diff_df.loc[diff_df["Asset"] == self.base].iloc[0]
                notification += (
                    f"\nBase Asset ({self.base}) threshold exceeded:"
                    f"\n  Current Balance: {base_row['Current_Balance']}"
                    f"\n  Difference: {base_row['Difference_Balance']}"
                    f"\n  Available Diff: {base_row['Difference_Available']}"
                )

            if quote_exceeded:
                quote_row = diff_df.loc[diff_df["Asset"] == self.quote].iloc[0]
                notification += (
                    f"\nQuote Asset ({self.quote}) threshold exceeded:"
                    f"\n  Current Balance: {quote_row['Current_Balance']}"
                    f"\n  Difference: {quote_row['Difference_Balance']}"
                    f"\n  Available Diff: {quote_row['Difference_Available']}"
                )

            return notification
        except Exception as e:
            logger.error(
                f"Error in _generate_notification: {type(e).__name__}: {e}"
            )
            raise

    def has_balance_returned(self) -> bool:
        """
        Check if balance has returned to starting levels.

        Useful for determining when to resume a stopped strategy.

        Returns:
            True if current balance matches starting balance
        """
        try:
            current_balance = self._market_data.get_balance_df()

            if current_balance.equals(self.starting_balance):
                return True

            # Compare with some tolerance
            for asset in [self.base, self.quote]:
                starting_row = self.starting_balance.loc[
                    self.starting_balance["Asset"] == asset
                ]
                current_row = current_balance.loc[
                    current_balance["Asset"] == asset
                ]

                if starting_row.empty or current_row.empty:
                    continue

                starting_total = starting_row["Total Balance"].iloc[0]
                current_total = current_row["Total Balance"].iloc[0]

                # Allow 0.1% tolerance
                if abs(current_total - starting_total) > starting_total * 0.001:
                    return False

            return True
        except Exception as e:
            logger.error(
                f"Error in has_balance_returned: {type(e).__name__}: {e}"
            )
            raise

    def is_amount_sufficient(self, amount: Decimal) -> bool:
        """
        Check if an amount meets minimum requirements.

        Args:
            amount: The amount to check

        Returns:
            True if amount is >= order_lower_amount
        """
        try:
            return amount >= Decimal(str(self._order_lower_amount))
        except Exception as e:
            logger.error(
                f"Error in is_amount_sufficient: {type(e).__name__}: {e}"
            )
            raise

    def get_balance_report(self) -> str:
        """
        Generate a balance status report.

        Returns:
            Formatted balance report string
        """
        try:
            current_balance = self._market_data.get_balance_df()
            diff_df = self._calculate_balance_diff(current_balance)

            report = "\nBalance Status:"
            for _, row in diff_df.iterrows():
                report += (
                    f"\n  {row['Asset']}:"
                    f"\n    Starting: {row['Starting_Balance']:.4f}"
                    f"\n    Current:  {row['Current_Balance']:.4f}"
                    f"\n    Change:   {row['Difference_Balance']:.4f}"
                )

            return report
        except Exception as e:
            logger.error(
                f"Error in get_balance_report: {type(e).__name__}: {e}"
            )
            raise
