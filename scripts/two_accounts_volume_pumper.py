import math
import os
import random
import time
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from random import randint
from typing import Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# ─── Config ──────────────────────────────────────────────────────────────────


class TwoAccountsVolumePumperConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field(
        "coinstore",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Exchange where the bot will trade",
        },
    )
    second_exchange: str = Field(
        "coinstore_2",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Second exchange (same exchange, different account instance)",
        },
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Trading pair in which the bot will place orders",
        },
    )
    order_lower_amount: int = Field(
        500,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Lower value for order amount (in base asset)",
        },
    )
    order_upper_amount: int = Field(
        2000,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Upper value for order amount (in base asset)",
        },
    )
    delay_order_time: int = Field(
        120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Delay time between orders (in seconds)",
        },
    )
    max_random_delay: int = Field(
        120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Maximum random delay added to delay_order_time (in seconds)",
        },
    )
    balance_loss_threshold: Decimal = Field(
        Decimal("0"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Balance loss threshold (in quote asset)",
        },
    )
    minimum_ask_bid_spread: Decimal = Field(
        Decimal("10"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Minimum ask-bid spread (basis points)",
        },
    )
    periodic_report_interval: float = Field(
        0,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Interval for periodic report (in hours, 0 to disable)",
        },
    )


# ─── Report Management ──────────────────────────────────────────────────────


class ReportTracker:
    def __init__(self, periodic_report_interval: float, base: str, quote: str):
        self.report_frequency = 60 * 60 * periodic_report_interval  # seconds
        self.periodic_report_interval = periodic_report_interval
        self.base = base
        self.quote = quote
        self.starting_time = datetime.now()
        self.last_report_timestamp = time.time()
        # totals
        self.total_traded_volume_quote = 0
        self.total_traded_volume_base = 0
        self.total_trades_count = 0
        self.total_tight_spread_count = 0
        self.total_out_of_spread_count = 0
        # interval
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
            vol_q = self.interval_traded_volume_quote
            vol_b = self.interval_traded_volume_base
            trades = self.interval_trades_count
            tight = self.interval_tight_spread_count
            oos = self.interval_out_of_spread_count
            duration_line = f"\nThis Report Covers The Last {self.periodic_report_interval} hour(s)"
        else:
            report_type = "Summary Report"
            vol_q = self.total_traded_volume_quote
            vol_b = self.total_traded_volume_base
            trades = self.total_trades_count
            tight = self.total_tight_spread_count
            oos = self.total_out_of_spread_count
            duration_line = ""

        running = self._format_duration(delta=datetime.now() - self.starting_time)
        return (
            f"\n{report_type}:"
            f"{duration_line}"
            f"\nTotal Traded Volume In Quote: {vol_q} {self.quote}"
            f"\nTotal Traded Volume In Base: {vol_b} {self.base}"
            f"\nTotal Trades Count: {trades}"
            f"\nTotal Tight Spread Error Count: {tight}"
            f"\nTotal Out Of Spread Error Count: {oos}"
            f"\nTotal Running Time: {running}"
        )

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


# ─── Risk Management ────────────────────────────────────────────────────────


