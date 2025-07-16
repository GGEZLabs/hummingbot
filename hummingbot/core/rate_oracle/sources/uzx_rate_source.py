from decimal import Decimal
from typing import TYPE_CHECKING, Dict, Optional

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather

if TYPE_CHECKING:
    from hummingbot.connector.exchange.uzx.uzx_exchange import UzxExchange


class UzxRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._uzx_exchange: Optional[UzxExchange] = None  # delayed because of circular reference

    @property
    def name(self) -> str:
        return "uzx"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchanges()
        results = {}
        tasks = [
            self._get_uzx_prices(exchange=self._uzx_exchange),
        ]
        task_results = await safe_gather(*tasks, return_exceptions=True)
        for task_result in task_results:
            if isinstance(task_result, Exception):
                self.logger().error(
                    msg="Unexpected error while retrieving rates from Uzx. Check the log file for more info.",
                    exc_info=task_result,
                )
                break
            else:
                results.update(task_result)
        return results

    def _ensure_exchanges(self):
        if self._uzx_exchange is None:
            self._uzx_exchange = self._build_uzx_connector_with_private_keys(domain="com")

    @staticmethod
    async def _get_uzx_prices(exchange: "UzxExchange", quote_token: str = None) -> Dict[str, Decimal]:
        """
        Fetches uzx prices

        :param exchange: The exchange instance from which to query prices.
        :param quote_token: A quote symbol, if specified only pairs with the quote symbol are included for prices
        :return: A dictionary of trading pairs and prices
        {
            "market": {
                "open": "4.078",
                "close": "4.056",
                "low": "4.002",
                "high": "4.141",
                "turn_over": "1512246.22457",
                "count": 0,
                "vol": "372410.45",
                "change": "-0.019",
                "change_percent": "-0.0046625766871165644171779141104294479"
            },
            "index": {
                "open": "0",
                "close": "0",
                "low": "0",
                "high": "0"
            },
            "tag": {
                "open": "0",
                "close": "0",
                "low": "0",
                "high": "0"
            },
            "funding_rate": "0",
            "pre_funding_rate": "0",
            "symbol": "ATOM-USDT",
            "risk_fund": "0"
        }
        """
        pairs_prices = await exchange.get_all_pairs_prices()
        results = {}
        for pair in pairs_prices:
            try:
                trading_pair = await exchange.trading_pair_associated_to_exchange_symbol(
                    symbol=exchange.get_hbot_trading_pair(pair["symbol"])
                )
            except KeyError:
                continue  # skip pairs that we don't track
            pair_price = pair["market"]["close"]
            if quote_token is not None:
                base, quote = split_hb_trading_pair(trading_pair=trading_pair)
                if quote != quote_token:
                    continue

            results[trading_pair] = Decimal(pair_price)

        return results

    @staticmethod
    def _build_uzx_connector_with_private_keys(domain: str) -> "UzxExchange":
        from hummingbot.client.hummingbot_application import HummingbotApplication
        from hummingbot.connector.exchange.uzx.uzx_exchange import UzxExchange

        app = HummingbotApplication.main_application()
        client_config_map = app.client_config_map
        connector_config = AllConnectorSettings.get_connector_config_keys("uzx")

        return UzxExchange(
            client_config_map=client_config_map,
            uzx_api_key=connector_config.uzx_api_key.get_secret_value(),
            uzx_api_secret=connector_config.uzx_api_secret.get_secret_value(),
            uzx_passphrase=connector_config.uzx_passphrase.get_secret_value(),
            trading_pairs=[],
            trading_required=False,
            domain=domain,
        )
