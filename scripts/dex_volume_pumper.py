import os
import time
from decimal import Decimal
from enum import Enum
from random import randint, uniform
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.utils.report_management import ReportManagement


class DexVolumePumperStatus(Enum):
    NOT_INITIALIZED = 0
    RUNNING = 1
    STOPPED = 2


s_decimal_0 = Decimal("0")


class DexVolumePumperConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field(
        "pancakeswap_binance-smart-chain_testnet",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Dex where the bot will generate volume",
        ),
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Trading pair"),
    )

    maximum_order_amount: int = Field(
        200,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "maximum order amount in base asset (GGEZ1)",
        ),
    )
    minimum_order_amount: int = Field(
        10,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "minimum order amount in base asset (GGEZ1)",
        ),
    )
    delay_order_time: int = Field(
        120,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Delay time between orders (in seconds)",
        ),
    )
    max_random_delay: int = Field(
        120,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Maximum random delay to be add to delay_order_time (in seconds)",
        ),
    )
    balance_loss_threshold: Decimal = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Balance loss threshold (in quote asset , USDT)",
        ),
    )
    periodic_report_interval: float = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "The interval for periodic report (in hours)",
        ),
    )
    total_inventory_usage: float = Field(
        100,
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "Total inventory usage as percentage (Enter 1 to indicate 1%)",
        ),
    )


class DexVolumePumper(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DexVolumePumperConfig):
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, GatewayBase], config: DexVolumePumperConfig):
        super().__init__(connectors)
        # config data
        self.exchange = config.exchange
        self.trading_pair = config.trading_pair
        self.maximum_order_amount = config.maximum_order_amount
        self.minimum_order_amount = config.minimum_order_amount
        self.delay_order_time = config.delay_order_time
        self.max_random_delay = config.max_random_delay
        self.balance_loss_threshold = config.balance_loss_threshold
        self.periodic_report_interval = config.periodic_report_interval
        self.total_inventory_usage = Decimal(config.total_inventory_usage / 100)

        # strategy data
        self.base, self.quote = split_hb_trading_pair(self.trading_pair)
        self.status = DexVolumePumperStatus.NOT_INITIALIZED.value
        self.on_going_task = False
        self.next_order_side = TradeType.SELL
        self.next_order_timestamp = time.time()
        self.last_order_amount = s_decimal_0

    @property
    def connector(self) -> GatewayBase:
        return self.connectors[self.exchange]

    def init_strategy(self):
        self.logger().info("Initializing strategy...")
        self.dex_market_info = MarketTradingPairTuple(self.connector, self.trading_pair, self.base, self.quote)
        self.starting_balance = self.get_balance_df()
        # report management
        self.report_management = ReportManagement(
            periodic_report_interval=self.periodic_report_interval,
            base=self.base,
            quote=self.quote,
        )
        self.status = DexVolumePumperStatus.RUNNING.value
        self.logger().info("Strategy initialized.")

    def on_tick(self):
        if self.status == DexVolumePumperStatus.NOT_INITIALIZED.value:
            self.init_strategy()

        if self.status == DexVolumePumperStatus.STOPPED.value:
            pass
            return

        if (
            self.periodic_report_interval > 0
            and self.current_timestamp - self.report_management.last_report_timestamp
            >= self.report_management.report_frequency
        ):
            report = self.report_management.generate_periodic_summary()
            self.logger().notify(report)

        if not self.on_going_task and self.current_timestamp >= self.next_order_timestamp:
            self.on_going_task = True
            # wrap async task in safe_ensure_future
            safe_ensure_future(self.pump_volume_task())

    async def pump_volume_task(self):
        self.on_going_task = True
        mid_price = round(Decimal(0.0873), 6)
        # mid_price = await self.connector.get_quote_price(
        #         trading_pair=self.trading_pair,
        #         is_buy=self.next_order_side == TradeType.BUY,
        #         amount=Decimal(self.minimum_order_amount),
        #     )
        self.logger().info(f"Mid price for {self.trading_pair} is {mid_price} " f"for {self.next_order_side} order.")
        if mid_price is None:
            self.on_going_task = False
            return

        order_amount = self.generate_order_amount(mid_price)  # in base (GGEZ1)

        order_proposal = self.generate_order_candidate(mid_price, order_amount)
        self.place_order(order_proposal)
        self.on_going_task = False
        self.next_order_timestamp = self.current_timestamp + self.delay_order_time + randint(0, self.max_random_delay)
        self.next_order_side = TradeType.SELL if self.next_order_side == TradeType.BUY else TradeType.BUY
        self.last_order_amount = order_proposal.amount
        self.report_management.add_new_order(order_proposal.amount, order_proposal.price)

    def generate_order_amount(self, mid_price: Decimal) -> Decimal:
        # keep the LP balanced between base and quote
        if self.last_order_amount == s_decimal_0:
            order_amount = round(
                Decimal(uniform(self.minimum_order_amount, self.maximum_order_amount)), 2
            )  # in base (GGEZ1)
        else:
            max_rondomized_amount = float(self.last_order_amount) * 0.2  # 20% of the last order amount
            order_amount = self.last_order_amount + round(
                Decimal(uniform(-max_rondomized_amount, max_rondomized_amount)), 2
            )  # in base (GGEZ1)

        current_balance = self.get_balance_df()
        base_currency_balance = Decimal(
            current_balance.loc[current_balance["Asset"] == self.base, "Available Balance"].iloc[0]
        )
        quote_currency_balance = Decimal(
            current_balance.loc[current_balance["Asset"] == self.quote, "Available Balance"].iloc[0]
        )

        # keep the order amount within the inventory
        if self.next_order_side == TradeType.BUY:
            order_amount = min(
                (quote_currency_balance / mid_price) * self.total_inventory_usage,
                order_amount,
            )
        else:
            order_amount = min(base_currency_balance * self.total_inventory_usage, order_amount)

        return round(order_amount, 2)

    def place_order(self, order: OrderCandidate):
        order_id = self.connector.place_order(
            is_buy=order.order_side == TradeType.BUY,
            trading_pair=order.trading_pair,
            amount=order.amount,
            price=order.price,
        )
        self.logger().info(
            f"Trade executed with order ID: {order_id} with {order.trading_pair} and order side {order.order_side} "
        )

    def generate_order_candidate(self, order_price, order_amount):
        is_buy = self.next_order_side == TradeType.BUY
        trading_pair = f"{self.base}-{self.quote}" if is_buy else f"{self.quote}-{self.base}"
        if is_buy:
            order_price = round(Decimal(1) / Decimal(order_price), 6)

        self.logger().info(
            f"trading_pair : {trading_pair} base : {self.base} quote :{self.quote} next_order_side :{self.next_order_side}"
        )
        buy_order_proposal = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=self.next_order_side,
            amount=Decimal(order_amount),
            price=Decimal(order_price),
        )

        return buy_order_proposal