class RiskChecker:
    def __init__(
        self,
        balance_loss_threshold: Decimal,
        starting_balance: pd.DataFrame,
        connector: ConnectorBase,
        base: str,
        quote: str,
        trading_pair: str,
    ):
        self.balance_loss_threshold = balance_loss_threshold
        self.starting_balance = starting_balance
        self.connector = connector
        self.base = base
        self.quote = quote
        self.trading_pair = trading_pair

    def _calculate_quote_base_balance_threshold(self):
        quote_threshold = self.balance_loss_threshold
        mid_price = self.connector.get_mid_price(self.trading_pair)
        base_threshold = quote_threshold / mid_price
        return quote_threshold, base_threshold

    def _get_balance_differences_df(self, current_balance: pd.DataFrame):
        sb = self.starting_balance
        diff_df = pd.DataFrame({
            "Exchange": sb["Exchange"],
            "Asset": sb["Asset"],
            "Starting_Available_Balance": sb["Available Balance"],
            "Starting_Balance": sb["Total Balance"],
            "Current_Available_Balance": current_balance["Available Balance"],
            "Current_Balance": current_balance["Total Balance"],
        })
        diff_df["Difference_Balance"] = diff_df["Current_Balance"] - diff_df["Starting_Balance"]
        diff_df["Difference_Available_Balance"] = (
            diff_df["Current_Available_Balance"] - diff_df["Starting_Available_Balance"]
        )
        return diff_df

    def _check_balance_threshold(self, balance_df, asset, threshold):
        try:
            difference = abs(Decimal(str(balance_df.loc[balance_df["Asset"] == asset, "Difference_Balance"].iloc[0])))
            return difference > threshold
        except (KeyError, IndexError):
            return False

    def is_balance_below_thresholds(self, current_balance: pd.DataFrame) -> tuple:
        quote_threshold, base_threshold = self._calculate_quote_base_balance_threshold()
        diff_df = self._get_balance_differences_df(current_balance)
        if len(diff_df["Exchange"].unique()) > 1:
            diff_df = (
                diff_df.groupby("Asset")
                .agg({
                    "Starting_Available_Balance": "sum",
                    "Starting_Balance": "sum",
                    "Current_Available_Balance": "sum",
                    "Current_Balance": "sum",
                    "Difference_Balance": "sum",
                    "Difference_Available_Balance": "sum",
                })
                .reset_index()
            )
        base_cond = self._check_balance_threshold(diff_df.round(2), self.base, base_threshold)
        quote_cond = self._check_balance_threshold(diff_df.round(2), self.quote, quote_threshold)
        is_below = base_cond or quote_cond
        notification = self._build_notification(diff_df, base_cond, quote_cond)
        return is_below, notification

    def check_balance_returned(self, current_balance: pd.DataFrame) -> bool:
        if current_balance.equals(self.starting_balance):
            return True
        if len(current_balance["Exchange"].unique()) > 1:
            cur_agg = current_balance.groupby("Asset").agg({"Total Balance": "sum", "Available Balance": "sum"}).round(2)
            start_agg = self.starting_balance.groupby("Asset").agg({"Total Balance": "sum", "Available Balance": "sum"}).round(2)
            if cur_agg.equals(start_agg):
                return True
        return False

    def _build_notification(self, diff_df: pd.DataFrame, base_cond: bool, quote_cond: bool) -> str:
        if not (base_cond or quote_cond):
            return ""
        notification = "\nWARNING : Balance below threshold."
        if base_cond:
            row = diff_df.loc[diff_df["Asset"] == self.base].iloc[0]
            notification += (
                f"\nBase Asset getting below threshold"
                f"\nCurrent Base Balance: {row['Current_Balance']}"
                f"\nDifference Base : {row['Difference_Balance']}"
                f"\nDifference Base Available Balance : {row['Difference_Available_Balance']}"
            )
        if quote_cond:
            row = diff_df.loc[diff_df["Asset"] == self.quote].iloc[0]
            notification += (
                f"\nQuote Asset getting below threshold"
                f"\nCurrent Quote Balance: {row['Current_Balance']}"
                f"\nDifference Quote : {row['Difference_Balance']}"
                f"\nDifference Quote Available Balance : {row['Difference_Available_Balance']}"
            )
        return notification


# ─── Utility Functions ───────────────────────────────────────────────────────


def percent_distance_from_bid(ask: Decimal, bid: Decimal, price: Decimal) -> Decimal:
    price_range = ask - bid
    if price_range == 0:
        return Decimal(0)
    return ((price - bid) / price_range) * Decimal(100)


def round_to_tick_size(price: Decimal, tick_size: Decimal) -> Decimal:
    return math.floor(price / tick_size) * tick_size


def basis_points_to_decimal(bp) -> Decimal:
    return Decimal(str(bp)) / Decimal("10000")


