"""
Report service for the Volume Pumper strategy.

This service handles trading statistics tracking and report generation.
"""

import time
from datetime import datetime, timedelta
from decimal import Decimal


class ReportService:
    """
    Service for reporting and statistics.

    This service is responsible for:
    - Tracking trade statistics (volume, count)
    - Tracking error counts (tight spread, out of spread)
    - Generating summary and periodic reports
    - Managing report timing

    Single Responsibility: Statistics tracking and reporting.
    """

    def __init__(
        self,
        base: str,
        quote: str,
        periodic_report_interval: float,
    ):
        """
        Initialize the report service.

        Args:
            base: Base asset symbol
            quote: Quote asset symbol
            periodic_report_interval: Report interval in hours (0 = disabled)
        """
        self._base = base
        self._quote = quote
        self._report_interval_hours = periodic_report_interval
        self._report_frequency_seconds = 60 * 60 * periodic_report_interval

        # Timestamps
        self._starting_time = datetime.now()
        self._last_report_timestamp = time.time()

        # Total statistics (cumulative)
        self._total_volume_quote = Decimal("0")
        self._total_volume_base = Decimal("0")
        self._total_trades_count = 0
        self._total_tight_spread_count = 0
        self._total_out_of_spread_count = 0

        # Interval statistics (reset each report)
        self._interval_volume_quote = Decimal("0")
        self._interval_volume_base = Decimal("0")
        self._interval_trades_count = 0
        self._interval_tight_spread_count = 0
        self._interval_out_of_spread_count = 0

    @property
    def base(self) -> str:
        """Get the base asset."""
        return self._base

    @property
    def quote(self) -> str:
        """Get the quote asset."""
        return self._quote

    @property
    def total_trades(self) -> int:
        """Get total number of trades."""
        return self._total_trades_count

    @property
    def total_volume_base(self) -> Decimal:
        """Get total volume in base currency."""
        return self._total_volume_base

    @property
    def total_volume_quote(self) -> Decimal:
        """Get total volume in quote currency."""
        return self._total_volume_quote

    def track_trade(self, amount: Decimal, price: Decimal) -> None:
        """
        Record a completed trade.

        Args:
            amount: Trade amount in base currency
            price: Trade price
        """
        volume_quote = amount * price

        # Update totals
        self._total_volume_quote += volume_quote
        self._total_volume_base += amount
        self._total_trades_count += 1

        # Update interval
        self._interval_volume_quote += volume_quote
        self._interval_volume_base += amount
        self._interval_trades_count += 1

    def track_tight_spread(self) -> None:
        """Record a tight spread occurrence."""
        self._total_tight_spread_count += 1
        self._interval_tight_spread_count += 1

    def track_out_of_spread(self) -> None:
        """Record an out-of-spread occurrence."""
        self._total_out_of_spread_count += 1
        self._interval_out_of_spread_count += 1

    def is_report_due(self) -> bool:
        """
        Check if a periodic report is due.

        Returns:
            True if report should be generated
        """
        if self._report_interval_hours <= 0:
            return False

        elapsed = time.time() - self._last_report_timestamp
        return elapsed >= self._report_frequency_seconds

    def generate_summary(self) -> str:
        """
        Generate a summary report of all-time statistics.

        Returns:
            Formatted summary report string
        """
        return self._generate_report(
            report_type="Summary Report",
            volume_quote=self._total_volume_quote,
            volume_base=self._total_volume_base,
            trades_count=self._total_trades_count,
            tight_spread_count=self._total_tight_spread_count,
            out_of_spread_count=self._total_out_of_spread_count,
            include_interval_note=False,
        )

    def generate_periodic_report(self) -> str:
        """
        Generate a periodic interval report and reset interval counters.

        Returns:
            Formatted periodic report string
        """
        report = self._generate_report(
            report_type="Periodic Summary Report",
            volume_quote=self._interval_volume_quote,
            volume_base=self._interval_volume_base,
            trades_count=self._interval_trades_count,
            tight_spread_count=self._interval_tight_spread_count,
            out_of_spread_count=self._interval_out_of_spread_count,
            include_interval_note=True,
        )

        # Reset interval counters
        self._reset_interval_data()
        self._last_report_timestamp = time.time()

        return report

    def _generate_report(
        self,
        report_type: str,
        volume_quote: Decimal,
        volume_base: Decimal,
        trades_count: int,
        tight_spread_count: int,
        out_of_spread_count: int,
        include_interval_note: bool,
    ) -> str:
        """
        Generate a formatted report.

        Args:
            report_type: Title for the report
            volume_quote: Volume in quote currency
            volume_base: Volume in base currency
            trades_count: Number of trades
            tight_spread_count: Tight spread occurrences
            out_of_spread_count: Out of spread occurrences
            include_interval_note: Whether to include interval duration note

        Returns:
            Formatted report string
        """
        running_time = self._format_duration(datetime.now() - self._starting_time)

        interval_note = ""
        if include_interval_note:
            interval_note = f"\nThis Report Covers The Last {self._report_interval_hours} hour(s)"

        return (
            f"\n{report_type}:"
            f"{interval_note}"
            f"\nTotal Traded Volume In Quote: {volume_quote:.4f} {self._quote}"
            f"\nTotal Traded Volume In Base: {volume_base:.4f} {self._base}"
            f"\nTotal Trades Count: {trades_count}"
            f"\nTotal Tight Spread Error Count: {tight_spread_count}"
            f"\nTotal Out Of Spread Error Count: {out_of_spread_count}"
            f"\nTotal Running Time: {running_time}"
        )

    def _reset_interval_data(self) -> None:
        """Reset interval statistics to zero."""
        self._interval_volume_quote = Decimal("0")
        self._interval_volume_base = Decimal("0")
        self._interval_trades_count = 0
        self._interval_tight_spread_count = 0
        self._interval_out_of_spread_count = 0

    @staticmethod
    def _format_duration(delta: timedelta) -> str:
        """
        Format a timedelta as a human-readable string.

        Args:
            delta: Time duration

        Returns:
            Formatted string like "1 day(s), 2 hour(s), 3 minute(s)"
        """
        days, seconds = delta.days, delta.seconds
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days} day(s), {hours} hour(s), {minutes} minute(s), and {seconds} second(s)"

    def get_stats_dict(self) -> dict:
        """
        Get statistics as a dictionary.

        Returns:
            Dictionary with all statistics
        """
        return {
            "total_volume_quote": float(self._total_volume_quote),
            "total_volume_base": float(self._total_volume_base),
            "total_trades": self._total_trades_count,
            "total_tight_spread": self._total_tight_spread_count,
            "total_out_of_spread": self._total_out_of_spread_count,
            "interval_volume_quote": float(self._interval_volume_quote),
            "interval_volume_base": float(self._interval_volume_base),
            "interval_trades": self._interval_trades_count,
            "running_since": self._starting_time.isoformat(),
        }
