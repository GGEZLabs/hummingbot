from enum import Enum

from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

EXCHANGE_NAME = "P2B"

MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = "x-MG43PCSN"

# API RESPONSE CODE
API_SUCCESS_CODE = ""
ORDER_NOT_EXIST_ERROR_CODE = 2030
ORDER_NOT_EXIST_MESSAGE = "Order not found."
UNKNOWN_ORDER_ERROR_CODE = 3080
UNKNOWN_ORDER_MESSAGE = "Invalid orderId value."

DEFAULT_DOMAIN = "com"

# https://api.p2pb2b.com
# http://api.p2pb2b.com/api/v2/public/market?market=ETH_BTC
# https://api.p2pb2b.com/api/v2/account/balances
# wss://apiws.p2pb2b.com/

# Base URL
REST_URL = "https://api.p2pb2b.com"
WSS_URL = "wss://apiws.p2pb2b.com"
REST_API_NAMESPACE = "api"
PUBLIC_API_VERSION = "v2"
PRIVATE_API_VERSION = "v2"

# Public API endpoints

# http://api.p2pb2b.com/api/v2/public/market?market=ETH_BTC
MARKET_PATH_URL = "/public/market"
MARKETS_PATH_URL = "/public/markets"

# http://api.p2pb2b.com/api/v2/public/ticker?market=ETH_BTC
TICKER_PATH_URL = "/public/ticker"
TICKERS_PATH_URL = "/public/tickers"

# https://api.p2pb2b.com/api/v2/public/book?market=ETH_BTC&side=sell&offset=0&limit=100
ORDER_BOOK_PATH_URL = "/public/book"

# https://api.p2pb2b.com/api/v2/public/history?market=ETH_BTC&lastId=1&limit=100
HISTORY_PATH_URL = "/public/history"

# https://api.p2pb2b.com/api/v2/public/depth/result?market=ETH_BTC&limit=100
DEPTH_PATH_URL = "/public/depth/result"

# http://api.p2pb2b.com/api/v2/public/market/kline?market=ETH_BTC&interval=1m&offset=0&limit=100
MARKET_KLINE_PATH_URL = "/public/market/kline"

# Private API endpoints
BALANCES_PATH_URL = "/account/balances"
BALANCE_PATH_URL = "/account/balance"
ORDER_HISTORY_PATH_URL = "/account/order_history"
ORDER_PATH_URL = "/account/order"
OPEN_ORDERS_PATH_URL = "/orders"
CREATE_NEW_ORDER_PATH_URL = "/order/new"
CANCEL_ORDER_PATH_URL = "/order/cancel"
EXECUTED_HISTORY_PATH_URL = "/account/executed_history"
ALL_EXECUTED_HISTORY_PATH_URL = "/account/executed_history/all"

# cache time
OPEN_ORDERS_CACHE_TIME = 10

WS_HEARTBEAT_TIME_INTERVAL = 30
DEPTH_LIMIT = 20
DEPTH_INTERVAL = "0.0001"
# P2B params

SIDE_BUY = "buy"
SIDE_SELL = "sell"


class OrderRole(Enum):
    TAKER = 1
    MAKER = 2


TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
MAX_REQUESTS_PER_SECOND = 10
ONE_SECOND = 1


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


# Websocket event types
DIFF_EVENT_TYPE = "depthUpdate"
DEALS_EVENT_TYPE = "deals"
DEPTH_EVENT_TYPE = "depth"
SUBSCRIBE_METHOD = "subscribe"


RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=RAW_REQUESTS, limit=MAX_REQUESTS_PER_SECOND, time_interval=ONE_SECOND),
    # Weighted Limits
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=MARKETS_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=DEPTH_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=OPEN_ORDERS_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=CREATE_NEW_ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=CANCEL_ORDER_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=TICKERS_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
    RateLimit(
        limit_id=TICKER_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=ONE_SECOND,
        linked_limits=[
            LinkedLimitWeightPair(RAW_REQUESTS),
        ],
    ),
]