def adjust_order_amount_for_balance(
    order_price: Decimal,
    order_amount: Decimal,
    balance: pd.DataFrame,
    exchange: str,
    order_side: TradeType,
    base: str,
    quote: str,
) -> Decimal:
    new_order_amount = deepcopy(order_amount)
    if order_side == TradeType.BUY:
        quote_balance = Decimal(str(
            balance.loc[(balance["Exchange"] == exchange) & (balance["Asset"] == quote), "Available Balance"].iloc[0]
        ))
        if quote_balance < order_amount * order_price:
            new_order_amount = math.floor(quote_balance / order_price)
    else:
        base_balance = Decimal(str(
            balance.loc[(balance["Exchange"] == exchange) & (balance["Asset"] == base), "Available Balance"].iloc[0]
        ))
        if base_balance < order_amount:
            new_order_amount = base_balance
    return new_order_amount


# ─── Strategy ────────────────────────────────────────────────────────────────


class TwoAccountsVolumePumperStatus(Enum):
    NOT_INITIALIZED = 0
    RUNNING = 1
    STOPPED = 2
    UNDERBALANCED = 3


class TwoAccountsVolumePumper(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: TwoAccountsVolumePumperConfig):
        cls.markets = {config.exchange: {config.trading_pair}, config.second_exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: TwoAccountsVolumePumperConfig):
        super().__init__(connectors)
        self.first_exchange = config.exchange
        self.second_exchange = config.second_exchange
        self.trading_pair = config.trading_pair
        self.order_lower_amount = config.order_lower_amount
        self.order_upper_amount = config.order_upper_amount
        self.delay_order_time = config.delay_order_time
        self.balance_loss_threshold = config.balance_loss_threshold
        self.minimum_ask_bid_spread_bp = config.minimum_ask_bid_spread
        self.max_random_delay = config.max_random_delay
        self.periodic_report_interval = config.periodic_report_interval
        # strategy state
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        self.status = TwoAccountsVolumePumperStatus.NOT_INITIALIZED
        self.first_exchange_order_side = TradeType.BUY
        self.second_exchange_order_side = TradeType.SELL
        self._current_price_movement = "up"

    @property
    def first_connector(self) -> ConnectorBase:
        return self.connectors[self.first_exchange]

    @property
    def second_connector(self) -> ConnectorBase:
        return self.connectors[self.second_exchange]

    # ── Initialization ───────────────────────────────────────────────────

    def init_strategy(self):
        self.logger().info("Initializing strategy...")
        best_bid_price = self.first_connector.get_mid_price(self.trading_pair)
        self.tick_size = self.first_connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.logger().info(f"Tick size for {self.trading_pair} on {self.first_exchange}: {self.tick_size}")
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.last_trade_price = self.first_connector.get_order_book(self.trading_pair).last_trade_price
        self.starting_balance = self.get_balance_df()
        self.minimum_ask_bid_spread = basis_points_to_decimal(self.minimum_ask_bid_spread_bp)
        self.risk_checker = RiskChecker(
            balance_loss_threshold=self.balance_loss_threshold,
            starting_balance=self.starting_balance,
            connector=self.first_connector,
            base=self.base,
            quote=self.quote,
            trading_pair=self.trading_pair,
        )
        self.report_tracker = ReportTracker(
            periodic_report_interval=self.periodic_report_interval,
            base=self.base,
            quote=self.quote,
        )
        self.status = TwoAccountsVolumePumperStatus.RUNNING

    # ── Price Calculation ────────────────────────────────────────────────

    def calculate_order_price(self):
        best_ask_price = self.first_connector.get_price(self.trading_pair, True)
        best_bid_price = self.first_connector.get_price(self.trading_pair, False)
        mid_price = self.first_connector.get_mid_price(self.trading_pair)
        last_trade_price = Decimal(str(self.first_connector.get_order_book(self.trading_pair).last_trade_price))
        if best_bid_price > last_trade_price or best_ask_price < last_trade_price:
            last_trade_price = mid_price

        self._decide_price_movement(best_ask_price, best_bid_price, last_trade_price)

        direction = 1 if self._current_price_movement == "up" else -1
        order_price = Decimal(str(
            last_trade_price + self.tick_size * Decimal(randint(0, 5)) * direction
        ))

        if order_price < best_bid_price:
            order_price = best_bid_price + self.tick_size
        if order_price > best_ask_price:
            order_price = best_ask_price - self.tick_size

        order_price = round_to_tick_size(order_price, self.tick_size)
        return best_ask_price, best_bid_price, order_price

    def _decide_price_movement(self, best_ask_price: Decimal, best_bid_price: Decimal, last_trade_price: Decimal):
        bid_distance = percent_distance_from_bid(best_ask_price, best_bid_price, last_trade_price)
        if self._current_price_movement == "down":
            flip_probability = (1 - float(bid_distance) / 100) ** 3
        else:
            flip_probability = (float(bid_distance) / 100) ** 3
        if random.uniform(0, 1) < flip_probability:
            self._current_price_movement = "up" if self._current_price_movement == "down" else "down"

    # ── Tick Logic ───────────────────────────────────────────────────────

    def on_tick(self):
        if self.status == TwoAccountsVolumePumperStatus.NOT_INITIALIZED:
            self.init_strategy()

        if self.status == TwoAccountsVolumePumperStatus.STOPPED:
            if self.risk_checker.check_balance_returned(current_balance=self.get_balance_df()):
                self.logger().notify("\nNOTIFICATION : Balance has returned to starting balance.\nResuming strategy.")
                self.status = TwoAccountsVolumePumperStatus.RUNNING
            return

        if self.status == TwoAccountsVolumePumperStatus.UNDERBALANCED:
            return

        # periodic report
        if (
            self.periodic_report_interval > 0
            and self.current_timestamp - self.report_tracker.last_report_timestamp
            >= self.report_tracker.report_frequency
        ):
            report = self.report_tracker.generate_periodic_summary()
            self.logger().notify(report)

        # delay between orders
        if self.current_timestamp - self.last_mid_price_timestamp < self.delay_order_time + self.random_delay:
            return

        # risk management
        is_below, notification = self.risk_checker.is_balance_below_thresholds(current_balance=self.get_balance_df())
        if is_below:
            self.logger().notify(notification)
            self.cancel_all_orders(self.first_exchange)
            self.cancel_all_orders(self.second_exchange)
            self.logger().notify("\nNOTIFICATION : Stopping strategy initiated.\nCanceling all orders")
            self.status = TwoAccountsVolumePumperStatus.STOPPED
            return

        # calculate order price
        best_ask_price, best_bid_price, order_price = self.calculate_order_price()

        # check spread
        bid_ask_spread = best_ask_price - best_bid_price
        if bid_ask_spread < self.minimum_ask_bid_spread:
            self.report_tracker.increase_total_tight_spread_count()
            if self.report_tracker.interval_tight_spread_count % 5 == 0:
                notification = (
                    f"\nWARNING : Tight Spread."
                    f"\nTight spread count: {self.report_tracker.interval_tight_spread_count}"
                    f"\nSpread {bid_ask_spread}"
                    f"\nOrder placing is delayed by {self.random_delay + self.delay_order_time} seconds"
                )
                self.logger().notify(notification)
            self.start_orders_delay()
            return

        # check if last trade price changed
        order_book = self.first_connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price
        if last_trade_price_new != float(self.last_trade_price):
            self.last_trade_price = last_trade_price_new
            self.start_orders_delay()
            self.logger().info(
                f"\nNOTIFICATION : Last Traded Price Has Changed."
                f"\nLast trade price: {self.last_trade_price}"
                f"\nOrder placing is delayed by {self.random_delay + self.delay_order_time} seconds"
            )
            return

        # place orders if price within spread
        if best_bid_price < order_price < best_ask_price:
            order_amount = randint(self.order_lower_amount, self.order_upper_amount)

            adjusted_first = adjust_order_amount_for_balance(
                order_price, order_amount, self.get_balance_df(),
                self.first_exchange, self.first_exchange_order_side, self.base, self.quote,
            )
            adjusted_second = adjust_order_amount_for_balance(
                order_price, order_amount, self.get_balance_df(),
                self.second_exchange, self.second_exchange_order_side, self.base, self.quote,
            )
            adjusted_order_amount = min(adjusted_first, adjusted_second)

            if adjusted_order_amount < self.order_lower_amount:
                if self.is_balance_below_minimum_order_amount(self.first_exchange):
                    self.logger().notify(
                        f"\nNOTIFICATION : {self.first_exchange} balance is below minimum order amount."
                    )
                    self.status = TwoAccountsVolumePumperStatus.UNDERBALANCED
                    return
                if self.is_balance_below_minimum_order_amount(self.second_exchange):
                    self.logger().notify(
                        f"\nNOTIFICATION : {self.second_exchange} balance is below minimum order amount."
                    )
                    self.status = TwoAccountsVolumePumperStatus.UNDERBALANCED
                    return
                self.flip_next_order_side()
                return

            first_order = self.generate_order_candidate(order_price, adjusted_order_amount, self.first_exchange_order_side)
            second_order = self.generate_order_candidate(order_price, adjusted_order_amount, self.second_exchange_order_side)
            self.place_order(self.first_exchange, first_order)
            self.place_order(self.second_exchange, second_order)

            self.last_trade_price = order_price
            self.report_tracker.add_new_order(adjusted_order_amount, order_price)
            self.flip_next_order_side()
        else:
            self.report_tracker.increase_total_out_of_spread_count()
            self.logger().info(f"Order price {order_price} is not within spread {best_ask_price} - {best_bid_price}")

        self.start_orders_delay()
        self.logger().info(f"\nNext order is delayed by {self.random_delay + self.delay_order_time} seconds")

    # ── Order Helpers ────────────────────────────────────────────────────

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def generate_order_candidate(self, order_price, order_amount, order_side):
        return OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=order_side,
            amount=Decimal(str(order_amount)),
            price=order_price,
        )

    def flip_next_order_side(self):
        if self.first_exchange_order_side == TradeType.SELL:
            self.first_exchange_order_side = TradeType.BUY
            self.second_exchange_order_side = TradeType.SELL
        else:
            self.first_exchange_order_side = TradeType.SELL
            self.second_exchange_order_side = TradeType.BUY

    def cancel_all_orders(self, exchange: str):
        for order in self.get_active_orders(connector_name=exchange):
            self.cancel(exchange, order.trading_pair, order.client_order_id)

    def start_orders_delay(self):
        self.random_delay = randint(0, self.max_random_delay)
        self.last_mid_price_timestamp = self.current_timestamp

    def is_balance_below_minimum_order_amount(self, exchange: str):
        balance_df = self.get_balance_df()
        mid_price = float(self.first_connector.get_mid_price(self.trading_pair))
        base_balances = (
            balance_df.loc[
                (balance_df["Asset"] == self.base) & (balance_df["Exchange"] == exchange), ["Available Balance"]
            ].iloc[0].values[0]
        )
        quote_balances = (
            balance_df.loc[
                (balance_df["Asset"] == self.quote) & (balance_df["Exchange"] == exchange), ["Available Balance"]
            ].iloc[0].values[0]
        )
        quote_balances = quote_balances / mid_price
        return base_balances < self.order_lower_amount and quote_balances < self.order_lower_amount

    # ── Lifecycle ────────────────────────────────────────────────────────

    def on_stop(self):
        self.cancel_all_orders(self.first_exchange)
        self.cancel_all_orders(self.second_exchange)
        self.logger().notify(f"\nNOTIFICATION : Stopping strategy initiated.\n{self.format_status()}")
        return super().on_stop()

    def format_status(self) -> str:
        text = super().format_status()
        order_info = (
            f"\nStrategy Config :"
            f"\nBot Status: {self.status.name}"
            f"\nExchange: {self.first_exchange} Trading Pair: {self.trading_pair}"
            f"\nOrder Amount Range: {self.order_lower_amount} - {self.order_upper_amount} {self.base}"
            f"\nDelay Order Time: {self.delay_order_time} seconds + Random Delay: 0 - {self.max_random_delay} seconds"
            f"\nMinimum Ask Bid Spread: {self.minimum_ask_bid_spread_bp} basis points"
            f"\nBalance Loss Threshold: {self.balance_loss_threshold} {self.quote}"
            f"\nPeriodic Report Interval: {self.periodic_report_interval} hour(s)"
            f"\n\n Current Price Trend : {self._current_price_movement}wards"
        )
        return text + f"\n\n{order_info}\n\n{self.report_tracker.generate_report()}"
