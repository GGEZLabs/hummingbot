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
REST_URL = "https://api.uzx.com"
PUBLIC_WSS_URL = "wss://v2-api.uzx.com/notification/swap/ws"
PRIVATE_WSS_URL = "wss://v2-api.uzx.com/notification/pri/ws"


# Public API endpoints
MARKETS_PATH_URL = "/api/v1/swap/symbols"
TICKERS_PATH_URL = "/api/symbol-thumb"

# Private API endpoints
BALANCES_PATH_URL = "/api/asset/wallet"
LATEST_TRADES_PATH_URL = "/api/latest-trade"
DEPTH_PATH_URL = "/api/exchange-plate-depth"
CREATE_NEW_ORDER_PATH_URL = "/api/order/add"
CANCEL_ORDER_PATH_URL = "/api/order/cancel/{orderId}"
FILLED_ORDERS_PATH_URL = "/api/order/history"
CURRENT_ORDERS_PATH_URL = "/api/order/current/now"

# order requests cache time
ORDER_REQUESTS_CACHE_TIME = 10
FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 10.0

# Params
DEPTH_LIMIT = 20
WS_HEARTBEAT_TIME_INTERVAL = 5
TAKER_SIDE_SELL = "sell"
TAKER_SIDE_BUY = "buy"

# Rate Limit time intervals
RAW_REQUESTS = "RAW_REQUESTS"
ONE_SECOND = 1

# Websocket event types
SUBSCRIBE_METHOD = "sub"
DIFF_EVENT_TYPE = "depthUpdate"
DEALS_EVENT_TYPE = "fills"
DEPTH_EVENT_TYPE = "orderbook"
SUBSCRIBE_TYPE = "swap"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=RAW_REQUESTS, limit=10, time_interval=ONE_SECOND),
    # Weighted Limits
    # Public API endpoints
    RateLimit(
        limit_id=MARKETS_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    # Private API endpoints
    RateLimit(
        limit_id=DEPTH_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=LATEST_TRADES_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=CREATE_NEW_ORDER_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=FILLED_ORDERS_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=CURRENT_ORDERS_PATH_URL,
        limit=3,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
]

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "PENDING_CANCEL": OrderState.OPEN,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
    "EXPIRED": OrderState.FAILED,
    "EXPIRED_IN_MATCH": OrderState.FAILED,
}


# exchange status
class OrderStatus(Enum):
    TRADING = "TRADING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    OVERTIMED = "OVERTIMED"


class Order_Direction(Enum):
    buy = "BUY"
    sell = "SELL"


class Order_Type(Enum):
    market_price = "MARKET_PRICE"
    limit_price = "LIMIT_PRICE"


CUSTOMER_MARKET_PAIR = [
    {
        "product_id": 204165,
        "product_name": "GGEZ1USDT",
        "swap_value": "0.001",
        "base_coin_id": 9075,
        "base_coin_name": "GGEZ1",
        "quote_coin_id": 9747,
        "quote_coin_name": "USDT",
        "coin_precision": 2,
        "price_precision": 6,
        "price_unit": "0.1",
        "price_range": "0.05",
        "max_leverage": 100,
        "max_once_limit_num": 300000,
        "max_once_market_num": 100000,
        "max_hold_num": 1000000,
        "status": 1,
        "maker_fee": "0.0004",
        "taker_fee": "0.0006",
        "sort": 0,
    }
]
