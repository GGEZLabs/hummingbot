import time
from datetime import datetime, timedelta


class ReportManagement:
    def __init__(self, periodic_report_interval: float, base: str, quote: str):
        self.report_frequency = 60 * 60 * periodic_report_interval  # seconds
        self.periodic_report_interval = periodic_report_interval
        self.base = base
        self.quote = quote
        self.starting_time = datetime.now()
        self.last_report_timestamp = time.time()
        self.total_traded_volume_quote = 0
        self.total_traded_volume_base = 0
        self.total_trades_count = 0
        self.total_tight_spread_count = 0
        self.total_out_of_spread_count = 0
        # interval report data
        self.interval_tight_spread_count = 0
        self.interval_traded_volume_quote = 0
        self.interval_traded_volume_base = 0
        self.interval_trades_count = 0
        self.interval_out_of_spread_count = 0

    def _format_duration(self, delta: timedelta) -> str:
        days, seconds = delta.days, delta.seconds
        hours, minutes = divmod(seconds, 3600)
        minutes, seconds = divmod(minutes, 60)
        return f"{days} day(s), {hours} hour(s), {minutes} minute(s), and {seconds} second(s)"

    def generate_report(self, is_periodic: bool = False) -> str:
        if is_periodic:
            report_type = "Periodic Summary Report"
            traded_volume_quote = self.interval_traded_volume_quote
            traded_volume_base = self.interval_traded_volume_base
            trades_count = self.interval_trades_count
            tight_spread_count = self.interval_tight_spread_count
            out_of_spread_count = self.interval_out_of_spread_count
            report_duration = f"\nThis Report Covers The Last {self.periodic_report_interval} hour(s)"
        else:
            report_type = "Summary Report"
            traded_volume_quote = self.total_traded_volume_quote
            traded_volume_base = self.total_traded_volume_base
            trades_count = self.total_trades_count
            tight_spread_count = self.total_tight_spread_count
            out_of_spread_count = self.total_out_of_spread_count
            report_duration = ""

        total_running_time = self._format_duration(delta=datetime.now() - self.starting_time)

        report = (
            f"\n{report_type}:"
            f"{report_duration}"
            f"\nTotal Traded Volume In Quote: {traded_volume_quote} {self.quote}"
            f"\nTotal Traded Volume In Base: {traded_volume_base} {self.base}"
            f"\nTotal Trades Count: {trades_count}"
            f"\nTotal Tight Spread Error Count: {tight_spread_count}"
            f"\nTotal Out Of Spread Error Count: {out_of_spread_count}"
            f"\nTotal Running Time: {total_running_time}"
        )
        return report

    def increase_total_tight_spread_count(self):
        self.total_tight_spread_count += 1
        self.interval_tight_spread_count += 1

    def increase_total_out_of_spread_count(self):
        self.total_out_of_spread_count += 1
        self.interval_out_of_spread_count += 1

    def add_new_order(self, order_amount, order_price):
        self.total_traded_volume_quote += order_amount * order_price
        self.total_traded_volume_base += order_amount
        self.total_trades_count += 1
        self.interval_traded_volume_quote += order_amount * order_price
        self.interval_traded_volume_base += order_amount
        self.interval_trades_count += 1

    def _reset_interval_data(self):
        self.interval_tight_spread_count = 0
        self.interval_traded_volume_quote = 0
        self.interval_traded_volume_base = 0
        self.interval_trades_count = 0
        self.interval_out_of_spread_count = 0

    def generate_periodic_summary(self):
        report = self.generate_report(is_periodic=True)
        self._reset_interval_data()
        self.last_report_timestamp = time.time()
        return report
