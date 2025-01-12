from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

REST_URL = "https://api.coinstore.com/api"
HEALTH_CHECK_ENDPOINT = "/v2/public/config/spot/symbols"
CANDLES_ENDPOINT = "/v1/market/kline"

WSS_URL = "wss://ws.coinstore.com/s/ws"

INTERVALS = bidict(
    {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "12h": "12h",
        "1d": "1d",
        "1w": "1w",
        "1M": "1M",
    }
)

DEFAULT_INTERVAL = "1h"
WS_INTERVALS = {
    "1m": "min_1",
    "5m": "min_5",
    "15m": "min_15",
    "30m": "min_30",
    "1h": "hour_1",
    "4h": "hour_4",
    "12h": "hour_12",
    "1d": "day_1",
    "1w": "week_1",
    "1M": "mon_1",
}

REST_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
    "4h": "4hour",
    "12h": "12hour",
    "1d": "1day",
    "1w": "1week",
}

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 2000
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ONE_SECOND = 1

RATE_LIMITS = [
    RateLimit(REQUEST_WEIGHT, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(
        CANDLES_ENDPOINT, limit=120, time_interval=3 * ONE_SECOND, linked_limits=[LinkedLimitWeightPair("raw", 1)]
    ),
    RateLimit(
        HEALTH_CHECK_ENDPOINT, limit=120, time_interval=3 * ONE_SECOND, linked_limits=[LinkedLimitWeightPair("raw", 1)]
    ),
]
