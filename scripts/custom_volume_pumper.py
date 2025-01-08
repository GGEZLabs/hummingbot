import math
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from random import randint
from typing import Dict

import pandas as pd
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CustomVolumePumperConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field(
        "coinstore",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"),
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Trading pair in which the bot will place orders"
        ),
    )
    order_lower_amount: int = Field(
        500,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Lower value for order amount (in base asset , GGEZ1)"
        ),
    )
    order_upper_amount: int = Field(
        2000,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Upper value for order amount (in base asset , GGEZ1)"
        ),
    )
    delay_order_time: int = Field(
        120, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Delay time between orders (in seconds)")
    )
    max_random_delay: int = Field(
        120,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Maximum random delay to be add to delay_order_time (in seconds)"
        ),
    )
    balance_loss_threshold: Decimal = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Balance loss threshold (in quote asset , USDT)"
        ),
    )
    minimum_ask_bid_spread: Decimal = Field(
        10,
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Minimum ask bid spread (basis points)"),
    )
    periodic_report_interval: float = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "The interval for periodic report (in hours)"
        ),
    )


class CustomVolumePumper(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: CustomVolumePumperConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CustomVolumePumperConfig):
        super().__init__(connectors)
        # config data
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.order_lower_amount = config.order_lower_amount
        self.order_upper_amount = config.order_upper_amount
        self.delay_order_time = config.delay_order_time
        self.balance_loss_threshold = config.balance_loss_threshold
        self.minimum_ask_bid_spread = config.minimum_ask_bid_spread
        self.max_random_delay = config.max_random_delay
        self.periodic_report_interval = config.periodic_report_interval
        # strategy data
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        self.status = "NOT_INITIALIZED"
        # report data
        self.starting_time = datetime.now()
        self.report_frequency = 60 * 60 * self.periodic_report_interval  # seconds
        self.last_report_timestamp = time.time()
        self.total_traded_volume_quote = 0
        self.total_traded_volume_base = 0
        self.total_trades_count = 0
        self.total_tight_spread_count = 0
        # interval report data
        self.interval_tight_spread_count = 0
        self.interval_traded_volume_quote = 0
        self.interval_traded_volume_base = 0
        self.interval_trades_count = 0

    @property
    def connector(self):
        return self.connectors[self.exchange]

    def init_strategy(self):
        """
        Initialize strategy
        - Query and set tick price (price quantum)
        - Query and set taker & maker fees for specific trading pair (just fetches
          it now, because it looks like HB just reads it from defaults instead of querying the exchange)
        """
        self.logger().info("Initializing strategy...")
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        self.tick_size = self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)
        self.logger().info(f"Tick size for {self.trading_pair} on {self.exchange}: {self.tick_size}")
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.last_trade_price = self.connector.get_order_book(self.trading_pair).last_trade_price
        self.starting_balance = self.get_balance_df()
        self.status = "RUNNING"

    def on_tick(self):
        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        if self.status == "STOPPED":
            # check if balance return to the starting balance
            self.check_balance_return()
            return

        #  cancel all orders active orders
        self.cancel_all_orders()

        if (
            self.periodic_report_interval > 0
            and self.current_timestamp - self.last_report_timestamp >= self.report_frequency
        ):
            self.generate_periodic_summary()

        # check if last mid price timestamp is less than delay order time
        if self.current_timestamp - self.last_mid_price_timestamp < self.delay_order_time + self.random_delay:
            return

        # risk management
        self.stop_loss_when_balance_below_threshold()

        # calculate order price
        best_ask_price, best_bid_price, order_price = self.calculate_order_price()

        # check if spread is too low
        bid_ask_spread = best_ask_price - best_bid_price
        if bid_ask_spread < self.convert_from_basis_point(self.minimum_ask_bid_spread):
            self.start_orders_delay()
            notification = "\nWARNING : Tight Spread."
            notification += f"\nSpread {bid_ask_spread}"
            notification += f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
            self.logger().notify(notification)
            self.total_tight_spread_count += 1
            self.interval_tight_spread_count += 1
            return

        # check if last trade price has changed
        order_book = self.connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price
        if last_trade_price_new != float(self.last_trade_price):
            # if last trade price has changed, update last trade price and timestamp
            self.last_trade_price = last_trade_price_new
            self.start_orders_delay()
            notification = "\nNOTIFICATION : Last Traded Price Has Changed."
            notification += f"\nLast trade price: {self.last_trade_price}"
            notification += f"\nOrder placing is delayed by {self.random_delay+self.delay_order_time} seconds"
            self.logger().info(notification)
            return

        # TODO get last trade time
        # check if order price is within spread
        if order_price < best_ask_price and order_price > best_bid_price:
            # generate random order amount
            order_amount = randint(self.order_lower_amount, self.order_upper_amount)  # in base (GGEZ1)

            # check if we have enough balance to place order
            order_amount = self.adjust_order_amount_for_balance(order_price, order_amount)

            # create order proposals and place them
            sell_order_proposal = self.generate_order_candidate(order_price, order_amount, False)
            self.place_order(self.exchange, sell_order_proposal)

            buy_order_proposal = self.generate_order_candidate(order_price, order_amount, True)
            self.place_order(self.exchange, buy_order_proposal)
            self.last_trade_price = order_price
            # update total and interval trade data
            self.total_traded_volume_quote += order_amount * order_price
            self.total_traded_volume_base += order_amount
            self.total_trades_count += 1
            self.interval_traded_volume_quote += order_amount * order_price
            self.interval_traded_volume_base += order_amount
            self.interval_trades_count += 1

        # update last mid price timestamp
        self.start_orders_delay()
        self.logger().info(f"\nNext order is delayed by {self.random_delay+self.delay_order_time} seconds")

    def convert_from_basis_point(self, basis_point):
        return basis_point / 10000

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        if order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def generate_order_candidate(self, order_price, order_amount, is_buy=True):
        buy_order_proposal = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=Decimal(order_amount),
            price=order_price,
        )

        return buy_order_proposal

    def adjust_order_amount_for_balance(self, order_price, order_amount):
        balance = self.get_balance_df()
        quote_balance = Decimal(
            balance.loc[
                (balance["Exchange"] == self.exchange) & (balance["Asset"] == self.quote), "Available Balance"
            ].iloc[0]
        )
        base_balance = Decimal(
            balance.loc[
                (balance["Exchange"] == self.exchange) & (balance["Asset"] == self.base), "Available Balance"
            ].iloc[0]
        )

        if quote_balance < order_amount * order_price:
            order_amount = math.floor(quote_balance / order_price)

        if base_balance < order_amount:
            order_amount = base_balance
        return order_amount

    def calculate_order_price(self):
        best_ask_price = self.connector.get_price(self.trading_pair, True)
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        mid_price = self.connector.get_mid_price(self.trading_pair)
        order_price = Decimal((best_ask_price + mid_price) / 2) + randint(0, 99) * self.tick_size
        # round order price to tick size
        order_price = math.floor(order_price / self.tick_size) * self.tick_size
        return best_ask_price, best_bid_price, order_price

    def cancel_all_orders(self):
        active_orders = self.get_active_orders(connector_name=self.exchange)
        for order in active_orders:
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def start_orders_delay(self):
        self.random_delay = randint(0, self.max_random_delay)
        self.last_mid_price_timestamp = self.current_timestamp

    def stop_loss_when_balance_below_threshold(self):
        quote_threshold, base_threshold = self.calculate_quote_base_balance_threshold()
        balance_differences_df = self.get_balance_differences_df()
        base_condition, quote_condition = self.check_thresholds(balance_differences_df, base_threshold, quote_threshold)

        if base_condition or quote_condition:
            notification = "\nWARNING : Balance below threshold."
            if base_condition:
                base_balance = balance_differences_df.loc[balance_differences_df["Asset"] == self.base].iloc[0]
                notification += "\nBase Asset getting below threshold"
                notification += f"\nCurrent Base Balance: {str(base_balance['Current_Balance'])}"
                notification += f"\nDifference Base : {str(base_balance['Difference_Balance'])}"
                notification += (
                    f"\nDifference Base Available Balance : {str(base_balance['Difference_Available_Balance'])}"
                )
            if quote_condition:
                quote_balance = balance_differences_df.loc[balance_differences_df["Asset"] == self.quote].iloc[0]
                notification += "\nQuote Asset getting below threshold"
                notification += f"\nCurrent Quote Balance: {str(quote_balance['Current_Balance'])}"
                notification += f"\nDifference Quote : {str(quote_balance['Difference_Balance'])}"
                notification += (
                    f"\nDifference Quote Available Balance : {str(quote_balance['Difference_Available_Balance'])}"
                )

            self.logger().notify(notification)
            self.cancel_all_orders()
            self.logger().notify("\nNOTIFICATION : Stopping strategy initiated.\nCanceling all orders")
            self.status = "STOPPED"

    def calculate_quote_base_balance_threshold(self):
        quote_threshold = self.balance_loss_threshold
        mid_price = self.connector.get_mid_price(self.trading_pair)
        base_threshold = quote_threshold / mid_price
        return quote_threshold, base_threshold

    def get_balance_differences_df(self):
        current_balance = self.get_balance_df()
        starting_balance = self.starting_balance
        balance_differences_df = pd.DataFrame(
            {
                "Exchange": starting_balance["Exchange"],
                "Asset": starting_balance["Asset"],
                "Starting_Available_Balance": starting_balance["Available Balance"],
                "Starting_Balance": starting_balance["Total Balance"],
                "Current_Available_Balance": current_balance["Available Balance"],
                "Current_Balance": current_balance["Total Balance"],
            }
        )
        balance_differences_df["Difference_Balance"] = (
            balance_differences_df["Current_Balance"] - balance_differences_df["Starting_Balance"]
        )
        balance_differences_df["Difference_Available_Balance"] = (
            balance_differences_df["Current_Available_Balance"] - balance_differences_df["Starting_Available_Balance"]
        )
        return balance_differences_df

    def is_balance_below_threshold(self, balance_df, asset, threshold):
        try:
            difference_balance = abs(
                Decimal(balance_df.loc[balance_df["Asset"] == asset, "Difference_Balance"].iloc[0])
            )
            difference_available_balance = abs(
                Decimal(balance_df.loc[balance_df["Asset"] == asset, "Difference_Available_Balance"].iloc[0])
            )
            return difference_balance > threshold or difference_available_balance > threshold
        except (KeyError, IndexError):
            return False

    def check_thresholds(self, balance_df, base_threshold, quote_threshold):
        base_condition = self.is_balance_below_threshold(balance_df, self.base, base_threshold)
        quote_condition = self.is_balance_below_threshold(balance_df, self.quote, quote_threshold)
        return base_condition, quote_condition

    def on_stop(self):
        self.cancel_all_orders()
        notification = "\nNOTIFICATION : Stopping strategy initiated."
        notification += f"\n{self.format_status()}"
        self.logger().notify(notification)
        return super().on_stop()

    def format_status(self) -> str:
        text = super().format_status()
        order_info = (
            f"\nOrder Info"
            f"\nOrder Amount Range: {self.order_lower_amount} - {self.order_upper_amount} {self.base}"
            f"\nDelay Order Time: {self.delay_order_time} seconds + Random Delay: 0 - {self.max_random_delay} seconds"
        )
        return text + f"\n\n{order_info}\n\n{self.create_report()}"

    def format_duration(self, delta: timedelta) -> str:
        days, seconds = delta.days, delta.seconds
        hours, minutes = divmod(seconds, 3600)
        minutes, seconds = divmod(minutes, 60)
        return f"{days} day(s), {hours} hour(s), {minutes} minute(s), and {seconds} second(s)"

    def create_report(self, is_periodic: bool = False) -> str:
        if is_periodic:
            report_type = "Periodic Summary Report"
            traded_volume_quote = self.interval_traded_volume_quote
            traded_volume_base = self.interval_traded_volume_base
            trades_count = self.interval_trades_count
            tight_spread_count = self.interval_tight_spread_count
            report_duration = f"\nThis Report Covers The Last {self.periodic_report_interval} hour(s)"
        else:
            report_type = "Summary Report"
            traded_volume_quote = self.total_traded_volume_quote
            traded_volume_base = self.total_traded_volume_base
            trades_count = self.total_trades_count
            tight_spread_count = self.total_tight_spread_count
            report_duration = ""

        total_running_time = self.format_duration(delta=datetime.now() - self.starting_time)

        report = (
            f"\n{report_type}:"
            f"{report_duration}"
            f"\nTotal Traded Volume In Quote: {traded_volume_quote} {self.quote}"
            f"\nTotal Traded Volume In Base: {traded_volume_base} {self.base}"
            f"\nTotal Trades Count: {trades_count}"
            f"\nTotal Tight Spread Error Count: {tight_spread_count}"
            f"\nTotal Running Time: {total_running_time}"
        )
        return report

    def generate_periodic_summary(self):
        self.logger().notify(self.create_report(is_periodic=True))
        # reset interval data
        self.interval_tight_spread_count = 0
        self.interval_traded_volume_quote = 0
        self.interval_traded_volume_base = 0
        self.interval_trades_count = 0
        # update last report timestamp
        self.last_report_timestamp = self.current_timestamp

    def check_balance_return(self):
        balance = self.get_balance_df()
        if balance.equals(self.starting_balance):
            self.status = "RUNNING"
            notification = "\nNOTIFICATION : Balance has returned to starting balance.\nResuming strategy."
            self.logger().notify(notification)
