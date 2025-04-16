from bidict import bidict

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# base URL
REST_URL = "https://api.uzx.com"
WSS_URL = "wss://v2-api.uzx.com/notification/swap/ws"
# public API endpoints
HEALTH_CHECK_ENDPOINT = "/api/v1/swap/symbols"
CANDLES_ENDPOINT = "/notification/swap/{symbol}/tag"

DEFAULT_INTERVAL = "1h"

INTERVALS = bidict(
    {
        "1m": "1min",
        "3m": "3min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "60min",
        "2h": "2hour",
        "4h": "4hour",
        "6h": "6hour",
        "8h": "8hour",
        "12h": "12hour",
        "1d": "1day",
        "3d": "3day",
        "5d": "5day",
        "1w": "1week",
        "1M": "1mon",
    }
)

INTERVALS_IN_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "5d": 432000,
    "1w": 604800,
    "1M": 2592000,
}

MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 300
RAW_REQUESTS = "RAW_REQUESTS"
ONE_SECOND = 1
MAX_REQUESTS_PER_SECOND = 20

RATE_LIMITS = [
    # pools
    RateLimit(limit_id=RAW_REQUESTS, limit=MAX_REQUESTS_PER_SECOND, time_interval=ONE_SECOND * 2),
    # public endpoints
    RateLimit(
        CANDLES_ENDPOINT,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND * 2,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        HEALTH_CHECK_ENDPOINT,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND * 2,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
]
