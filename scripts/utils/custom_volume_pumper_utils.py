import math
from decimal import Decimal
from random import uniform

import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase


class CustomVolumePumperUtils:
    def __init__(
        self,
        connector: ConnectorBase,
        exchange: str,
        trading_pair: str,
        base: str,
        quote: str,
    ):
        self.connector = connector
        self.exchange = exchange
        self.trading_pair = trading_pair
        self.base = base
        self.quote = quote
        pass

    @property
    def tick_size(self):
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        return self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)

    def adjust_order_amount_for_balance(
        self, order_price: Decimal, order_amount: Decimal, balance: pd.DataFrame
    ) -> Decimal:
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

    def convert_from_basis_point(self, basis_point):
        return basis_point / 10000

    def round_price_to_tick_size(self, price: Decimal) -> Decimal:
        return math.floor(price / self.tick_size) * self.tick_size

    def calculate_order_price(self) -> Decimal:
        best_ask_price = self.connector.get_price(self.trading_pair, True)
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        mid_price = self.connector.get_mid_price(self.trading_pair)
        order_price = Decimal((best_ask_price + mid_price) / 2)
        # adjust order price with random value
        order_price = Decimal(uniform(float(order_price), float(best_ask_price)))
        # round to tick size
        order_price = self.round_price_to_tick_size(order_price)
        return best_ask_price, best_bid_price, order_price
