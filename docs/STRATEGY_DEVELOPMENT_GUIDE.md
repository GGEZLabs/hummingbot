# Hummingbot Strategy Development Guide

A practical, end-to-end guide for building Scripts and Controllers in the V2 framework — covering architecture, workflow, debugging, status formatting, and best practices.

---

## Table of Contents

1. [The Inheritance Hierarchy](#1-the-inheritance-hierarchy)
2. [When to Use What](#2-when-to-use-what)
3. [Building a Script (ScriptStrategyBase)](#3-building-a-script-scriptstrategybbase)
4. [Building a V2 Script (StrategyV2Base)](#4-building-a-v2-script-strategyv2base)
5. [Building a Controller](#5-building-a-controller)
6. [The Full Data Flow](#6-the-full-data-flow)
7. [Available Executors](#7-available-executors)
8. [Formatting the `status` Command](#8-formatting-the-status-command)
9. [Debugging](#9-debugging)
10. [Best Practices](#10-best-practices)

---

## 1. The Inheritance Hierarchy

```
StrategyPyBase               (C++/Cython clock integration)
  └── ScriptStrategyBase     (simple buy/sell/cancel API)
        └── StrategyV2Base   (executor orchestrator + controllers)
```

Controllers are **not** in this hierarchy — they are separate `asyncio`-driven components that communicate with the strategy through an **async queue**.

```
RunnableBase
  └── ControllerBase         (async control loop, sends ExecutorActions)
        ├── DirectionalTradingControllerBase
        └── MarketMakingControllerBase
```

### Why Three Layers?

| Layer | Responsibility | Order API |
|---|---|---|
| `ScriptStrategyBase` | Tick-driven logic, raw orders | `self.buy()`, `self.sell()`, `self.cancel()` |
| `StrategyV2Base` | Executor orchestration, multi-controller | `CreateExecutorAction`, `StopExecutorAction` |
| `ControllerBase` | Async signal generation, loosely coupled | Sends actions via `asyncio.Queue` |

The key design insight: **Controllers run in their own async loop** and push `ExecutorAction` lists to a queue. The strategy's `listen_to_executor_actions` coroutine drains that queue every iteration. This loose coupling means a controller can be stopped, restarted, or replaced without touching the strategy.

---

## 2. When to Use What

```
Simple one-off idea, no config file needed
  → ScriptStrategyBase (scripts/my_script.py)

Multi-pair strategy with YAML config, using Executors directly
  → StrategyV2Base (scripts/my_v2_script.py)

Reusable strategy logic that can be hot-swapped or run in parallel
  → ControllerBase + StrategyV2Base via v2_with_controllers.py
```

**Rule of thumb**: Start with `ScriptStrategyBase`. When you find yourself managing order state manually (tracking fills, cancels, refreshes), switch to `StrategyV2Base` and use Executors. When your logic grows large or you need to run multiple independent strategies side-by-side, extract it into a Controller.

---

## 3. Building a Script (ScriptStrategyBase)

### File Location

```
scripts/my_pmm.py
```

### Minimal Template

```python
import os
from decimal import Decimal
from typing import Dict

from pydantic import Field
from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MyScriptConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)   # required
    exchange: str = Field("binance_paper_trade")
    trading_pair: str = Field("ETH-USDT")
    order_amount: Decimal = Field(Decimal("0.01"))


class MyScript(ScriptStrategyBase):
    """One-liner description shown in 'status'."""

    # ------------------------------------------------------------------ #
    # Class-level market declaration (overridden by init_markets)          #
    # ------------------------------------------------------------------ #
    markets = {"binance_paper_trade": {"ETH-USDT"}}

    @classmethod
    def init_markets(cls, config: MyScriptConfig):
        """Called once at start. Sets the market/connector mapping."""
        cls.markets = {config.exchange: {config.trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: MyScriptConfig):
        super().__init__(connectors)     # note: no config forwarded here
        self.config = config
        self._last_order_ts = 0

    # ------------------------------------------------------------------ #
    # Lifecycle hooks                                                       #
    # ------------------------------------------------------------------ #
    def on_tick(self):
        """Called every clock tick (~1 s) after connectors are ready."""
        if self.current_timestamp - self._last_order_ts < 15:
            return
        self._cancel_all()
        self._place_orders()
        self._last_order_ts = self.current_timestamp

    async def on_stop(self):
        """Called when the user runs 'stop'. Async, so you can await things."""
        self._cancel_all()

    # ------------------------------------------------------------------ #
    # Event callbacks (optional)                                           #
    # ------------------------------------------------------------------ #
    def did_fill_order(self, event):
        msg = f"Filled {event.trade_type.name} {event.amount} {event.trading_pair}"
        self.log_with_clock(20, msg)       # 20 = logging.INFO
        self.notify_hb_app_with_timestamp(msg)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _cancel_all(self):
        for order in self.get_active_orders(self.config.exchange):
            self.cancel(self.config.exchange, order.trading_pair, order.client_order_id)

    def _place_orders(self):
        connector = self.connectors[self.config.exchange]
        mid = connector.get_mid_price(self.config.trading_pair)
        self.buy(self.config.exchange, self.config.trading_pair,
                 self.config.order_amount, OrderType.LIMIT, mid * Decimal("0.999"))
        self.sell(self.config.exchange, self.config.trading_pair,
                  self.config.order_amount, OrderType.LIMIT, mid * Decimal("1.001"))

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Connectors not ready."
        lines = ["", "  My PMM Script"]
        lines += ["    " + l for l in self.get_balance_df().to_string(index=False).split("\n")]
        return "\n".join(lines)
```

### `init_markets` vs `markets`

- `markets` (class variable) is the **fallback** used when no config file exists.
- `init_markets` is called by the framework when a YAML config **is** provided, before the constructor runs. Override it to derive the connector list from config parameters.

### Running It

```bash
# With paper trade (no config file)
start --script my_pmm.py

# With YAML config
create --script-config my_pmm.py       # generates conf_my_pmm_1.yml
start --script my_pmm.py --conf conf_my_pmm_1.yml
```

---

## 4. Building a V2 Script (StrategyV2Base)

`StrategyV2Base` extends `ScriptStrategyBase` with:

- An `ExecutorOrchestrator` that manages typed executor components (Position, DCA, Grid, TWAP…)
- A `MarketDataProvider` for candle feeds and order book data
- A `controllers` dict for plugging in Controller modules

Use this when you want **managed order state** — the executors track fills, manage stop-loss / take-profit, and close themselves.

### Minimal Template

```python
import os
from decimal import Decimal
from typing import Dict, List, Set

from pydantic import Field
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig, TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction, StopExecutorAction, StoreExecutorAction,
)
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class MyV2Config(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    # markets and candles_config are inherited from StrategyV2ConfigBase
    order_amount_quote: Decimal = Field(Decimal("100"))


class MyV2Strategy(StrategyV2Base):

    @classmethod
    def init_markets(cls, config: MyV2Config):
        # StrategyV2Base.init_markets also loads controller markets
        super().init_markets(config)

    def __init__(self, connectors: Dict[str, ConnectorBase], config: MyV2Config):
        super().__init__(connectors, config)
        self.config = config

    # ------------------------------------------------------------------ #
    # Tick hook — StrategyV2Base.on_tick() already calls:                  #
    #   update_executors_info() + update_controllers_configs()             #
    #   + determine_executor_actions()                                     #
    # ------------------------------------------------------------------ #
    def on_tick(self):
        super().on_tick()          # ALWAYS call super
        # add custom global checks here (e.g., max drawdown)

    # ------------------------------------------------------------------ #
    # The three proposal methods you MUST implement                        #
    # ------------------------------------------------------------------ #
    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        active = self.filter_executors(
            self.get_all_executors(),
            lambda e: e.is_active
        )
        if len(active) >= 1:
            return []              # already have an open position

        connector = "binance_perpetual"
        pair = "ETH-USDT"
        price = self.market_data_provider.get_price_by_type(connector, pair)
        amount = self.config.order_amount_quote / price

        config = PositionExecutorConfig(
            timestamp=self.current_timestamp,
            connector_name=connector,
            trading_pair=pair,
            side=TradeType.BUY,
            amount=amount,
            triple_barrier_config=TripleBarrierConfig(
                stop_loss=Decimal("0.02"),
                take_profit=Decimal("0.03"),
                time_limit=60 * 30,
            ),
        )
        return [CreateExecutorAction(controller_id="main", executor_config=config)]

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        # Stop executors that are done but still active (edge cases)
        return []

    def store_actions_proposal(self) -> List[StoreExecutorAction]:
        # The base class already handles buffer management; override if needed
        return super().store_actions_proposal()

    def format_status(self) -> str:
        # The base class format_status() already renders balances,
        # executors table, and performance summary.
        return super().format_status()
```

### `on_tick` call chain

```
clock tick
  └── ScriptStrategyBase.tick()
        └── checks ready_to_trade
              └── ScriptStrategyBase.on_tick()   (if you override without super())
                  → StrategyV2Base.on_tick()
                        ├── update_executors_info()
                        ├── update_controllers_configs()   (reloads YAML every 10 s)
                        └── determine_executor_actions()
                              ├── create_actions_proposal()   ← YOU implement
                              ├── stop_actions_proposal()     ← YOU implement
                              └── store_actions_proposal()    ← base handles buffer
```

---

## 5. Building a Controller

Controllers are the right abstraction when:

- Your strategy logic is complex enough to deserve its own async loop
- You want to run it in parallel with other controllers under one script
- You want hot-reload capability (the YAML is re-read every `config_update_interval`)

### File Location

Controllers live in the `controllers/` package:

```
hummingbot/strategy_v2/controllers/<type>/<name>.py
```

Where `<type>` is `directional_trading`, `market_making`, or `generic`.

### Step 1: Define the Config

```python
from decimal import Decimal
from pydantic import Field
from hummingbot.core.data_type.common import MarketDict
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase


class MyControllerConfig(ControllerConfigBase):
    controller_name: str = "my_controller"
    controller_type: str = "generic"            # matches directory name

    connector_name: str = Field(
        default="binance_perpetual",
        json_schema_extra={
            "prompt": "Connector name: ",
            "prompt_on_new": True,
        }
    )
    trading_pair: str = Field(
        default="ETH-USDT",
        json_schema_extra={
            "prompt": "Trading pair: ",
            "prompt_on_new": True,
        }
    )
    rsi_period: int = Field(
        default=14,
        json_schema_extra={
            "is_updatable": True,   # can be hot-reloaded without restart
        }
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """Tell the strategy which markets this controller needs."""
        return markets.add_or_update(self.connector_name, self.trading_pair)
```

**Key field metadata flags:**

| Flag | Effect |
|---|---|
| `"prompt_on_new": True` | Shown when running `create --script-config` |
| `"is_updatable": True` | Field can change via YAML hot-reload without restarting |

### Step 2: Implement the Controller

```python
import asyncio
from decimal import Decimal
from typing import List

import pandas as pd

from hummingbot.core.data_type.common import TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig, TripleBarrierConfig,
)
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction, ExecutorAction,
)


class MyController(ControllerBase):
    """RSI-based directional controller."""

    def __init__(
        self,
        config: MyControllerConfig,
        market_data_provider: MarketDataProvider,
        actions_queue: asyncio.Queue,
    ):
        super().__init__(config, market_data_provider, actions_queue, update_interval=1.0)
        self.config: MyControllerConfig = config

    # ------------------------------------------------------------------ #
    # Async lifecycle                                                       #
    # ------------------------------------------------------------------ #
    async def on_start(self):
        """Called once when the control loop starts."""
        self.logger().info(f"MyController starting on {self.config.trading_pair}")
        # Initialize any candle feeds not covered by the strategy config
        self.market_data_provider.initialize_candles_feed(
            CandlesConfig(
                connector=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                interval="1m",
                max_records=self.config.rsi_period + 10,
            )
        )

    def on_stop(self):
        """Called when stop() is invoked."""
        self.logger().info("MyController stopped.")

    # ------------------------------------------------------------------ #
    # Core interface — both MUST be implemented                            #
    # ------------------------------------------------------------------ #
    async def update_processed_data(self):
        """
        Pull market data and compute indicators.
        Results are stored in self.processed_data (plain dict).
        Called every `update_interval` seconds by the control loop,
        but ONLY when market_data_provider is ready AND
        executors_update_event is set.
        """
        candles = self.market_data_provider.get_candles_df(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            interval="1m",
            max_records=self.config.rsi_period + 10,
        )
        if candles is None or len(candles) < self.config.rsi_period:
            self.processed_data = {"signal": 0, "features": pd.DataFrame()}
            return

        # Compute RSI
        delta = candles["close"].diff()
        gain = delta.clip(lower=0).ewm(com=self.config.rsi_period - 1, adjust=False).mean()
        loss = (-delta).clip(lower=0).ewm(com=self.config.rsi_period - 1, adjust=False).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        last_rsi = float(rsi.iloc[-1])

        signal = 0
        if last_rsi < 30:
            signal = 1    # oversold → long
        elif last_rsi > 70:
            signal = -1   # overbought → short

        features = pd.DataFrame({"RSI": [last_rsi], "Signal": [signal]})
        self.processed_data = {"signal": signal, "features": features}

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Translate processed_data into a list of ExecutorActions.
        Keep this method slim — delegate to helpers.
        """
        actions: List[ExecutorAction] = []
        signal = self.processed_data.get("signal", 0)

        if signal != 0 and self._can_open(signal):
            actions.append(self._build_create_action(signal))

        return actions

    # ------------------------------------------------------------------ #
    # Status display                                                       #
    # ------------------------------------------------------------------ #
    def to_format_status(self) -> List[str]:
        """
        Lines returned here are inserted into the main strategy status output
        under the "Controller: <id>" section.
        """
        features = self.processed_data.get("features", pd.DataFrame())
        if features.empty:
            return ["  Waiting for data..."]
        lines = [f"  RSI: {features['RSI'].iloc[0]:.1f}  Signal: {features['Signal'].iloc[0]}"]
        return lines

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #
    def _can_open(self, signal: int) -> bool:
        trade_type = TradeType.BUY if signal > 0 else TradeType.SELL
        active = self.filter_executors(
            self.executors_info,
            lambda e: e.is_active and e.side == trade_type,
        )
        return len(active) == 0

    def _build_create_action(self, signal: int) -> CreateExecutorAction:
        connector = self.config.connector_name
        pair = self.config.trading_pair
        price = self.market_data_provider.get_price_by_type(connector, pair)
        amount = self.config.total_amount_quote / price
        side = TradeType.BUY if signal > 0 else TradeType.SELL

        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=PositionExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=connector,
                trading_pair=pair,
                side=side,
                amount=amount,
                triple_barrier_config=TripleBarrierConfig(
                    stop_loss=Decimal("0.02"),
                    take_profit=Decimal("0.03"),
                    time_limit=60 * 30,
                ),
            ),
        )
```

### Step 3: Wire it into the Strategy

Use the generic `v2_with_controllers.py` script — no custom script needed:

```bash
# 1. Create controller config
create --controller-config my_controller   # generates in conf/controllers/

# 2. Create strategy config pointing at it
create --script-config v2_with_controllers.py
# When prompted for controllers_config, enter: my_controller_config_1.yml

# 3. Run
start --script v2_with_controllers.py --conf conf_v2_with_controllers_1.yml
```

Or build a custom strategy script that wires it manually:

```python
class MyStrategy(StrategyV2Base):
    def __init__(self, connectors, config):
        super().__init__(connectors, config)
        # Controllers listed in config.controllers_config are loaded automatically
        # by initialize_controllers() in __init__

    def create_actions_proposal(self):
        return []   # controllers handle everything

    def stop_actions_proposal(self):
        return []
```

---

## 6. The Full Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Clock (every ~1s)                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │ tick()
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    StrategyV2Base.on_tick()                      │
│  1. update_executors_info()  → pulls report from orchestrator   │
│  2. update_controllers_configs()  → hot-reloads YAML (10s)      │
│  3. determine_executor_actions()  → create/stop/store           │
│     └─ execute_action() on orchestrator directly                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              ControllerBase.control_loop()  [asyncio]           │
│  Every update_interval (default 1s):                            │
│  1. update_processed_data()  → fetch data, compute signals      │
│  2. determine_executor_actions()  → build action list           │
│  3. send_actions()  → puts actions into actions_queue           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ asyncio.Queue
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│       StrategyV2Base.listen_to_executor_actions()  [asyncio]    │
│  Drains the queue and calls:                                    │
│  executor_orchestrator.execute_actions(actions)                 │
│  → creates / stops executors                                    │
│  → updates controller.executors_info                            │
│  → sets controller.executors_update_event                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     ExecutorOrchestrator                        │
│  Manages: PositionExecutor, DCAExecutor, GridExecutor,          │
│           TWAPExecutor, XEMMExecutor, ArbitrageExecutor,        │
│           OrderExecutor                                          │
│  Each executor runs its own async loop and places real orders   │
│  via the connector.                                             │
└─────────────────────────────────────────────────────────────────┘
```

**Important**: The `executors_update_event` in `ControllerBase` is the synchronization point. The controller's `control_task` only runs `update_processed_data` when the event is set. After sending actions to the queue, the event is cleared and will only be set again after the strategy loop processes the actions and updates `executors_info`. This prevents the controller from flooding the queue with duplicate actions.

---

## 7. Available Executors

| Executor | Config Class | Use Case |
|---|---|---|
| `PositionExecutor` | `PositionExecutorConfig` | Single position with triple-barrier (SL/TP/time) |
| `DCAExecutor` | `DCAExecutorConfig` | Dollar-cost averaging entry over multiple levels |
| `GridExecutor` | `GridExecutorConfig` | Grid trading between price levels |
| `TWAPExecutor` | `TWAPExecutorConfig` | Time-weighted average price execution |
| `XEMMExecutor` | `XEMMExecutorConfig` | Cross-exchange market making |
| `ArbitrageExecutor` | `ArbitrageExecutorConfig` | Spot arbitrage between two venues |
| `OrderExecutor` | `OrderExecutorConfig` | Low-level single order placement |

### PositionExecutorConfig (most common)

```python
from hummingbot.strategy_v2.executors.position_executor.data_types import (
    PositionExecutorConfig, TripleBarrierConfig, TrailingStop,
)

config = PositionExecutorConfig(
    timestamp=self.current_timestamp,
    connector_name="binance_perpetual",
    trading_pair="BTC-USDT",
    side=TradeType.BUY,
    amount=Decimal("0.001"),          # in BASE asset
    leverage=10,
    triple_barrier_config=TripleBarrierConfig(
        stop_loss=Decimal("0.02"),            # 2% SL
        take_profit=Decimal("0.04"),          # 4% TP
        time_limit=60 * 60,                   # 1 hour max
        trailing_stop=TrailingStop(
            activation_price=Decimal("0.02"), # activate after +2%
            trailing_delta=Decimal("0.01"),   # trail by 1%
        ),
    ),
)
```

### Querying Executor State

```python
from hummingbot.strategy_v2.models.base import RunnableStatus

# In a Script (StrategyV2Base):
all_executors = self.get_all_executors()
active = self.filter_executors(all_executors, lambda e: e.is_active)
trading = self.filter_executors(all_executors, lambda e: e.is_trading)
done = self.filter_executors(all_executors, lambda e: e.is_done)

# In a Controller:
active = self.filter_executors(self.executors_info, lambda e: e.is_active)
```

`ExecutorInfo` key attributes:

| Attribute | Type | Description |
|---|---|---|
| `id` | str | Unique executor ID |
| `status` | `RunnableStatus` | NOT_STARTED / RUNNING / TERMINATED |
| `is_active` | bool | Running and not done |
| `is_trading` | bool | Has an open order on the exchange |
| `is_done` | bool | Closed (SL/TP/time/manual) |
| `side` | `TradeType` | BUY or SELL |
| `net_pnl_quote` | Decimal | Realized PnL in quote |
| `close_type` | `CloseType` | STOP_LOSS / TAKE_PROFIT / TIME_LIMIT / etc. |

---

## 8. Formatting the `status` Command

The `status` command calls `format_status()` on the active strategy. The return value is a plain string displayed in the terminal.

### In a Script (ScriptStrategyBase)

```python
def format_status(self) -> str:
    if not self.ready_to_trade:
        return "Connectors not ready."

    lines = []

    # --- Balances (built-in helper) ---
    balance_df = self.get_balance_df()
    lines += ["", "  Balances:"]
    lines += ["    " + l for l in balance_df.to_string(index=False).split("\n")]

    # --- Custom KPIs ---
    lines += ["", "  Strategy state:"]
    lines += [f"    Last signal: {self._last_signal}"]
    lines += [f"    Open orders: {len(self.get_active_orders(self.config.exchange))}"]

    return "\n".join(lines)
```

### In a V2 Script (StrategyV2Base)

The base `format_status()` already renders:
- Balances table
- Active orders table
- Per-controller section (calls `controller.to_format_status()`)
- Executors table (last 6, with age, PnL, status)
- Positions table (for perpetual)
- Global performance summary

Call `super().format_status()` and append your own sections:

```python
def format_status(self) -> str:
    base = super().format_status()
    extra = "\n".join([
        "",
        "=" * 60,
        "  MY CUSTOM METRICS",
        f"  Total ticks: {self._tick_count}",
        f"  Max drawdown: {self._max_drawdown:.2f}%",
    ])
    return base + extra
```

### In a Controller (`to_format_status`)

The strategy calls `controller.to_format_status()` and includes the result in its own output. Return a `List[str]`, one entry per line:

```python
def to_format_status(self) -> List[str]:
    lines = []
    features = self.processed_data.get("features", pd.DataFrame())

    if features.empty:
        return ["  Waiting for candle data..."]

    # Use format_df_for_printout for aligned tables
    from hummingbot.client.ui.interface_utils import format_df_for_printout
    lines.append(format_df_for_printout(features.tail(5), table_format="psql"))

    lines.append(f"  Active executors: {len(self.filter_executors(self.executors_info, lambda e: e.is_active))}")
    return lines
```

### Tips for Clean Status Output

```python
# Align numbers in columns
lines.append(f"  {'PnL':<20} {pnl:>10.4f} USDT")
lines.append(f"  {'Volume':<20} {volume:>10.2f} USDT")

# Section dividers
lines.append("  " + "-" * 50)

# Conditional warning
if pnl < Decimal("-10"):
    lines.append("  *** WARNING: PnL below threshold ***")
```

---

## 9. Debugging

### Method 1: Structured Logging (Recommended for Production)

All strategy classes have `self.logger()` (or `self.log_with_clock()`):

```python
# Standard Python logging levels
self.logger().debug("Detailed trace: %s", some_dict)    # only visible at DEBUG level
self.logger().info("Order placed: %s", order_id)
self.logger().warning("Spread too tight, skipping tick")
self.logger().error("Unexpected error", exc_info=True)  # includes stack trace

# Show in Hummingbot UI notification bar
self.notify_hb_app_with_timestamp("RSI signal triggered: BUY")

# Clock-prefixed log (includes timestamp in terminal)
self.log_with_clock(logging.INFO, "Custom message")
```

Set log level in `conf/hummingbot_logs.yml`:

```yaml
loggers:
  hummingbot.strategy:
    level: DEBUG
```

Or at runtime:

```
config log_level DEBUG
```

### Method 2: VSCode Debugger (Full Breakpoint Support)

The repository ships a pre-configured `.vscode/launch.json`. To use it:

**1. Open the workspace in VSCode**

```bash
code /home/srassaggez/hummingbot_new/hummingbot
```

**2. Edit `.vscode/launch.json`** to point at your script:

```jsonc
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug My Script",
      "type": "debugpy",
      "request": "launch",
      "program": "${workspaceRoot}/bin/hummingbot_quickstart.py",
      "console": "integratedTerminal",
      "python": "/home/srassaggez/miniconda3/envs/hummingbot/bin/python",
      "args": [
        "-p", "a",                          // password (paper trade doesn't need real one)
        "-f", "my_script.py",               // script file name
        "-c", "conf_my_script_1.yml"        // config file (optional)
      ]
    }
  ]
}
```

**3. Set breakpoints** in your `on_tick`, `update_processed_data`, or `determine_executor_actions` methods.

**4. Press F5** to start debugging. The terminal will show Hummingbot's output; breakpoints will pause execution as normal.

> **Note on async code**: VSCode's debugpy handles `async` functions correctly. You can set breakpoints inside `update_processed_data` and `on_start` without issues.

### Method 3: `--headless` Mode for CI / Script Testing

```bash
python bin/hummingbot_quickstart.py \
  --headless \
  -p a \
  -f my_script.py \
  -c conf_my_script_1.yml
```

Headless mode suppresses the TUI and logs everything to stdout, useful for piping to files or running in CI.

### Common Debugging Patterns

**Print processed data every N ticks:**

```python
def on_tick(self):
    super().on_tick()
    if int(self.current_timestamp) % 60 == 0:   # every ~60 s
        self.logger().info(f"processed_data snapshot: {self.processed_data}")
```

**Verify candle feed is ready:**

```python
async def update_processed_data(self):
    candles = self.market_data_provider.get_candles_df(
        connector_name=self.config.connector_name,
        trading_pair=self.config.trading_pair,
        interval="1m",
        max_records=20,
    )
    if candles is None:
        self.logger().warning("Candle feed not ready yet")
        self.processed_data = {"signal": 0, "features": pd.DataFrame()}
        return
    self.logger().debug(f"Got {len(candles)} candles, latest close: {candles['close'].iloc[-1]}")
```

**Trace executor lifecycle:**

```python
def did_create_buy_order(self, event):
    self.logger().info(f"Buy order created: {event.order_id}")

def did_fill_order(self, event):
    self.logger().info(f"Filled {event.amount} @ {event.price}")

def did_cancel_order(self, event):
    self.logger().info(f"Cancelled: {event.order_id}")
```

---

## 10. Best Practices

### Keep the Controller Slim

The controller should only:
1. Fetch data (`update_processed_data`)
2. Decide what to do (`determine_executor_actions`)
3. Return actions — never place orders directly

Move all business logic (signal calculation, risk checks, position sizing) into separate methods or service classes. The `VolumePumperController` is a good example — it delegates entirely to `ArchitectService`, `RiskService`, `VolumeOrderService`, etc.

```python
# BAD: logic in determine_executor_actions
def determine_executor_actions(self):
    candles = self.market_data_provider.get_candles_df(...)
    delta = candles["close"].diff()
    # ... 40 more lines ...

# GOOD: logic separated
async def update_processed_data(self):
    self.processed_data = self._compute_signals()

def determine_executor_actions(self):
    signal = self.processed_data["signal"]
    if signal != 0 and self._can_open(signal):
        return [self._build_action(signal)]
    return []
```

### Always Guard for Data Not Ready

```python
async def update_processed_data(self):
    candles = self.market_data_provider.get_candles_df(...)
    if candles is None or len(candles) < self.config.min_candles:
        self.processed_data = {"signal": 0, "features": pd.DataFrame()}
        return
    # safe to proceed
```

### Prefer `is_updatable` Fields for Tuning Parameters

Any parameter you might want to adjust while the bot runs should be marked `"is_updatable": True`. This lets you edit the YAML and have the change picked up within 10 seconds (the `config_update_interval`) without restarting.

```python
risk_pct: Decimal = Field(
    default=Decimal("0.02"),
    json_schema_extra={"is_updatable": True},
)
```

### Use `filter_executors` Consistently

Never iterate `self.executors_info` manually with custom `if` chains. Use the static `filter_executors` with a lambda to make intent clear and keep code DRY:

```python
# Prefer this:
open_buys = self.filter_executors(
    self.executors_info,
    lambda e: e.is_active and e.side == TradeType.BUY
)

# Over this:
open_buys = [e for e in self.executors_info if e.is_active and e.side == TradeType.BUY]
```

### Idempotent `on_tick` / `control_task`

Both methods are called repeatedly. They must be safe to call with no side effects when conditions aren't met. Never assume anything was done in a previous tick — always read current state.

```python
def create_actions_proposal(self):
    # Always re-query state, never cache between ticks
    active = self.filter_executors(self.get_all_executors(), lambda e: e.is_active)
    if len(active) >= self.config.max_open_positions:
        return []
    ...
```

### Handle Errors Gracefully in `update_processed_data`

If an exception escapes `update_processed_data`, the control loop logs it and continues — but `processed_data` may be stale. Always initialize `processed_data` to a safe default at the top:

```python
async def update_processed_data(self):
    self.processed_data = {"signal": 0, "features": pd.DataFrame()}   # safe default first
    try:
        # ... real computation ...
        self.processed_data = {"signal": computed_signal, "features": df}
    except Exception as e:
        self.logger().error(f"Signal computation failed: {e}", exc_info=True)
        # processed_data remains at safe default
```

### One Config Class Per File

The framework auto-discovers the config and controller classes by scanning the module for subclasses of `ControllerConfigBase` and `ControllerBase`. Keep exactly one of each per file to avoid ambiguity.

### Never Call `buy()` / `sell()` from a Controller

Controllers don't have access to connectors directly. All order placement goes through `ExecutorAction` → `ExecutorOrchestrator` → `Executor` → `connector`. Bypassing this breaks the PnL tracking, executor lifecycle, and the database record.

### Minimum Complexity Checklist

Before adding a new abstraction, ask:
- [ ] Does this logic change independently from the rest? (separate class)
- [ ] Is it used in more than one place? (shared helper)
- [ ] Will it need hot-reload? (mark `is_updatable`)
- [ ] Does it need its own async timing? (separate controller, not tick logic)

If the answer to all four is "no", keep it inline.
