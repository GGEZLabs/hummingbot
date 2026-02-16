import logging
import math
import time
from typing import List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.p2b_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class P2bSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 100):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"p2b_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT

    @property
    def candles_endpoint(self):
        return CONSTANTS.CANDLES_ENDPOINT

    @property
    def candles_max_result_per_rest_request(self):
        return CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url, throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "_")

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
    ) -> dict:
        params = {
            "market": self._ex_trading_pair,
            "interval": CONSTANTS.INTERVALS[self.interval],
        }
        if limit:
            params["limit"] = limit

        if start_time:
            time_now = int(time.time())
            interval = CONSTANTS.INTERVALS_IN_SECONDS[self.interval]
            num_of_intervals = math.ceil((time_now - start_time) / interval)
            params["offset"] = 0 if limit > num_of_intervals else num_of_intervals - limit
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
         "result": [
            {
                1573472164,  // Open time   0
                "0.021421",  // Open        1
                "0.021407",  // Close       2
                "0.021427",  // Highest     3
                "0.021402",  // Lowest      4
                "1000",      // Volume      5
                "123456.78", // Amount      6
                "ETH_BTC"    // Market name 7
            },
        ]
        """
        return [
            [self.ensure_timestamp_in_seconds(row[0]), row[1], row[3], row[4], row[2], row[5], row[6], 0.0, 0.0, 0.0]
            for row in data["result"]
        ]

    def ws_subscription_payload(self):
        candle_params = [self._ex_trading_pair, CONSTANTS.INTERVALS_IN_SECONDS[self.interval]]
        return {
            "method": "kline.subscribe",
            "params": candle_params,
            "id": 1,
        }

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if data is not None and "params" in data:  # data will be None when the websocket is disconnected
            candles = data["params"][0]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candles[0])
            candles_row_dict["open"] = candles[1]
            candles_row_dict["high"] = candles[3]
            candles_row_dict["low"] = candles[4]
            candles_row_dict["close"] = candles[2]
            candles_row_dict["volume"] = candles[5]
            candles_row_dict["quote_asset_volume"] = candles[6]
            candles_row_dict["n_trades"] = 0.0
            candles_row_dict["taker_buy_base_volume"] = 0.0
            candles_row_dict["taker_buy_quote_volume"] = 0.0
            return candles_row_dict
