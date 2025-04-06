import math
from copy import deepcopy
from decimal import Decimal
from random import randint

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
        self._current_price_movement = "up"

    @property
    def tick_size(self):
        best_bid_price = self.connector.get_mid_price(self.trading_pair)
        return self.connector.get_order_price_quantum(self.trading_pair, best_bid_price)

    def adjust_order_amount_for_balance(
        self, order_price: Decimal, order_amount: Decimal, balance: pd.DataFrame
    ) -> Decimal:
        new_order_amount = deepcopy(order_amount)
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
            new_order_amount = math.floor(quote_balance / order_price)

        if base_balance < order_amount:
            new_order_amount = base_balance

        return new_order_amount

    def convert_from_basis_point(self, basis_point):
        return basis_point / 10000

    def round_price_to_tick_size(self, price: Decimal) -> Decimal:
        return math.floor(price / self.tick_size) * self.tick_size

    def distance_from_last_trade_price(
        self, ask_price: Decimal, bid_price: Decimal, last_trade_price: Decimal
    ) -> Decimal:
        range = ask_price - bid_price
        bid_distance_from_last_trade_price = (last_trade_price - bid_price) / range
        return bid_distance_from_last_trade_price * Decimal(100)

    def calculate_order_price(self) -> Decimal:
        best_ask_price = self.connector.get_price(self.trading_pair, True)
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        mid_price = self.connector.get_mid_price(self.trading_pair)
        last_trade_price = Decimal(self.connector.get_order_book(self.trading_pair).last_trade_price)
        if best_bid_price > last_trade_price or best_ask_price < last_trade_price:
            last_trade_price = mid_price

        bid_distance_percentage = self.distance_from_last_trade_price(best_ask_price, best_bid_price, last_trade_price)

        if bid_distance_percentage < 5:
            self._current_price_movement = "up"
        elif bid_distance_percentage > 95:
            self._current_price_movement = "down"

        order_price = Decimal(
            last_trade_price
            + self.tick_size * Decimal(randint(-2, 5)) * (1 if self._current_price_movement == "up" else -1)
        )

        if order_price < best_bid_price:
            order_price = best_bid_price + self.tick_size

        if order_price > best_ask_price:
            order_price = best_ask_price - self.tick_size

        # adjust order price with random value
        # order_price = Decimal(uniform(float(order_price), float(best_ask_price)))

        # round to tick size
        order_price = self.round_price_to_tick_size(order_price)
        return best_ask_price, best_bid_price, order_price
