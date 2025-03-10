import time
from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from scripts.utils.cex_to_dex_lp_price_config import CexToDexLpPriceConfig

s_decimal_0 = Decimal("0")


class CexToDexLpPrice(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: CexToDexLpPriceConfig):
        cls.markets = {config.cex_exchange: {config.cex_trading_pair}, config.dex_exchange: {config.dex_trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: CexToDexLpPriceConfig):
        super().__init__(connectors)
        # config data
        self.cex_exchange = config.cex_exchange
        self.cex_trading_pair = config.cex_trading_pair
        self.dex_exchange = config.dex_exchange
        self.dex_trading_pair = config.dex_trading_pair
        self.liquidity_amount = config.liquidity_amount
        self.mid_price_threshold = config.mid_price_threshold
        self.check_price_interval = config.check_price_interval
        self.upper_lower_price_spread = config.upper_lower_price_spread / 100
        self.fee_tier = config.fee_tier
        # strategy data
        self.price_source = PriceType.MidPrice
        self.last_check_time = 0

        self.status = "NOT_INITIALIZED"

    @property
    def cex_connector(self) -> ConnectorBase:
        return self.connectors[self.cex_exchange]

    @property
    def dex_connector(self) -> ConnectorBase:
        return self.connectors[self.dex_exchange]

    @property
    def active_positions(self):
        return [
            pos
            for pos in self.dex_market_info.market.amm_lp_orders
            if pos.is_nft and pos.trading_pair == self.dex_trading_pair
        ]

    @property
    def active_orders(self):
        return [
            pos
            for pos in self.dex_market_info.market.amm_lp_orders
            if not pos.is_nft and pos.trading_pair == self.dex_trading_pair
        ]

    def init_strategy(self):
        dex_base, dex_quote = self.dex_trading_pair.split("-")

        self.dex_market_info = MarketTradingPairTuple(self.dex_connector, self.dex_trading_pair, dex_base, dex_quote)

        self.status = "INITIALIZED"

    def on_tick(self):

        if self.status == "NOT_INITIALIZED":
            self.init_strategy()

        if not self.dex_market_info.market.ready:
            self.logger().info(f"dex_market_info not ready {self.dex_exchange}")

        if time.time() - self.last_check_time < self.check_price_interval:
            return

        if len(self.active_orders) != 0:
            return

        if len(self.active_positions) > 0:
            if self.are_positions_outside_mid_price_range():
                position_proposal = self.create_positions_proposal()
                self.add_position(position_proposal)
                # # remove old positions
                # self.remove_position(self.active_positions[0])
                # return

            self.last_check_time = time.time()
            return

        if len(self.active_positions) == 0:
            position_proposal = self.create_positions_proposal()
            self.add_position(position_proposal)

    def add_position(self, position_proposal):
        """
        Add a new position to the AMM
        """
        self.logger().info(
            f"Creating new position over {position_proposal['lower_price']} to {position_proposal['upper_price']} price range.",
        )
        self.logger().info(
            f"Creating new position over {position_proposal['lower_price']} to {position_proposal['upper_price']} price range."
        )

        self.dex_market_info.market.add_liquidity(
            self.dex_trading_pair,
            position_proposal["base_amount"],
            position_proposal["quote_amount"],
            position_proposal["lower_price"],
            position_proposal["upper_price"],
            self.fee_tier,
        )

    def remove_position(self, position):
        """
        Remove a position from the AMM
        """
        self.logger().info(
            f"Removing position over {position.lower_price} to {position.upper_price} price range.",
        )
        self.logger().info(f"Removing position with token id {position.token_id}")
        self.dex_market_info.market.remove_liquidity(position.trading_pair, position.token_id)

    def create_positions_proposal(self):
        """
        Creates a list of position proposals based on the provided order book DataFrame.
        """
        cex_mid_price = self.cex_connector.get_mid_price(self.cex_trading_pair)
        lower_price, upper_price = self.propose_position_boundary_prices(cex_mid_price)

        quote_amount = self.liquidity_amount
        base_amount = quote_amount / cex_mid_price

        return {
            "base_amount": Decimal(base_amount),
            "quote_amount": Decimal(quote_amount),
            "lower_price": Decimal(round(lower_price, 5)),
            "upper_price": Decimal(round(upper_price, 5)),
        }

    def propose_position_boundary_prices(self, cex_mid_price: Decimal):
        """
        We use this to create proposal for new range positions
        :return : lower_price, upper_price
        """
        half_spread = self.upper_lower_price_spread / Decimal("2")
        lower_price = cex_mid_price * (Decimal("1") - half_spread)
        upper_price = cex_mid_price * (Decimal("1") + half_spread)
        lower_price = max(s_decimal_0, lower_price)
        return lower_price, upper_price

    def are_positions_outside_mid_price_range(self):
        """
        Check if the active position is out of range of the mid price threshold
        :return: bool
        """

        cex_mid_price = self.cex_connector.get_mid_price(self.cex_trading_pair)
        for position in self.active_positions:
            upper_price_diff = self.percentage_diff(position.upper_price, cex_mid_price)
            lower_price_diff = self.percentage_diff(position.lower_price, cex_mid_price)
            if lower_price_diff > self.mid_price_threshold or upper_price_diff > self.mid_price_threshold:
                return True
        return False

    def percentage_diff(self, price1, price2):
        return abs(price1 - price2) / price1 * Decimal("100")
