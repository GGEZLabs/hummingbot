import logging
from typing import List, Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.coinstore_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class CoinstoreSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m", max_records: int = 150):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"coinstore_{self._trading_pair}"

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

    @property
    def ready(self):
        """
        This property returns a boolean indicating whether the _candles deque has reached its maximum length.
        """
        return len(self._candles) > 5

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(
            url=self.health_check_url, throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT
        )
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair.replace("-", "")

    async def fetch_candles(
        self, start_time: Optional[int] = None, end_time: Optional[int] = None, limit: Optional[int] = None
    ):
        if start_time is None and end_time is None:
            raise ValueError("Either the start time or end time must be specified.")

        if limit is None:
            limit = self.candles_max_result_per_rest_request

        candles_to_fetch = min(self.candles_max_result_per_rest_request, limit)

        if end_time is None:
            fixed_start_time = self._calculate_start_time(start_time)
            fixed_end_time = self._calculate_end_time(start_time + self.interval_in_seconds * candles_to_fetch)
        else:
            fixed_start_time = self._calculate_start_time(end_time - self.interval_in_seconds * candles_to_fetch)
            fixed_end_time = self._calculate_end_time(end_time)

        kwargs = {"start_time": fixed_start_time, "end_time": fixed_end_time, "limit": limit}

        params = self._get_rest_candles_params(fixed_start_time, fixed_end_time, limit=candles_to_fetch)
        headers = self._get_rest_candles_headers()
        rest_assistant = await self._api_factory.get_rest_assistant()

        url = self.candles_url + f"/{self._ex_trading_pair}"
        candles = await rest_assistant.execute_request(
            url=url,
            throttler_limit_id=self._rest_throttler_limit_id,
            params=params,
            data=self._rest_payload(**kwargs),
            headers=headers,
            method=self._rest_method,
        )
        arr = self._parse_rest_candles(candles, end_time)
        return np.array(arr).astype(float)

    def check_candles_sorted_and_equidistant(self, candles: np.ndarray):
        """
        This method checks if the given candles are sorted by timestamp in ascending order and equidistant.
        :param candles: numpy array with the candles
        """
        timestamps = [candle[0] for candle in candles]
        if len(self._candles) <= 1:
            return
        if not np.all(np.diff(timestamps) >= 0):
            self.logger().warning("Candles are not sorted by timestamp in ascending order.")
            self._reset_candles()
            return
        # timestamp_steps = np.unique(np.diff(timestamps))
        # interval_in_seconds = self.get_seconds_from_interval(self.interval)
        # if not np.all(timestamp_steps == interval_in_seconds):
        #     self.logger().warning("Candles are malformed. Restarting...")
        #     self._reset_candles()
        #     return

    def _get_rest_candles_params(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST,
    ) -> dict:
        if self.interval not in CONSTANTS.REST_INTERVALS:
            self.interval = CONSTANTS.DEFAULT_INTERVAL
        params = {"period": CONSTANTS.REST_INTERVALS[self.interval], "size": limit}
        return params

    def _parse_rest_candles(self, data: dict, end_time: Optional[int] = None) -> List[List[float]]:
        candles = data["data"]["item"]
        return [
            [
                self.ensure_timestamp_in_seconds(candle["startTime"]),  # timestamp
                candle["open"],  # open
                candle["high"],  # high
                candle["low"],  # low
                candle["close"],  # close
                candle["volume"],  # volume
                0.0,  # quote_asset_volume
                0.0,  # n_trades
                0.0,  # taker_buy_base_volume
                0.0,  # taker_buy_quote_volume
            ]
            for candle in candles
        ]

    def ws_subscription_payload(self):
        if self.interval not in CONSTANTS.WS_INTERVALS:
            self.interval = CONSTANTS.DEFAULT_INTERVAL
        candle_params = [f"{self._ex_trading_pair.lower()}@kline@{ CONSTANTS.WS_INTERVALS[self.interval]}"]
        payload = {"op": "SUB", "channel": candle_params, "id": 1}

        return payload

    def _parse_websocket_message(self, data: dict):
        if data is None:
            return None

        if data.get("T") == "kline":
            return {
                "timestamp": self.ensure_timestamp_in_seconds(data["startTime"]),
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
                "quote_asset_volume": 0.0,
                "n_trades": 0.0,
                "taker_buy_base_volume": 0.0,
                "taker_buy_quote_volume": 0.0,
            }

        if data.get("T") == "req" and "kline" in data.get("channel", ""):
            return [
                {
                    "timestamp": self.ensure_timestamp_in_seconds(item["startTime"]),
                    "open": item["open"],
                    "high": item["high"],
                    "low": item["low"],
                    "close": item["close"],
                    "volume": item["volume"],
                    "quote_asset_volume": 0.0,
                    "n_trades": 0.0,
                    "taker_buy_base_volume": 0.0,
                    "taker_buy_quote_volume": 0.0,
                }
                for item in data.get("item", [])
            ]

        return None

    async def _process_websocket_messages_task(self, websocket_assistant: WSAssistant):
        # TODO: Isolate ping pong logic
        async for ws_response in websocket_assistant.iter_messages():
            data = ws_response.data
            parsed_message = self._parse_websocket_message(data)
            # parsed messages may be ping or pong messages
            if isinstance(parsed_message, WSJSONRequest):
                await websocket_assistant.send(request=parsed_message)
            elif isinstance(parsed_message, dict):
                candles_row = np.array(
                    [
                        parsed_message["timestamp"],
                        parsed_message["open"],
                        parsed_message["high"],
                        parsed_message["low"],
                        parsed_message["close"],
                        parsed_message["volume"],
                        parsed_message["quote_asset_volume"],
                        parsed_message["n_trades"],
                        parsed_message["taker_buy_base_volume"],
                        parsed_message["taker_buy_quote_volume"],
                    ]
                ).astype(float)
                if len(self._candles) == 0:
                    self._candles.append(candles_row)
                    self._ws_candle_available.set()
                    safe_ensure_future(self.fill_historical_candles())
                else:
                    latest_timestamp = int(self._candles[-1][0])
                    current_timestamp = int(parsed_message["timestamp"])
                    if current_timestamp > latest_timestamp:
                        self._candles.append(candles_row)
                    elif current_timestamp == latest_timestamp:
                        self._candles[-1] = candles_row
            elif isinstance(parsed_message, list):
                # candles_rows = [
                #     np.array(
                #         [
                #             candle_data["timestamp"],
                #             candle_data["open"],
                #             candle_data["high"],
                #             candle_data["low"],
                #             candle_data["close"],
                #             candle_data["volume"],
                #             candle_data["quote_asset_volume"],
                #             candle_data["n_trades"],
                #             candle_data["taker_buy_base_volume"],
                #             candle_data["taker_buy_quote_volume"],
                #         ]
                #     ).astype(float)
                #     for candle_data in parsed_message
                # ]
                ...
