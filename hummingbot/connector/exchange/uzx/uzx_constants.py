from enum import Enum

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "UZx"

MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""

# API RESPONSE CODE
API_SUCCESS_CODE = 200
ORDER_NOT_EXIST_ERROR_CODE = "XXXX"  # TODO
UNKNOWN_ORDER_ERROR_CODE = "XXXX"  # TODO

# Base URL
DEFAULT_DOMAIN = "com"
REST_URL = "https://api-v2.uzx.com"
PUBLIC_WSS_URL = "wss://stream.uzx.com/notification/ws"
PRIVATE_WSS_URL = "wss://stream.uzx.com/notification/pri/ws"


# Public API endpoints
MARKETS_PATH_URL = "/v2/products"
TICKERS_PATH_URL = "/notification/spot/tickers"
PAIR_TICKER_PATH_URL = "/notification/spot/{symbol}/ticker"
SERVER_TIME_URL = "/v2/time"
DEPTH_PATH_URL = "/notification/spot/{symbol}/orderbook"

# Private API endpoints
BALANCES_PATH_URL = "/v2/account/balances"
CREATE_NEW_ORDER_PATH_URL = "/v2/trade/spot/order"
CANCEL_ORDER_PATH_URL = "/v2/trade/cancel-order"
FILLED_ORDERS_PATH_URL = "/v2/trade/history/orders"
CURRENT_ORDERS_PATH_URL = "/v2/trade/orders"


# order requests cache time
ORDER_REQUESTS_CACHE_TIME = 10
FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 10.0

# Params
DEPTH_LIMIT = 20
WS_HEARTBEAT_TIME_INTERVAL = 5
TAKER_SIDE_SELL = "sell"
TAKER_SIDE_BUY = "buy"

# Rate Limit time intervals
IP_LIMITING_RULE = "IP_LIMITING_RULE"
USER_LIMITING_RULE = "USER_LIMITING_RULE"
ONE_SECOND = 1

# Websocket event types
SUBSCRIBE_METHOD = "sub"
DIFF_EVENT_TYPE = "depthUpdate"
DEALS_EVENT_TYPE = "fills"
DEPTH_EVENT_TYPE = "orderBook"
SUBSCRIBE_TYPE = "spot"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=IP_LIMITING_RULE, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=USER_LIMITING_RULE, limit=10, time_interval=ONE_SECOND),
    # Weighted Limits
    # Public API endpoints
    RateLimit(
        limit_id=SERVER_TIME_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=PAIR_TICKER_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=MARKETS_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=DEPTH_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
        ],
    ),
    # Private API endpoints
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
            LinkedLimitWeightPair(USER_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=CREATE_NEW_ORDER_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
            LinkedLimitWeightPair(USER_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
            LinkedLimitWeightPair(USER_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=FILLED_ORDERS_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
            LinkedLimitWeightPair(USER_LIMITING_RULE),
        ],
    ),
    RateLimit(
        limit_id=CURRENT_ORDERS_PATH_URL,
        limit=10,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(IP_LIMITING_RULE),
            LinkedLimitWeightPair(USER_LIMITING_RULE),
        ],
    ),
]

# Order States
ORDER_STATE = {
    0: OrderState.OPEN,
    1: OrderState.PARTIALLY_FILLED,
    2: OrderState.PARTIALLY_FILLED,
    3: OrderState.CANCELED,
    4: OrderState.FILLED,
}


# exchange status
class OrderStatus(Enum):
    PENDING = 0
    PARTIALLY_FILLED = 1
    PARTIALLY_CANCELED = 2
    CANCELED = 3
    FULLY_FILLED = 4


class Order_Direction(Enum):
    buy = 1
    sell = 2


class Order_Type(Enum):
    MARKET_ORDER = 1
    LIMIT_GTC = 2
    LIMIT_IOC = 3
    LIMIT_FOK = 4
    LIMIT_MAKER = 5
    ADD_MARGIN = 6
    REDUCE_MARGIN = 7
    MODIFY_LEVERAGE = 8
    ONE_CLICK_CLOSING = 9


class Products_Type(Enum):
    base = "BASE"
    swap = "SWAP"
    spot = "SPOT"
