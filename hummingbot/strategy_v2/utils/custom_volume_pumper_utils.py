import functools
import math
import random
from copy import deepcopy
from decimal import Decimal
from random import randint, uniform
from typing import Any, List

import numpy as np
import pandas as pd

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate


class CustomVolumePumperUtils:
    def __init__(
        self,
        connector: ConnectorBase,
        trading_pair: str,
        base: str = None,
        quote: str = None,
    ):
        self.connector = connector
        self.trading_pair = trading_pair
        self.base = base if base else trading_pair.split("-")[0]
        self.quote = quote if quote else trading_pair.split("-")[1]
        self._current_price_movement = "up"

    @functools.cached_property
    def price_tick_size(self):
        return self.connector.get_order_price_quantum(self.trading_pair, Decimal("0"))

    @functools.cached_property
    def amount_tick_size(self):
        return self.connector.get_order_size_quantum(self.trading_pair, Decimal("0"))

    @staticmethod
    def percent_distance_from_bid(ask: Decimal, bid: Decimal, price: Decimal) -> Decimal:
        price_range = ask - bid
        if price_range == 0:
            return Decimal(0)
        distance_from_bid = (price - bid) / price_range
        return distance_from_bid * Decimal(100)

    @staticmethod
    def cube_number(value):
        return value**3

    @staticmethod
    def rescale_value(value, from_min, from_max, to_min, to_max):
        return to_min + ((value - from_min) / (from_max - from_min)) * (to_max - to_min)

    @staticmethod
    def get_spread(bid_price: float, ask_price: float) -> float:
        return (ask_price - bid_price) / ((ask_price + bid_price) / 2) * 100

    @staticmethod
    def get_random_decimal(num1: Decimal, num2: Decimal) -> Decimal:
        return Decimal(str(uniform(float(num1), float(num2))))

    @staticmethod
    def compare_numbers(num1: any, operator: str, num2: any) -> bool:
        if operator == "==":
            return Decimal(str(num1)) == Decimal(str(num2))
        elif operator == ">":
            return Decimal(str(num1)) > Decimal(str(num2))
        elif operator == "<":
            return Decimal(str(num1)) < Decimal(str(num2))
        elif operator == ">=":
            return Decimal(str(num1)) >= Decimal(str(num2))
        elif operator == "<=":
            return Decimal(str(num1)) <= Decimal(str(num2))

    def adjust_order_amount_for_balance(
        self, order_price: Decimal, order_amount: Decimal, balance: pd.DataFrame, exchange: str, order_side: TradeType
    ) -> Decimal:
        new_order_amount = deepcopy(order_amount)

        if order_side == TradeType.BUY:
            quote_balance = Decimal(
                balance.loc[
                    (balance["Exchange"] == exchange) & (balance["Asset"] == self.quote), "Available Balance"
                ].iloc[0]
            )
            if quote_balance < order_amount * order_price:
                new_order_amount = math.floor(quote_balance / order_price)

        else:
            base_balance = Decimal(
                balance.loc[
                    (balance["Exchange"] == exchange) & (balance["Asset"] == self.base), "Available Balance"
                ].iloc[0]
            )
            if base_balance < order_amount:
                new_order_amount = base_balance

        return new_order_amount

    def convert_from_basis_point(self, basis_point):
        return basis_point / 10000

    def calculate_order_price(self) -> Decimal:
        best_ask_price = self.connector.get_price(self.trading_pair, True)
        best_bid_price = self.connector.get_price(self.trading_pair, False)
        mid_price = self.connector.get_mid_price(self.trading_pair)
        last_trade_price = Decimal(self.connector.get_order_book(self.trading_pair).last_trade_price)
        if best_bid_price > last_trade_price or best_ask_price < last_trade_price:
            last_trade_price = mid_price

        self._decide_price_movement(best_ask_price, best_bid_price, last_trade_price)

        order_price = Decimal(
            last_trade_price
            + self.price_tick_size * Decimal(randint(0, 5)) * (1 if self._current_price_movement == "up" else -1)
        )

        if order_price < best_bid_price:
            order_price = best_bid_price + self.price_tick_size

        if order_price > best_ask_price:
            order_price = best_ask_price - self.price_tick_size

        # round to tick size
        order_price = self.round_price_to_tick_size(order_price)
        return best_ask_price, best_bid_price, order_price

    def _decide_price_movement(self, best_ask_price: Decimal, best_bid_price: Decimal, last_trade_price: Decimal):
        bid_distance_percentage = self.percent_distance_from_bid(best_ask_price, best_bid_price, last_trade_price)

        if self._current_price_movement == "down":
            # the less the bid_distance_percentage is the more likely to flip current_price_movement to up
            flip_percentage = (1 - bid_distance_percentage / 100) ** 3
        else:
            # the more the bid_distance_percentage is the more likely to flip current_price_movement to up
            flip_percentage = (bid_distance_percentage / 100) ** 3

        if random.uniform(0, 1) < flip_percentage:
            self._current_price_movement = "up" if self._current_price_movement == "down" else "down"

    def generate_order_candidate(self, price: Decimal | float, amount: Decimal | float, is_buy: bool) -> OrderCandidate:
        return OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY if is_buy else TradeType.SELL,
            amount=Decimal(amount),
            price=Decimal(price),
        )

    def get_balance_df(self) -> pd.DataFrame:
        """
        Returns a data frame for all asset balances for displaying purpose.
        """
        columns: List[str] = ["Exchange", "Asset", "Total Balance", "Available Balance"]
        data: List[Any] = []
        for asset in [self.base, self.quote]:
            data.append(
                [
                    self.connector.display_name,
                    asset,
                    float(self.connector.get_balance(asset)),
                    float(self.connector.get_available_balance(asset)),
                ]
            )
        df = pd.DataFrame(data=data, columns=columns).replace(np.nan, "", regex=True)
        df.sort_values(by=["Exchange", "Asset"], inplace=True)
        return df

    def get_available_balance(self, balance_df: pd.DataFrame, is_buy: bool) -> float:
        """Extract available balance for the appropriate asset."""
        asset = self.quote if is_buy else self.base
        asset_row = balance_df[balance_df["Asset"] == asset]
        return asset_row["Available Balance"].iloc[0] if not asset_row.empty else 0

    def _round_number_to_tick_size(self, price: Decimal, tick_size: Decimal) -> Decimal:
        return math.floor(price / tick_size) * tick_size

    def round_price_to_tick_size(self, price: Decimal) -> Decimal:
        return self._round_number_to_tick_size(price, self.price_tick_size)

    def round_amount_to_tick_size(self, amount: Decimal) -> Decimal:
        return self._round_number_to_tick_size(amount, self.amount_tick_size)
