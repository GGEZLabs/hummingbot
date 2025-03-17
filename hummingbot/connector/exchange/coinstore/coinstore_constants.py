from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "Coinstore"

MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""

# API RESPONSE CODE
API_SUCCESS_CODE = 0
ORDER_NOT_EXIST_ERROR_CODE = 4003
UNKNOWN_ORDER_ERROR_CODE = 3103

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

SAME_IP_REQUESTS_ID = "SAME_IP_REQUESTS"
SAME_USER_REQUESTS_ID = "SAME_USER_REQUESTS"

SAME_IP_REQUEST_LIMIT = 300
SAME_USER_REQUEST_LIMIT = 120

WS_SUBSCRIBE = "WSSubscribe"
WS_HEARTBEAT_TIME_INTERVAL = 30

ONE_SECOND = 1
THREE_SECONDS = 3
TIME_INTERVAL = 2

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=SAME_IP_REQUESTS_ID, limit=SAME_IP_REQUEST_LIMIT, time_interval=THREE_SECONDS),
    RateLimit(limit_id=SAME_USER_REQUESTS_ID, limit=SAME_USER_REQUEST_LIMIT, time_interval=THREE_SECONDS),
    # Weighted Limits
    # Public Endpoints
    RateLimit(
        limit_id=ORDER_INFO_PATH_URL,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=TICKER_PRICE_PATH_URL,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=TICKER_BOOK_PATH_URL,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=EXCHANGE_INFO_PATH_URL,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=WS_SUBSCRIBE,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=SNAPSHOT_PATH_URL,
        limit=SAME_IP_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
        ],
    ),
    # Private Endpoints
    RateLimit(
        limit_id=ACCOUNTS_PATH_URL,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=MY_TRADES_PATH_URL,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=REST_CREATE_ORDER,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=ACCOUNT_MATCHES_TRADE,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=REST_CANCEL_ORDER,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
    ),
    RateLimit(
        limit_id=REST_CANCEL_BATCH_ORDERS,
        limit=SAME_USER_REQUEST_LIMIT,
        time_interval=THREE_SECONDS,
        linked_limits=[
            LinkedLimitWeightPair(SAME_IP_REQUESTS_ID),
            LinkedLimitWeightPair(SAME_USER_REQUESTS_ID),
        ],
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
