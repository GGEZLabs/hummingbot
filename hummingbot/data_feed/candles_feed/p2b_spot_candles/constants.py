from bidict import bidict

from hummingbot.core.api_throttler.data_types import RateLimit

# base URL
REST_URL = "https://api.p2pb2b.com"
WSS_URL = "wss://apiws.p2pb2b.com"
# public API endpoints
HEALTH_CHECK_ENDPOINT = "/api/v2/public/markets"
CANDLES_ENDPOINT = "/api/v2/public/market/kline"

INTERVALS = bidict(
    {
        "1m": "1m",
        "1h": "1h",
        "1d": "1d",
    }
)

DEFAULT_INTERVAL = "1h"
INTERVALS_IN_SECONDS = {
    "1m": 60,
    "1h": 3600,
    "1d": 86400,
}


MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 100
RAW_REQUESTS = "RAW_REQUESTS"
ONE_SECOND = 1
MAX_REQUESTS_PER_SECOND = 10

RATE_LIMITS = [
    # pools
    RateLimit(limit_id=RAW_REQUESTS, limit=MAX_REQUESTS_PER_SECOND, time_interval=ONE_SECOND),
    # public endpoints
    RateLimit(
        CANDLES_ENDPOINT,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
    ),
    RateLimit(
        HEALTH_CHECK_ENDPOINT,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
    ),
]
