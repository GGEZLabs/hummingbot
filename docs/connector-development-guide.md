# Exchange Connector Development Guide

Internal reference for building new exchange connectors in our customized Hummingbot codebase.

---

## Table of Contents

1. [Introduction & Links](#1-introduction--links)
2. [File Structure & Build Order](#2-file-structure--build-order)
3. [Constants (`*_constants.py`)](#3-constants-_constantspy)
4. [Authentication (`*_auth.py`)](#4-authentication-_authpy)
5. [Web Utils & Config Registration](#5-web-utils--config-registration)
6. [Order Book & Data Sources](#6-order-book--data-sources)
7. [Main Exchange Class (`*_exchange.py`)](#7-main-exchange-class-_exchangepy)
8. [Caching Mechanisms](#8-caching-mechanisms)
9. [Price Oracle](#9-price-oracle)
10. [Data Feed Candles](#10-data-feed-candles)
11. [Testing Approach](#11-testing-approach)
12. [General Notes & Tips](#12-general-notes--tips)
13. [Appendix A: Abstract Methods Checklist](#appendix-a-abstract-methods-checklist)
14. [Appendix B: Registration Checklist](#appendix-b-registration-checklist)

---

## 1. Introduction & Links

### Purpose

This document is the definitive internal reference for building a new exchange connector for our Hummingbot deployment. It covers the standard connector architecture plus our custom additions: caching, price oracle integration, candle feeds, and volume methods.

### Prerequisites

- Python 3.10+
- Strong understanding of `asyncio` and async/await patterns
- Access to the target exchange's REST and WebSocket API documentation
- Familiarity with HMAC-based authentication schemes
- Understanding of order book data structures

### Official References

- Official connector docs: https://hummingbot.org/connectors/connectors/
- Official architecture: https://hummingbot.org/developers/connectors/architecture/
- Base class: `hummingbot/connector/exchange_py_base.py`

### Files Checklist (per connector)

Every exchange connector requires **8 files** in `hummingbot/connector/exchange/<exchange_name>/`:

| # | File | Purpose |
|---|------|---------|
| 1 | `__init__.py` | Package marker (empty) |
| 2 | `<name>_constants.py` | API URLs, rate limits, order state mappings |
| 3 | `<name>_auth.py` | Request signing and authentication |
| 4 | `<name>_web_utils.py` | URL builders, API factory, throttler creation |
| 5 | `<name>_utils.py` | Config map, fee schema, keys, auto-discovery metadata |
| 6 | `<name>_order_book.py` | Order book message parsing |
| 7 | `<name>_api_order_book_data_source.py` | REST snapshots + WebSocket order book streaming |
| 8 | `<name>_api_user_stream_data_source.py` | WebSocket user events (fills, balances) |
| 9 | `<name>_exchange.py` | Main exchange class (implements `ExchangePyBase`) |

---

## 2. File Structure & Build Order

### Recommended Build Order

Build files in this order to resolve dependencies incrementally:

```
1. constants.py       -- No internal dependencies
2. auth.py            -- Depends on: constants
3. web_utils.py       -- Depends on: constants, auth
4. utils.py           -- Depends on: constants (for auto-discovery)
5. order_book.py      -- Depends on: constants
6. api_order_book_data_source.py  -- Depends on: constants, web_utils, order_book
7. api_user_stream_data_source.py -- Depends on: constants, auth, web_utils
8. exchange.py        -- Depends on: ALL above files
```

### Base Class

The main exchange class inherits from `ExchangePyBase` (in `hummingbot/connector/exchange_py_base.py`), which requires implementing:

- **13 abstract properties** (name, authenticator, rate limits, domain, etc.)
- **14 abstract methods** (place order, cancel, update balances, format trading rules, etc.)

See [Appendix A](#appendix-a-abstract-methods-checklist) for the full list.

---

## 3. Constants (`*_constants.py`)

This file defines all exchange-specific constants. It has no internal dependencies and is imported by every other file.

### Required Constants

```python
# Exchange identity
EXCHANGE_NAME = "MyExchange"
MAX_ORDER_ID_LEN = 32
HBOT_ORDER_ID_PREFIX = ""  # or a prefix like "x-MG43PCSN"

# API response codes
API_SUCCESS_CODE = 0           # Exchange-specific success indicator
ORDER_NOT_EXIST_ERROR_CODE = 4003
UNKNOWN_ORDER_ERROR_CODE = 3103

# Base URLs
REST_URL = "https://api.myexchange.com"
WSS_URL = "wss://ws.myexchange.com/ws"
DEFAULT_DOMAIN = "com"

# Public API endpoints
MARKETS_PATH_URL = "/v1/markets"
TICKER_PATH_URL = "/v1/ticker"
TICKERS_PATH_URL = "/v1/tickers"
DEPTH_PATH_URL = "/v1/depth"

# Private API endpoints
BALANCES_PATH_URL = "/v1/account/balances"
CREATE_NEW_ORDER_PATH_URL = "/v1/order/new"
CANCEL_ORDER_PATH_URL = "/v1/order/cancel"

# Cache TTLs
OPEN_ORDERS_CACHE_TIME = 10  # seconds

# WebSocket
WS_HEARTBEAT_TIME_INTERVAL = 30
DEPTH_LIMIT = 20

# Order state mapping (exchange state -> Hummingbot OrderState)
ORDER_STATE = {
    "OPEN": OrderState.OPEN,
    "FILLED": OrderState.FILLED,
    "PARTIALLY_FILLED": OrderState.PARTIALLY_FILLED,
    "CANCELED": OrderState.CANCELED,
    "REJECTED": OrderState.FAILED,
}
```

### Rate Limit Patterns

Rate limits use `RateLimit` objects with optional `LinkedLimitWeightPair` for shared pools.

**Comparison Table:**

| Feature | P2B | UZX | Coinstore |
|---------|-----|-----|-----------|
| Pool type | Single (`RAW_REQUESTS`) | Dual (`IP` + `USER`) | Dual (`SAME_IP` + `SAME_USER`) |
| Rate | 10 req/s | 10 req/s (IP), 3 req/s (orders) | 8 req/3s (IP), 6 req/3s (user) |
| Window | 1 second | 1 second | 3 seconds |
| Private endpoints | Linked to RAW_REQUESTS | Linked to BOTH pools | Linked to BOTH pools |
| Public endpoints | Linked to RAW_REQUESTS | Linked to IP only | Linked to IP only |

**Template - Single Pool (simplest):**

```python
RAW_REQUESTS = "RAW_REQUESTS"
MAX_REQUESTS_PER_SECOND = 10

RATE_LIMITS = [
    RateLimit(limit_id=RAW_REQUESTS, limit=MAX_REQUESTS_PER_SECOND, time_interval=1),
    RateLimit(
        limit_id=BALANCES_PATH_URL,
        limit=MAX_REQUESTS_PER_SECOND,
        time_interval=1,
        linked_limits=[LinkedLimitWeightPair(RAW_REQUESTS)],
    ),
    # ... repeat for each endpoint
]
```

**Template - Dual Pool (recommended for production):**

```python
IP_POOL = "IP_POOL"
USER_POOL = "USER_POOL"

RATE_LIMITS = [
    # Pool definitions
    RateLimit(limit_id=IP_POOL, limit=8, time_interval=3),
    RateLimit(limit_id=USER_POOL, limit=6, time_interval=3),
    # Public endpoint - IP only
    RateLimit(
        limit_id=MARKETS_PATH_URL, limit=8, time_interval=3,
        linked_limits=[LinkedLimitWeightPair(IP_POOL)],
    ),
    # Private endpoint - both pools
    RateLimit(
        limit_id=CREATE_NEW_ORDER_PATH_URL, limit=6, time_interval=3,
        linked_limits=[
            LinkedLimitWeightPair(IP_POOL),
            LinkedLimitWeightPair(USER_POOL),
        ],
    ),
]
```

---

## 4. Authentication (`*_auth.py`)

Inherits from `AuthBase` (`hummingbot/core/web_assistant/auth.py`) and must implement:

- `rest_authenticate(request: RESTRequest) -> RESTRequest`
- `ws_authenticate(request: WSRequest) -> WSRequest`

### Authentication Comparison

| Feature | P2B | UZX | Coinstore |
|---------|-----|-----|-----------|
| Algorithm | HMAC-SHA512 | HMAC-SHA256 | Double HMAC-SHA256 |
| Body handling | Base64-encode body, sign it | Concatenate timestamp+method+path+query+body | Rotating key from `floor(timestamp/30000)` |
| Headers | `X-TXC-APIKEY`, `X-TXC-SIGNATURE`, `X-TXC-PAYLOAD` | `UZX-ACCESS-KEY`, `UZX-ACCESS-SIGN`, `UZX-ACCESS-TIMESTAMP`, `UZX-ACCESS-PASSPHRASE` | `X-CS-APIKEY`, `X-CS-EXPIRES`, `X-CS-SIGN` |
| Extra credentials | API key + secret | API key + secret + passphrase | API key + secret |
| WS auth | None (pass-through) | Login event with signed timestamp | Login message with signed "LOGIN" string |
| Nonce/Timestamp | Millisecond timestamp + random offset | Unix seconds | Millisecond timestamp |

### Template

```python
class MyExchangeAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        # 1. Extract or serialize the request body/params
        # 2. Generate timestamp
        # 3. Create signature string (exchange-specific format)
        # 4. Sign with HMAC
        # 5. Add auth headers to request
        headers = self._build_auth_headers(request)
        request.headers = {**(request.headers or {}), **headers}
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        return request  # pass-through if WS auth not needed

    def _generate_signature(self, message: str) -> str:
        return hmac.new(
            self.secret_key.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
```

### Coinstore's Rotating Key Pattern (most complex)

Coinstore uses a unique approach where the signing key rotates every 30 seconds:

```
1. expires_key = floor(timestamp_ms / 30000)   -- rotates every 30s
2. hmac_key = HMAC-SHA256(secret_key, expires_key)  -- derive ephemeral key
3. signature = HMAC-SHA256(hmac_key, request_body)   -- sign with ephemeral key
```

This adds an extra layer of security but means the signing key changes over time.

---

## 5. Web Utils & Config Registration

### `*_web_utils.py`

Provides URL builders and API factory construction:

```python
def public_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URL}{path_url}"

def private_rest_url(path_url: str, domain: str = DEFAULT_DOMAIN) -> str:
    return f"{CONSTANTS.REST_URL}{path_url}"

def build_api_factory(
    throttler: AsyncThrottler,
    time_synchronizer: TimeSynchronizer,
    domain: str,
    auth: AuthBase,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer,
                time_provider=time_provider,
            ),
        ],
    )

def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)

async def get_current_server_time(throttler, domain) -> float:
    # Option A: Call exchange's server time endpoint
    # Option B: Use local time (simpler, works for most exchanges)
    return int(time.time() * 1000)
```

### `*_utils.py` - Config Registration & Auto-Discovery

This file is critical for Hummingbot's auto-discovery system. It must define specific module-level variables:

```python
from decimal import Decimal
from pydantic import ConfigDict, Field, SecretStr
from hummingbot.client.config.config_data_types import BaseConnectorConfigMap
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

# Required module-level constants for auto-discovery
CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True,
)

# Config map defines the API credentials the user must provide
class MyExchangeConfigMap(BaseConnectorConfigMap):
    connector: str = "my_exchange"
    my_exchange_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your MyExchange API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    my_exchange_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your MyExchange API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    model_config = ConfigDict(title="my_exchange")

KEYS = MyExchangeConfigMap.model_construct()
```

### Multi-Account Support (`OTHER_DOMAINS`)

To support multiple API key sets for the same exchange (e.g., running two accounts simultaneously):

```python
OTHER_DOMAINS = ["my_exchange_2"]
OTHER_DOMAINS_PARAMETER = {"my_exchange_2": "_2"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"my_exchange_2": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"my_exchange_2": DEFAULT_FEES}

class MyExchange2ConfigMap(BaseConnectorConfigMap):
    connector: str = "my_exchange_2"
    # ... same fields with _2 suffix prompts
    model_config = ConfigDict(title="my_exchange_2")

OTHER_DOMAINS_KEYS = {"my_exchange_2": MyExchange2ConfigMap.construct()}
```

Both P2B and Coinstore use this pattern. The `domain` parameter is passed through to the exchange class to differentiate instances.

### Auto-Discovery

Hummingbot automatically discovers connectors through `AllConnectorSettings.create_connector_settings()` in `hummingbot/client/settings.py`. It scans `hummingbot/connector/exchange/*/` directories and imports `*_utils.py` from each, reading the `CENTRALIZED`, `EXAMPLE_PAIR`, `DEFAULT_FEES`, and `KEYS` variables. No manual registration is needed for the connector itself.

---

## 6. Order Book & Data Sources

### `*_order_book.py`

Parses raw exchange messages into standardized order book format. Typically a lightweight class with static methods:

```python
class MyExchangeOrderBook(OrderBook):
    @classmethod
    def snapshot_message_from_exchange(cls, msg, timestamp, metadata=None):
        # Convert exchange snapshot format to OrderBookMessage
        ...

    @classmethod
    def diff_message_from_exchange(cls, msg, timestamp, metadata=None):
        # Convert exchange diff/delta format to OrderBookMessage
        ...

    @classmethod
    def trade_message_from_exchange(cls, msg, metadata=None):
        # Convert exchange trade format to OrderBookMessage
        ...
```

### `*_api_order_book_data_source.py`

Handles REST snapshots and WebSocket streaming for public market data:

**Key methods to implement:**

- `_request_order_book_snapshot(trading_pair)` - REST call to get full order book
- `_subscribe_channels(ws)` - Subscribe to WebSocket depth/trade channels
- `_parse_order_book_diff_message(raw_message, message_queue)` - Parse WS diff messages
- `_parse_trade_message(raw_message, message_queue)` - Parse WS trade messages

### `*_api_user_stream_data_source.py`

Handles WebSocket streaming for private user data (order fills, balance changes):

**Key methods to implement:**

- `_subscribe_channels(ws)` - Subscribe to private channels (may need WS auth)
- `_process_event_message(event_message, queue)` - Parse user events

### Trading Pair Format Conventions

Each exchange has its own pair format. You must handle conversions:

| Exchange | Exchange Format | Hummingbot Format | Conversion Method |
|----------|----------------|-------------------|-------------------|
| P2B | `BTC_USDT` | `BTC-USDT` | Replace `_` with `-` |
| UZX | `BTC-USDT` | `BTC-USDT` | Replace `-` with `/` (for API) |
| Coinstore | `BTCUSDT` | `BTC-USDT` | Concatenated (no separator) |

The conversion is done via:
- `get_exchange_trading_pair(hb_pair)` - Hummingbot format to exchange format
- `get_hbot_trading_pair(exchange_pair)` - Exchange format to Hummingbot format

---

## 7. Main Exchange Class (`*_exchange.py`)

### Class-Level Configuration

```python
class MyExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 1.0  # Seconds between status updates
    LONG_POLL_INTERVAL = 10                  # Seconds for long-polling when WS active
    TICK_INTERVAL_LIMIT = 10                 # Seconds threshold for poll mode switch
    web_utils = web_utils                    # Reference to web_utils module
```

**Polling interval comparison:**

| Setting | P2B | UZX | Coinstore |
|---------|-----|-----|-----------|
| `UPDATE_ORDER_STATUS_MIN_INTERVAL` | 1.0s | 10.0s | 1.0s |
| `LONG_POLL_INTERVAL` | 10s | 30s | 10s |
| `TICK_INTERVAL_LIMIT` | 10s | 60s (default) | 10s |

### Required Properties (13 total)

```python
@property
def name(self) -> str: ...                              # "my_exchange"
@property
def authenticator(self) -> AuthBase: ...                # Return auth instance
@property
def rate_limits_rules(self) -> List[RateLimit]: ...     # Return RATE_LIMITS
@property
def domain(self) -> str: ...                            # "com" (or variant)
@property
def client_order_id_max_length(self) -> int: ...        # e.g., 32
@property
def client_order_id_prefix(self) -> str: ...            # e.g., "" or "x-PREFIX"
@property
def trading_rules_request_path(self) -> str: ...        # e.g., "/v1/markets"
@property
def trading_pairs_request_path(self) -> str: ...        # e.g., "/v1/markets"
@property
def check_network_request_path(self) -> str: ...        # e.g., "/v1/markets"
@property
def trading_pairs(self) -> List[str]: ...               # Return self._trading_pairs
@property
def is_cancel_request_in_exchange_synchronous(self) -> bool: ...  # Usually True
@property
def is_trading_required(self) -> bool: ...              # Return self._trading_required
```

### Required Methods (14 total)

```python
def supported_order_types(self) -> List[OrderType]: ...
def _is_request_exception_related_to_time_synchronizer(self, ex) -> bool: ...
def _is_order_not_found_during_status_update_error(self, ex) -> bool: ...
def _is_order_not_found_during_cancelation_error(self, ex) -> bool: ...
def _create_web_assistants_factory(self) -> WebAssistantsFactory: ...
def _create_order_book_data_source(self) -> OrderBookTrackerDataSource: ...
def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource: ...
def _get_fee(self, base, quote, order_type, side, amount, price, is_maker) -> TradeFeeBase: ...
def _initialize_trading_pair_symbols_from_exchange_info(self, info): ...
async def _place_order(self, order_id, pair, amount, side, type, price) -> Tuple[str, float]: ...
async def _place_cancel(self, order_id, tracked_order) -> bool: ...
async def _format_trading_rules(self, exchange_info) -> List[TradingRule]: ...
async def _update_trading_fees(self): ...   # Can be pass if exchange has no fee endpoint
async def _user_stream_event_listener(self): ...
async def _all_trade_updates_for_order(self, order) -> List[TradeUpdate]: ...
async def _request_order_status(self, tracked_order) -> OrderUpdate: ...
async def _update_balances(self): ...
```

### Custom Methods (our additions)

These are **not** part of the base class but are added to all our connectors for strategy integration:

```python
async def get_all_pairs_prices(self) -> List[Dict[str, str]]:
    """Fetch ticker prices for all trading pairs. Used by rate oracle."""
    ...

async def get_volume(self, trading_pair: str) -> Decimal:
    """Get 24h trading volume for a pair. Used by volume strategies."""
    ...

async def track_all_open_orders(self, market: str):
    """
    Discover and track orders placed outside Hummingbot.
    Useful for managing orders across bot restarts or external tools.
    """
    ...
```

---

## 8. Caching Mechanisms

### Why Caching Matters

Without caching, a bot with 10 open orders triggers **20+ API calls per polling cycle** (one status check + one trade fill check per order). With typical polling intervals of 1-10 seconds, this quickly exhausts rate limits.

Caching works by:
1. Fetching a batch response (e.g., all open orders) once
2. Storing it with a timestamp
3. Reusing the cached response for individual order lookups within the TTL window

### Cache Architecture Comparison

| Feature | P2B | UZX | Coinstore |
|---------|-----|-----|-----------|
| **Cache count** | 1 (unfilled orders) | 2 (unfilled + filled) | 3 (unfilled + order_info + trade fills) |
| **Cache TTL** | 10s | 10s | 10s (unfilled, order_info) |
| **Cleanup** | None | None | Every 60s |
| **Duplicate fill prevention** | No | No | Yes (via `_processed_trade_fills`) |
| **Memory management** | Unbounded | Unbounded | Bounded (periodic cleanup) |

### Cache Pattern 1: Single Cache (P2B - simplest)

```python
def __init__(self, ...):
    self._unfilled_or_partially_filled_responses_cache = {}

async def _get_unfilled_or_partially_filled_response(self, market: str):
    cached = self._unfilled_or_partially_filled_responses_cache.get(market)
    if cached is not None:
        if cached["timestamp"] > self.current_timestamp - CACHE_TTL:
            return cached["response"]

    response = await self._api_post(...)  # Fetch from exchange
    self._unfilled_or_partially_filled_responses_cache[market] = {
        "response": response,
        "timestamp": self.current_timestamp,
    }
    return response
```

### Cache Pattern 2: Dual Cache (UZX)

Adds a second cache for filled/completed orders, since checking both unfilled and filled orders is needed for status resolution:

```python
def __init__(self, ...):
    self._unfilled_or_partially_filled_responses_cache = {}
    self._filled_responses_cache = {}

async def _get_filled_response(self, market: str):
    cached = self._filled_responses_cache.get(market)
    if cached and (self.current_timestamp - cached["timestamp"] < CACHE_TTL):
        return cached["response"]

    response = await self._api_get(...)
    self._filled_responses_cache[market] = {
        "response": response,
        "timestamp": self.current_timestamp,
    }
    return response
```

### Cache Pattern 3: Triple Cache + Cleanup (Coinstore - recommended)

The most robust pattern with three caches, duplicate fill prevention, and periodic cleanup:

```python
def __init__(self, ...):
    # Cache 1: Active/unfilled orders
    self._unfilled_or_partially_filled_responses_cache = {}
    # Cache 2: Individual order info lookups
    self._order_info_cache: Dict[str, Dict[str, Any]] = {}
    self._order_info_cache_time = 10.0
    # Cache 3: Track processed trade fill amounts
    self._processed_trade_fills: Dict[str, Decimal] = {}
    # Cleanup timer
    self._last_cache_cleanup_timestamp = 0.0
```

**Duplicate fill prevention** tracks cumulative filled quantities per order:

```python
async def _all_trade_updates_for_order(self, order):
    exchange_id = str(order.exchange_order_id)
    # ... fetch current fill amount from exchange ...

    prev_fill_qty = self._processed_trade_fills.get(exchange_id, Decimal("0"))
    if current_fill_qty <= prev_fill_qty:
        return []  # Already processed this fill level

    incremental = current_fill_qty - prev_fill_qty
    # ... create TradeUpdate with incremental amount ...
    self._processed_trade_fills[exchange_id] = current_fill_qty
```

**Periodic cleanup** prevents memory leaks in long-running bots:

```python
def _cleanup_caches(self):
    if self.current_timestamp - self._last_cache_cleanup_timestamp < 60.0:
        return
    self._last_cache_cleanup_timestamp = self.current_timestamp

    # Remove expired order info entries
    expired = [k for k, v in self._order_info_cache.items()
               if self.current_timestamp - v["timestamp"] > self._order_info_cache_time * 2]
    for k in expired:
        del self._order_info_cache[k]

    # Remove trade fills for orders no longer tracked
    active_ids = {str(o.exchange_order_id)
                  for o in self._order_tracker.all_fillable_orders.values()
                  if o.exchange_order_id}
    stale = [k for k in self._processed_trade_fills if k not in active_ids]
    for k in stale:
        del self._processed_trade_fills[k]
```

### Recommendation for New Connectors

Use the **3-cache + cleanup pattern** (Coinstore style). Reasons:

1. **Duplicate fills** cause accounting errors and can trigger unwanted strategy actions
2. **Memory leaks** from unbounded caches cause bots to slowly consume more RAM over days
3. **Rate limit safety** from the order_info cache prevents hammering endpoints for completed orders
4. The extra complexity is minimal and pays for itself in production reliability

---

## 9. Price Oracle

### Architecture

The rate oracle system provides conversion rates for any token pair, used for portfolio valuation, fee calculation, and cross-pair arbitrage.

- **Base class**: `hummingbot/core/rate_oracle/sources/rate_source_base.py`
- **Registry**: `hummingbot/core/rate_oracle/rate_oracle.py` (`RATE_ORACLE_SOURCES` dict)
- **Utilities**: `hummingbot/core/rate_oracle/utils.py` (`find_rate` function)

### Currently Registered Sources (16)

```
binance, binance_us, coin_gecko, coin_cap, kucoin, ascend_ex,
gate_io, coinbase_advanced_trade, cube, dexalot, hyperliquid,
derive, mexc, uzx, p2b, coinstore
```

### Graph-Based Price Finding

The `find_rate()` function in `utils.py` performs chain conversion:

```
Direct:     BTC-USDT exists -> use it
Reverse:    USDT-BTC exists -> use 1/price
Chain:      BTC-ETH + ETH-USDT exists -> BTC-USDT = BTC-ETH * ETH-USDT
Inverse chain: BTC-ETH + USDT-ETH exists -> BTC-USDT = BTC-ETH / USDT-ETH
```

### Steps to Add a New Rate Source

1. **Create** `hummingbot/core/rate_oracle/sources/<name>_rate_source.py`
2. **Inherit** from `RateSourceBase`
3. **Implement** `name` property and `get_prices()` method
4. **Register** in `RATE_ORACLE_SOURCES` dict in `rate_oracle.py`

### Template

```python
from decimal import Decimal
from typing import Dict, Optional
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache

class MyExchangeRateSource(RateSourceBase):
    def __init__(self):
        super().__init__()
        self._exchange = None  # Lazy init to avoid circular imports

    @property
    def name(self) -> str:
        return "my_exchange"

    @async_ttl_cache(ttl=30, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        self._ensure_exchange()
        pairs_prices = await self._exchange.get_all_pairs_prices()
        results = {}
        for ticker in pairs_prices:
            # Parse exchange-specific ticker format
            # Convert to trading_pair -> mid_price mapping
            bid = Decimal(ticker["bid"])
            ask = Decimal(ticker["ask"])
            if 0 < bid <= ask:
                results[trading_pair] = (bid + ask) / Decimal("2")
        return results

    def _ensure_exchange(self):
        if self._exchange is None:
            from hummingbot.client.hummingbot_application import HummingbotApplication
            from hummingbot.connector.exchange.my_exchange.my_exchange_exchange import MyExchangeExchange
            app = HummingbotApplication.main_application()
            self._exchange = MyExchangeExchange(
                client_config_map=app.client_config_map,
                my_exchange_api_key="",
                my_exchange_api_secret="",
                trading_pairs=[],
                trading_required=False,
            )
```

Key points:
- Use `@async_ttl_cache(ttl=30)` to avoid hammering the exchange for rate data
- Create the exchange instance **without** private keys (trading_required=False)
- Use lazy initialization to avoid circular imports

---

## 10. Data Feed Candles

### Architecture

The candle feed system provides OHLCV data for strategies that need technical analysis.

- **Base class**: `hummingbot/data_feed/candles_feed/candles_base.py`
- **Registry**: `hummingbot/data_feed/candles_feed/candles_factory.py` (`_candles_map` dict)
- **Config**: `hummingbot/data_feed/candles_feed/data_types.py` (`CandlesConfig`)

### Standard Candle Format

All candle feeds must normalize data to this 10-column format:

```python
columns = [
    "timestamp",           # Unix timestamp (seconds)
    "open",                # Open price
    "high",                # High price
    "low",                 # Low price
    "close",               # Close price
    "volume",              # Base asset volume
    "quote_asset_volume",  # Quote asset volume
    "n_trades",            # Number of trades
    "taker_buy_base_volume",   # Taker buy base volume
    "taker_buy_quote_volume",  # Taker buy quote volume
]
```

### Interval Support Comparison

| Exchange | Intervals Supported | Total |
|----------|-------------------|-------|
| P2B | 1m, 1h, 1d | 3 |
| UZX | 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 5d, 1w, 1M | 16 |
| Coinstore | 1m, 5m, 15m, 30m, 1h, 4h, 12h, 1d, 1w, 1M | 10 |

### Coinstore's Dual Interval Naming

Coinstore uses different interval names for REST vs WebSocket:

```python
# REST intervals
REST_INTERVALS = {"1m": "1min", "5m": "5min", "1h": "60min", "4h": "4hour", ...}

# WebSocket intervals
WS_INTERVALS = {"1m": "min_1", "5m": "min_5", "1h": "hour_1", "4h": "hour_4", ...}
```

This requires mapping in both the REST fetch and WS subscribe methods.

### Steps to Add Candle Support

1. **Create directory**: `hummingbot/data_feed/candles_feed/<name>_spot_candles/`
2. **Create files**:
   - `__init__.py` (empty)
   - `constants.py` (URLs, intervals, rate limits)
   - `<name>_spot_candles.py` (implements `CandlesBase`)
3. **Register** in `candles_factory.py`:
   ```python
   from hummingbot.data_feed.candles_feed.<name>_spot_candles.<name>_spot_candles import MyExchangeSpotCandles
   # Add to _candles_map:
   "my_exchange": MyExchangeSpotCandles,
   ```

### Candle Constants Template

```python
from bidict import bidict
from hummingbot.core.api_throttler.data_types import RateLimit

REST_URL = "https://api.myexchange.com"
WSS_URL = "wss://ws.myexchange.com/ws"
HEALTH_CHECK_ENDPOINT = "/v1/markets"
CANDLES_ENDPOINT = "/v1/klines"

INTERVALS = bidict({
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "60min",
    "4h": "4hour",
    "1d": "1day",
})

DEFAULT_INTERVAL = "1h"
MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST = 300

RATE_LIMITS = [
    RateLimit("RAW", limit=10, time_interval=1),
    RateLimit(CANDLES_ENDPOINT, limit=10, time_interval=1),
    RateLimit(HEALTH_CHECK_ENDPOINT, limit=10, time_interval=1),
]
```

---

## 11. Testing Approach

### Recommended Build-Test Order

Test each component as you build it, in this order:

| # | Test | What It Validates | Why This Order |
|---|------|-------------------|----------------|
| 1 | **Balance fetch** | Auth + web_utils + network connectivity | Simplest authenticated endpoint |
| 2 | **Trading rules** | Exchange info parsing, trading pair symbol mapping | Validates data normalization |
| 3 | **Order book** | REST snapshot + WebSocket streaming | Validates public data pipeline |
| 4 | **Place order** | Full order flow (create -> track -> receive exchange ID) | Validates core trading |
| 5 | **Cancel order** | Cancellation flow | Validates order lifecycle |
| 6 | **Order status + trade updates** | Caching logic, fill detection, state transitions | Validates status polling |
| 7 | **User stream** | WebSocket event processing (fills, balance updates) | Validates real-time updates |

### Test Base Class

The test framework provides `AbstractExchangeConnectorTests.ExchangeConnectorTests` in `hummingbot/connector/test_support/exchange_connector_test.py`.

It requires implementing **~51 abstract members** including:

**URL properties (6):**
- `all_symbols_url`, `latest_prices_url`, `network_status_url`
- `trading_rules_url`, `order_creation_url`, `balance_url`

**Mock response properties (9):**
- `all_symbols_request_mock_response`, `latest_prices_request_mock_response`
- `all_symbols_including_invalid_pair_mock_response`
- `network_status_request_successful_mock_response`
- `trading_rules_request_mock_response`, `trading_rules_request_erroneous_mock_response`
- `order_creation_request_successful_mock_response`
- `balance_request_mock_response_for_base_and_quote`, `balance_request_mock_response_only_base`

**Expected values (8):**
- `expected_latest_price`, `expected_supported_order_types`
- `expected_trading_rule`, `expected_logged_error_for_erroneous_trading_rule`
- `expected_exchange_order_id`, `expected_partial_fill_price`
- `expected_partial_fill_amount`, `expected_fill_fee`, `expected_fill_trade_id`

**Validation methods (5):**
- `validate_auth_credentials_present`, `validate_order_creation_request`
- `validate_order_cancelation_request`, `validate_order_status_request`
- `validate_trades_request`

**Configuration methods (14):**
- `configure_successful_cancelation_response`
- `configure_erroneous_cancelation_response`
- `configure_order_not_found_error_cancelation_response`
- `configure_one_successful_one_erroneous_cancel_all_response`
- `configure_completely_filled_order_status_response`
- `configure_canceled_order_status_response`
- `configure_open_order_status_response`
- `configure_http_error_order_status_response`
- `configure_partially_filled_order_status_response`
- `configure_order_not_found_error_order_status_response`
- `configure_partial_fill_trade_response`
- `configure_erroneous_http_fill_trade_response`
- `configure_full_fill_trade_response`

**WebSocket event methods (5):**
- `order_event_for_new_order_websocket_update`
- `order_event_for_canceled_order_websocket_update`
- `order_event_for_full_fill_websocket_update`
- `trade_event_for_full_fill_websocket_update`
- `balance_event_websocket_update`

**Factory methods (2):**
- `exchange_symbol_for_tokens`, `create_exchange_instance`

### HTTP Mocking

Tests use the `aioresponses` library to mock HTTP calls:

```python
from aioresponses import aioresponses

@aioresponses()
async def test_balance_fetch(self, mock_api):
    url = f"{CONSTANTS.REST_URL}{CONSTANTS.BALANCES_PATH_URL}"
    mock_api.post(url, body=json.dumps({"data": [...]}))

    await self.exchange._update_balances()
    self.assertEqual(Decimal("100"), self.exchange.available_balances["BTC"])
```

### Manual Testing Tips

1. **Use `scripts/` directory** - Create a simple script that instantiates your connector and tests basic operations
2. **Start with read-only endpoints** - Balances, ticker, order book before placing real orders
3. **Use small amounts** - When testing order placement, use minimum order sizes
4. **Check logs** - Hummingbot logs to `logs/` directory; use `hummingbot logs` command in the CLI
5. **Test edge cases** - Server overload (503), order not found, rate limit exceeded

---

## 12. General Notes & Tips

### Timestamp Units

Exchanges use different timestamp units. Always normalize:

```python
# Seconds (Unix) -> standard for Hummingbot internal use
# Milliseconds -> most common in exchange APIs
# Convert ms to s: timestamp * 1e-3
# Convert s to ms: int(timestamp * 1e3)
```

Watch for this in:
- `fill_timestamp` in `TradeUpdate` (expects seconds)
- `update_timestamp` in `OrderUpdate` (expects seconds)
- Exchange API parameters (usually expects milliseconds)

### Common Pitfalls

1. **Error code checking** - Each exchange returns errors differently. Some use HTTP status codes, others embed error codes in JSON response bodies. Always check both.

2. **WebSocket reconnection** - WebSocket connections drop. The base class handles reconnection, but your subscribe logic must be **idempotent** (safe to call multiple times).

3. **Exchange order ID types** - Some exchanges return integer IDs, others return strings. Always convert to `str` when creating `OrderUpdate` or `TradeUpdate` objects.

4. **Trading pair symbol map** - The `_initialize_trading_pair_symbols_from_exchange_info` method must create a `bidict` mapping between exchange symbols and Hummingbot trading pairs. This mapping is used throughout the connector.

5. **`_make_trading_pairs_request` and `_make_trading_rules_request`** - Override these if the exchange requires POST instead of GET, or needs special parameters (like UZX requiring `{"ins_type": "SPOT"}`).

6. **`_make_network_check_request`** - Override if the health check endpoint needs POST or authentication (like Coinstore using the accounts endpoint).

7. **Unfilled quantity calculation** - Different exchanges report filled vs unfilled differently:
   - Some give `left` (remaining amount)
   - Some give `dealStock` (filled amount)
   - Some give `cumQty` (cumulative filled quantity)

### Debugging

- **Logger**: Every connector has `self.logger()` available
- **CLI logs**: Use `hummingbot logs` command in the Hummingbot CLI
- **Log files**: Check `logs/` directory for detailed output
- **Network debugging**: Set log level to DEBUG to see all HTTP requests/responses

### Performance Considerations

- **Batch operations** - Use batch cancel endpoints when available (Coinstore has `REST_CANCEL_BATCH_ORDERS`)
- **Cache aggressively** - Especially for endpoints called per-order (multiply by number of open orders)
- **Minimize WS subscriptions** - Only subscribe to channels you need
- **Use `safe_gather`** - For parallel async operations with error handling

---

## Appendix A: Abstract Methods Checklist

Complete list from `ExchangePyBase`:

### Abstract Properties (13)

| Property | Return Type | Description |
|----------|-------------|-------------|
| `name` | `str` | Connector name (e.g., "my_exchange") |
| `authenticator` | `AuthBase` | Auth instance for request signing |
| `rate_limits_rules` | `List[RateLimit]` | Rate limit configuration |
| `domain` | `str` | Domain variant (e.g., "com") |
| `client_order_id_max_length` | `int` | Max length for client order IDs |
| `client_order_id_prefix` | `str` | Prefix for generated order IDs |
| `trading_rules_request_path` | `str` | REST path for trading rules |
| `trading_pairs_request_path` | `str` | REST path for available pairs |
| `check_network_request_path` | `str` | REST path for health check |
| `trading_pairs` | `List[str]` | Active trading pairs |
| `is_cancel_request_in_exchange_synchronous` | `bool` | True if cancel is synchronous |
| `is_trading_required` | `bool` | True if auth/trading is needed |

### Abstract Methods (15)

| Method | Return Type | Description |
|--------|-------------|-------------|
| `supported_order_types()` | `List[OrderType]` | Supported order types (LIMIT, MARKET, etc.) |
| `_is_request_exception_related_to_time_synchronizer(ex)` | `bool` | Check if error is time-sync related |
| `_is_order_not_found_during_status_update_error(ex)` | `bool` | Check if error means order not found |
| `_is_order_not_found_during_cancelation_error(ex)` | `bool` | Check if cancel error means order not found |
| `_create_web_assistants_factory()` | `WebAssistantsFactory` | Build the HTTP/WS client factory |
| `_create_order_book_data_source()` | `OrderBookTrackerDataSource` | Build order book data source |
| `_create_user_stream_data_source()` | `UserStreamTrackerDataSource` | Build user stream data source |
| `_get_fee(...)` | `TradeFeeBase` | Calculate trading fee |
| `_initialize_trading_pair_symbols_from_exchange_info(info)` | `None` | Build symbol mapping from exchange info |
| `_place_order(...)` | `Tuple[str, float]` | Submit order, return (exchange_id, timestamp) |
| `_place_cancel(order_id, tracked_order)` | `bool` | Cancel order, return success |
| `_format_trading_rules(exchange_info)` | `List[TradingRule]` | Parse exchange info into trading rules |
| `_update_trading_fees()` | `None` | Update fee info (can be `pass`) |
| `_user_stream_event_listener()` | `None` | Process WebSocket user events loop |
| `_all_trade_updates_for_order(order)` | `List[TradeUpdate]` | Get trade fills for an order |
| `_request_order_status(tracked_order)` | `OrderUpdate` | Get current order status |
| `_update_balances()` | `None` | Fetch and update account balances |

### Commonly Overridden Non-Abstract Methods

| Method | Why Override |
|--------|-------------|
| `_make_trading_pairs_request()` | Exchange needs POST or special params |
| `_make_trading_rules_request()` | Exchange needs POST or special params |
| `_make_network_check_request()` | Exchange needs POST or auth for health check |
| `cancel_all()` | Exchange supports batch cancel |
| `_status_polling_loop_fetch_updates()` | Custom polling logic |

---

## Appendix B: Registration Checklist

### 1. Connector (Automatic)

Place files in `hummingbot/connector/exchange/<name>/` with a valid `<name>_utils.py` containing `CENTRALIZED`, `EXAMPLE_PAIR`, `DEFAULT_FEES`, and `KEYS`.

The auto-discovery in `AllConnectorSettings.create_connector_settings()` handles the rest.

### 2. Rate Oracle (Manual)

File: `hummingbot/core/rate_oracle/rate_oracle.py`

```python
# Add import at top:
from hummingbot.core.rate_oracle.sources.<name>_rate_source import MyExchangeRateSource

# Add to RATE_ORACLE_SOURCES dict:
RATE_ORACLE_SOURCES = {
    ...
    "my_exchange": MyExchangeRateSource,
}
```

### 3. Candle Feed (Manual)

File: `hummingbot/data_feed/candles_feed/candles_factory.py`

```python
# Add import at top:
from hummingbot.data_feed.candles_feed.<name>_spot_candles.<name>_spot_candles import MyExchangeSpotCandles

# Add to _candles_map dict in CandlesFactory:
_candles_map = {
    ...
    "my_exchange": MyExchangeSpotCandles,
}
```

### Summary Registration Table

| Component | Location | Registration Type |
|-----------|----------|------------------|
| Connector | `connector/exchange/<name>/` | Automatic (file scan) |
| Rate Oracle | `core/rate_oracle/rate_oracle.py` | Manual (add to `RATE_ORACLE_SOURCES`) |
| Candle Feed | `data_feed/candles_feed/candles_factory.py` | Manual (add to `_candles_map`) |

---

## Quick Reference: File-to-Reference Mapping

| What You're Building | Best Reference File |
|---------------------|-------------------|
| Simple connector | `connector/exchange/p2b/p2b_exchange.py` |
| Mid-complexity connector | `connector/exchange/uzx/uzx_exchange.py` |
| Full-featured connector | `connector/exchange/coinstore/coinstore_exchange.py` |
| Base class contract | `connector/exchange_py_base.py` |
| Auth with passphrase | `connector/exchange/uzx/uzx_auth.py` |
| Rotating key auth | `connector/exchange/coinstore/coinstore_auth.py` |
| Rate source | `core/rate_oracle/sources/p2b_rate_source.py` |
| Candle feed | `data_feed/candles_feed/p2b_spot_candles/` |
| Test base class | `connector/test_support/exchange_connector_test.py` |
