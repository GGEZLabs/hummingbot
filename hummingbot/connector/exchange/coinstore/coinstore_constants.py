from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "Coinstore"

MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""

# API RESPONSE CODE
API_SUCCESS_CODE = 0
ORDER_NOT_EXIST_ERROR_CODE = 4003

# Base URL
REST_URL = "https://api.coinstore.com/api"
WSS_URL = "wss://ws.coinstore.com/s/ws"
DEFAULT_DOMAIN = "com"

# Public API endpoints
REST_CANCEL_BATCH_ORDERS = "/trade/order/cancelBatch"
REST_CANCEL_ORDER = "/trade/order/cancel"
REST_CREATE_ORDER = "/trade/order/place"
REST_DEPTH = "/v1/market/depth"
REST_NEW_ORDER = "/trade/order/active"
ACCOUNT_MATCHES_TRADE = "/trade/match/accountMatches"
REST_ORDER_INFO = "/v2/trade/order/orderInfo"


TICKER_PRICE_PATH_URL = "/v1/ticker/price"
TICKER_BOOK_PATH_URL = "/v1/market/tickers"  # ticker book latest traded price
MY_TRADES_PATH_URL = "/trade/match/accountMatches"
SNAPSHOT_PATH_URL = REST_DEPTH  # order book
ORDER_INFO_PATH_URL = REST_ORDER_INFO
ACCOUNTS_PATH_URL = "/spot/accountList"
EXCHANGE_INFO_PATH_URL = "/v2/public/config/spot/symbols"
# SNAPSHOT_PATH_URL

# METHOD
GET = "GET"
POST = "POST"
DELETE = "DELETE"

# Websocket event types
DEPTH_EVENT_TYPE = "depth"
TRADE_EVENT_TYPE = "trade"
DIFF_EVENT_TYPE = "depth"

TAKER_SIDE_BUY = "BUY"
TAKER_SIDE_SELL = "SELL"
# http header
CONTENT_TYPE = "Content-Type"
APPLICATION_FORM = "application/x-www-form-urlencoded"

ACEEPT = "Accept"
COOKIE = "Cookie"
LOCALE = "Locale="

RAW_REQUESTS = "RAW_REQUESTS"
REQUEST_WEIGHT = "REQUEST_WEIGHT"
WS_SUBSCRIBE = "WSSubscribe"
WS_HEARTBEAT_TIME_INTERVAL = 30

ONE_SECOND = 1


RATE_LIMITS = [
    RateLimit(limit_id=REQUEST_WEIGHT, limit=120, time_interval=60 * ONE_SECOND),
    RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=MY_TRADES_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=ORDER_INFO_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=REST_CREATE_ORDER, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=TICKER_PRICE_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=ACCOUNT_MATCHES_TRADE, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=REST_CANCEL_ORDER, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=REST_CANCEL_BATCH_ORDERS, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=WS_SUBSCRIBE, limit=120, time_interval=3 * ONE_SECOND),
    RateLimit(limit_id=RAW_REQUESTS, limit=120, time_interval=5 * 60 * ONE_SECOND),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=120,
        time_interval=60 * ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
            LinkedLimitWeightPair(RAW_REQUESTS, 1),
        ],
    ),
    RateLimit(
        limit_id=RAW_REQUESTS,
        limit=120,
        time_interval=3 * ONE_SECOND,
        linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2), LinkedLimitWeightPair(RAW_REQUESTS, 1)],
        weight=1,
    ),
]

# Order States
ORDER_STATE = {
    "REJECTED": OrderState.FAILED,
    "SUBMITTING": OrderState.PENDING_CREATE,
    "SUBMITTED": OrderState.OPEN,
    "PARTIAL_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELING": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "EXPIRED": OrderState.FAILED,
    "STOPPED": OrderState.FAILED,
    "FILLED": OrderState.FILLED,
}

# Order Types
COINSTORE_ORDER_TYPE = {
    OrderType.LIMIT: "LIMIT",
    OrderType.LIMIT_MAKER: "LIMIT",
    OrderType.MARKET: "MARKET",
}
