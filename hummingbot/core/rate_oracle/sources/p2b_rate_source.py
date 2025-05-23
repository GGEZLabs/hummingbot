from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather

if TYPE_CHECKING:
    from hummingbot.connector.exchange.p2b.p2b_exchange import P2bExchange


class P2bRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._p2b_exchange: Optional[P2bExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "p2b"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchanges()
        results = {}
        tasks = [
            self._get_p2b_prices(exchange=self._p2b_exchange),
        ]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(
                    msg="Unexpected error while retrieving rates from P2b. Check the log file for more info.",
                    exc_info=task_result,
                )
                break
            else:
                results.update(task_result)
        return results

    def _ensure_exchanges(self):
        if self._p2b_exchange is None:
            self._p2b_exchange = self._build_p2b_connector_without_private_keys(domain="com")

    @staticmethod
    async def _get_p2b_prices(exchange: "P2bExchange", quote_token: str = None) -> Dict[str, Decimal]:
        """
        Fetches p2b prices

        :param exchange: The exchange instance from which to query prices.
        :param quote_token: A quote symbol, if specified only pairs with the quote symbol are included for prices
        :return: A dictionary of trading pairs and prices
        """
        pairs_prices = await exchange.get_all_pairs_prices()
        results = {}
        for exchange_symbol in pairs_prices:
            try:
                trading_pair = await exchange.trading_pair_associated_to_exchange_symbol(
                    symbol=exchange.get_hbot_trading_pair(exchange_symbol)
                )
            except KeyError:
                continue  # skip pairs that we don't track
            pair_price = pairs_prices[exchange_symbol]["ticker"]
            if quote_token is not None:
                base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                if quote != quote_token:
                    continue
            bid_price = pair_price.get("bid")
            ask_price = pair_price.get("ask")
            if bid_price is not None and ask_price is not None and 0 < Decimal(bid_price) <= Decimal(ask_price):
                results[trading_pair] = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")

        return results

    @staticmethod
    def _build_p2b_connector_without_private_keys(domain: str) -> "P2bExchange":
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.p2b.p2b_exchange import P2bExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map

        return P2bExchange(
            client_config_map=client_config_map,
            p2b_api_key="",
            p2b_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=domain,
        )
