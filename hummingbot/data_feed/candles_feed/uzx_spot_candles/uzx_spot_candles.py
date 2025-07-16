import logging
from typing import List, Optional

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.uzx_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class UzxSpotCandles(CandlesBase):
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
        return f"uzx_{self._trading_pair}"

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
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT.format(symbol=self._ex_trading_pair)

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
        return trading_pair.replace("-", "")

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
    ) -> dict:

        params = {
            "interval": CONSTANTS.INTERVALS[self.interval],
            "start": int(start_time),
            "end": int(end_time),
        }

        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        """
         {
            "code": 200,
            "data": [
                {
                    "close": 1667.78,
                    "high": 1667.78,
                    "id": 1744640760,
                    "low": 1664.93,
                    "open": 1666.14
                }],
            "interval": "1min",
            "msg": "success",
            "symbol": "ETHUSDT",
            "ts": 1744658729117
        }
        """
        return [
            [
                self.ensure_timestamp_in_seconds(row["id"]),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                0,
                0,
                0.0,
                0.0,
                0.0,
            ]
            for row in data["data"]
        ]

    def ws_subscription_payload(self):
        return {
            "event": "sub",
            "params": {
                "symbol": self._ex_trading_pair,
                "biz": "swap",
                "type": "swap.candles",
                "interval": CONSTANTS.INTERVALS[self.interval],
            },
            "zip": False,
        }

    def _parse_websocket_message(self, data: dict):
        """
        {
            "type": "swap.market.candles",
            "product_name": "BTCUSDT",
            "interval": "5min",
            "data": {
                "id": 1744696500,
                "seq_id": 68806979,
                "open": "85593.1",
                "close": "85593.1",
                "high": "85593.1",
                "low": "85593.1",
                "turn_over": "0",
                "vol": "0",
                "count": 0
            },
            "id": 1744696500,
            "seq_id": 68806979
        }
        """
        candles_row_dict = {}
        if data is not None and "data" in data:  # data will be None when the websocket is disconnected
            candles = data["data"]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candles["id"])
            candles_row_dict["open"] = candles["open"]
            candles_row_dict["high"] = candles["high"]
            candles_row_dict["low"] = candles["low"]
            candles_row_dict["close"] = candles["close"]
            candles_row_dict["volume"] = candles["vol"]
            candles_row_dict["quote_asset_volume"] = candles["turn_over"]
            candles_row_dict["n_trades"] = candles["count"]
            candles_row_dict["taker_buy_base_volume"] = 0.0
            candles_row_dict["taker_buy_quote_volume"] = 0.0
            return candles_row_dict
        elif data is not None and "ping" in data:
            return WSJSONRequest(payload={"pong": int(self._time() * 1000)})
        else:
            return None
