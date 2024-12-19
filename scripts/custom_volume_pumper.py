from decimal import Decimal
import math
import time
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from random import randint


class CustomVolumePumpr(ScriptStrategyBase):
    # Settings / Inputs
    exchange: str = "coinstore"
    trading_pair: str = "GGEZ1-USDT"
    order_lower_amount = 100  # in base (GGEZ1)
    order_upper_amount = 300
    price_source = PriceType.MidPrice
    last_trade_price = 0
    delay_order_time = 120  # seconds
    last_mid_price_timestamp = time.time()

    markets = {exchange: {trading_pair}}
    status: str = "NOT_INITIALIZED"

    @property
    def connector(self):
        return self.connectors[self.exchange]

    def on_tick(self):
        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        #  cancel all orders active orders
        self.cancel_all_orders()

        # check if last mid price timestamp is less than delay order time
        if time.time() - self.last_mid_price_timestamp < self.delay_order_time:
            return

        # calculate order price
        best_ask_price, best_bid_price, order_price = self.calculate_order_price()

        # check if last trade price has changed
        order_book = self.connector.get_order_book(self.trading_pair)
        last_trade_price_new = order_book.last_trade_price
        if last_trade_price_new != self.last_trade_price:
            # if last trade price has changed, update last trade price and timestamp
            self.last_trade_price = last_trade_price_new
            self.logger().info(f"Last trade price: {self.last_trade_price}")
            self.last_mid_price_timestamp = time.time()
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
            self.last_mid_price_timestamp = time.time()

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
        self.status = "RUNNING"

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
