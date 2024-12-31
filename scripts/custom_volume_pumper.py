import math
import os
import time
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
            prompt_on_new=True, prompt=lambda mi: "Lower value for order amount (in base asset)"
        ),
    )
    order_upper_amount: int = Field(
        2000,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Upper value for order amount (in base asset)"
        ),
    )
    delay_order_time: int = Field(
        120, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Delay time between orders (in seconds)")
    )
    balance_loss_threshold: Decimal = Field(
        0, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Balance loss threshold (in quote asset)")
    )
    minimum_ask_bid_spread: Decimal = Field(
        1,
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "minimum ask bid spread (basis points)"),
    )


# TODO minimum_ask_bid_spread change it to be in basis points                                   DONE
# TODO add stop trading parameter to stop all trades whe reaching the  balance_loss_threshold   DONE
# TODO check order book diff function in connector
# TODO Add random order delay time delay_order_time + randint(0, 120)                           DONE


class CustomVolumePumper(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: CustomVolumePumperConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CustomVolumePumperConfig):
        super().__init__(connectors)
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.order_lower_amount = config.order_lower_amount
        self.order_upper_amount = config.order_upper_amount
        self.delay_order_time = config.delay_order_time
        self.balance_loss_threshold = config.balance_loss_threshold
        self.minimum_ask_bid_spread = config.minimum_ask_bid_spread
        self.price_source = PriceType.MidPrice
        self.last_mid_price_timestamp = time.time()
        self.random_delay = 0
        self.status = "NOT_INITIALIZED"

    @property
    def connector(self):
        return self.connectors[self.exchange]

    def on_tick(self):
        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        if self.status == "STOPPED":
            return

        #  cancel all orders active orders
        self.cancel_all_orders()

        # risk management
        self.stop_loss_when_balance_below_threshold()

        # check if last mid price timestamp is less than delay order time
        if time.time() - self.last_mid_price_timestamp < self.delay_order_time + self.random_delay:
            return

        # calculate order price
        best_ask_price, best_bid_price, order_price = self.calculate_order_price()

        # check if spread is too low
        bid_ask_spread = best_ask_price - best_bid_price
        if bid_ask_spread < self.covert_from_basis_point(self.minimum_ask_bid_spread):
            self.logger().notify(f"Spread too low: {bid_ask_spread}")
            self.start_orders_delay()
            return

        # check if last trade price has changed
        order_book = self.connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price
        if last_trade_price_new != self.last_trade_price:
            # if last trade price has changed, update last trade price and timestamp
            self.last_trade_price = last_trade_price_new
            self.logger().info(f"Last trade price: {self.last_trade_price}")
            self.start_orders_delay()
            return

        # TODO get last trade time

        # check if order price is within spread
        if order_price < best_ask_price and order_price > best_bid_price:
            # generate random order amount
            order_amount = randint(self.order_lower_amount, self.order_upper_amount)  # in base (GGEZ1)

            # check if we have enough balance to place order
            order_amount = self.adjust_order_amount_for_balance(order_price, order_amount)

            # create order proposals and place them
            # TODO adjust proposal to budget
            sell_order_proposal = self.generate_order_candidate(order_price, order_amount, False)
            self.place_order(self.exchange, sell_order_proposal)

            buy_order_proposal = self.generate_order_candidate(order_price, order_amount, True)
            self.place_order(self.exchange, buy_order_proposal)

        # update last mid price timestamp
        self.start_orders_delay()

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

    def covert_from_basis_point(self, basis_point):
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
        return best_ask_price, best_bid_price, order_price

    def adjust_proposal_to_budget(self, proposal: OrderCandidate) -> OrderCandidate:
        proposal_adjusted = self.connector.budget_checker.adjust_candidate(proposal, all_or_none=True)
        return proposal_adjusted

    def cancel_all_orders(self):
        active_orders = self.get_active_orders(connector_name=self.exchange)
        for order in active_orders:
            # time_now = time.time()
            # cancel_when = (order.creation_timestamp * 1e-6) + 5
            # if cancel_when < time_now:
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def start_orders_delay(self):
        self.random_delay = randint(0, 120)
        self.last_mid_price_timestamp = time.time()

    def stop_loss_when_balance_below_threshold(self):
        quote_threshold, base_threshold = self.calculate_quote_base_balance_threshold()

        balance_differences_df = self.get_balance_differences_df()

        base_condition, quote_condition = self.check_thresholds(balance_differences_df, base_threshold, quote_threshold)

        if base_condition or quote_condition:
            notification = "\nWARNING : Balance below threshold."
            if base_condition:
                base_balance = balance_differences_df.loc[
                    balance_differences_df["Asset"] == self.base, "Current_Balance"
                ].iloc[0]
                notification += "\nBase Asset getting below threshold"
                notification += f"\nCurrent Base Balance: {str(base_balance)}"
            if quote_condition:
                quote_balance = balance_differences_df.loc[
                    balance_differences_df["Asset"] == self.quote, "Current_Balance"
                ].iloc[0]
                notification += "\nQuote Asset getting below threshold"
                notification += f"\nCurrent Quote Balance: {str(quote_balance)}"

            self.logger().notify(notification)
            self.cancel_all_orders()
            self.logger().notify("\nNotification : Stopping strategy initiated.\nCanceling all orders")
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
        difference_balance = Decimal(abs(balance_df.loc[balance_df["Asset"] == asset, "Difference_Balance"].iloc[0]))
        difference_available_balance = Decimal(
            abs(balance_df.loc[balance_df["Asset"] == asset, "Difference_Available_Balance"].iloc[0])
        )
        return difference_balance > threshold or difference_available_balance > threshold

    def check_thresholds(self, balance_df, base_threshold, quote_threshold):
        base_condition = self.is_balance_below_threshold(balance_df, self.base, base_threshold)
        quote_condition = self.is_balance_below_threshold(balance_df, self.quote, quote_threshold)
        return base_condition, quote_condition

    def on_stop(self):
        self.cancel_all_orders()
        self.logger().notify("Notification : Stopping strategy initiated.\nCanceling all orders")
        return super().on_stop()
