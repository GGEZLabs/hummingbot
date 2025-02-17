from hummingbot.core.api_throttler.data_types import RateLimit
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
WSS_URL = "wss://apiws.p2pb2b.ws"
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
UNEXECUTED_ORDERS_PATH_URL = "/orders"
CREATE_NEW_ORDER_PATH_URL = "/order/new"
CANCEL_ORDER_PATH_URL = "/order/cancel"
EXECUTED_HISTORY_PATH_URL = "/account/executed_history"
ALL_EXECUTED_HISTORY_PATH_URL = "/account/executed_history/all"

WS_HEARTBEAT_TIME_INTERVAL = 30

# P2B params

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

TIME_IN_FORCE_GTC = "GTC"  # Good till cancelled
TIME_IN_FORCE_IOC = "IOC"  # Immediate or cancel
TIME_IN_FORCE_FOK = "FOK"  # Fill or kill

# Rate Limit Type
REQUEST_WEIGHT = "REQUEST_WEIGHT"
ORDERS = "ORDERS"
ORDERS_24HR = "ORDERS_24HR"
RAW_REQUESTS = "RAW_REQUESTS"

# Rate Limit time intervals
ONE_MINUTE = 60
ONE_SECOND = 1
ONE_DAY = 86400

MAX_REQUEST = 5000

# Order States
ORDER_STATE = {
    "PENDING": OrderState.PENDING_CREATE,
    "NEW": OrderState.OPEN,
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
TRADE_EVENT_TYPE = "trade"

RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=BALANCES_PATH_URL, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=MARKETS_PATH_URL, limit=10, time_interval=ONE_SECOND),
    #
    RateLimit(limit_id=REQUEST_WEIGHT, limit=6000, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=100, time_interval=10 * ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=200000, time_interval=ONE_DAY),
    RateLimit(limit_id=RAW_REQUESTS, limit=61000, time_interval=5 * ONE_MINUTE),
    # # Weighted Limits
    # RateLimit(limit_id=TICKER_PRICE_CHANGE_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=TICKER_BOOK_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=PRICES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=EXCHANGE_INFO_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 100),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=P2B_USER_STREAM_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 2),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=SERVER_TIME_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=PING_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=ACCOUNTS_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=MY_TRADES_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #           linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 20),
    #                          LinkedLimitWeightPair(RAW_REQUESTS, 1)]),
    # RateLimit(limit_id=ORDER_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
    #   linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 4),
    #                  LinkedLimitWeightPair(ORDERS, 1),
    #                  LinkedLimitWeightPair(ORDERS_24HR, 1),
    #                  LinkedLimitWeightPair(RAW_REQUESTS, 1)])
]
