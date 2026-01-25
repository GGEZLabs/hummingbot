# Volume Pumper - Technical Documentation

## Overview

The Volume Pumper is a trading strategy for Hummingbot that generates trading volume by creating matched buy/sell order pairs. It implements sophisticated order management, risk controls, and an "architect" system for managing order book boundaries (paywalls).

The strategy has been refactored following SOLID principles into a modular architecture with dedicated layers for domain models, protocols, utilities, adapters, and services.

---

## Table of Contents

1. [Directory Structure](#directory-structure)
2. [Architecture Overview](#architecture-overview)
3. [Strategy States](#strategy-states)
4. [Layer Descriptions](#layer-descriptions)
5. [Initialization Flow](#initialization-flow)
6. [Core Properties](#core-properties)
7. [Main Execution Loop](#main-execution-loop)
8. [Volume Order Generation](#volume-order-generation)
9. [Architect System (Paywalls)](#architect-system-paywalls)
10. [Market Config (VolumePumperMarketConfig)](#market-config-volumepumpermarketconfig)
11. [Risk Management](#risk-management)
12. [Reporting System](#reporting-system)
13. [Order Lifecycle](#order-lifecycle)
14. [Configuration Parameters](#configuration-parameters)
15. [Dependencies](#dependencies)
16. [Flow Diagrams](#flow-diagrams)
17. [Known Issues & TODOs](#known-issues--todos)

---

## Directory Structure

```
hummingbot/strategy_v2/volume_pumper/
├── __init__.py                      # Package exports
├── controller.py                    # Main controller + factory function
│
├── domain/                          # Core domain models
│   ├── __init__.py
│   ├── enums.py                     # StrategyState, MovementType
│   ├── market_config.py             # VolumePumperMarketConfig
│   └── order_plan.py                # OrderActionPlan
│
├── protocols/                       # Interface definitions
│   ├── __init__.py
│   └── interfaces.py                # All Protocol classes
│
├── utils/                           # Pure utility functions
│   ├── __init__.py
│   ├── price_utils.py               # Price calculations
│   └── math_utils.py                # Mathematical helpers
│
├── adapters/                        # Infrastructure adapters
│   ├── __init__.py
│   ├── market_data_adapter.py       # Exchange market data
│   ├── order_adapter.py             # Order operations
│   └── persistence_adapter.py       # Database operations
│
└── services/                        # Business logic services
    ├── __init__.py
    ├── volume_order_service.py      # Volume order generation
    ├── boundary_service.py          # Boundary calculations
    ├── architect_service.py         # Phase decisions
    ├── risk_service.py              # Risk management
    └── report_service.py            # Reporting and statistics
```

### Entry Point

The strategy is loaded via: `controllers/market_making/volume_pumper.py`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ENTRY POINT                                  │
│            controllers/market_making/volume_pumper.py               │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FACTORY FUNCTION                                 │
│              create_volume_pumper_controller()                       │
│    Creates all adapters and services, injects into controller        │
└─────────────────────────────────────────────────────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
│     ADAPTERS      │  │     SERVICES      │  │    CONTROLLER     │
│  Infrastructure   │  │  Business Logic   │  │   Orchestration   │
├───────────────────┤  ├───────────────────┤  ├───────────────────┤
│ MarketDataAdapter │  │ VolumeOrderService│  │                   │
│ OrderAdapter      │  │ BoundaryService   │  │  Coordinates all  │
│ PersistenceAdapter│  │ ArchitectService  │  │  services, manages│
│                   │  │ RiskService       │  │  state transitions│
│                   │  │ ReportService     │  │                   │
└───────────────────┘  └───────────────────┘  └───────────────────┘
            │                      │
            ▼                      ▼
┌───────────────────┐  ┌───────────────────┐
│    PROTOCOLS      │  │      DOMAIN       │
│    Interfaces     │  │   Core Types      │
├───────────────────┤  ├───────────────────┤
│ IMarketDataProvider│ │ StrategyState     │
│ IOrderAdapter      │ │ MovementType      │
│ IPersistenceAdapter│ │ VolumePumperMarket│
│ IVolumeOrderService│ │    Config         │
│ IBoundaryService   │ │ OrderActionPlan   │
│ IArchitectService  │ │                   │
│ IRiskService       │ │                   │
│ IReportService     │ │                   │
└───────────────────┘  └───────────────────┘
```

### SOLID Principles Applied

| Principle | Implementation                                                    |
| --------- | ----------------------------------------------------------------- |
| **SRP**   | Each service has exactly one responsibility                       |
| **OCP**   | MovementType enum is extensible; new services implement protocols |
| **LSP**   | All services implement their respective protocols                 |
| **ISP**   | Small, focused protocol interfaces                                |
| **DIP**   | Controller depends on abstractions (protocols), not concretions   |

---

## Strategy States

The strategy operates in one of five states defined by `StrategyState` enum (in `domain/enums.py`):

| State                | Description                                    |
| -------------------- | ---------------------------------------------- |
| `NOT_INITIALIZED`    | Initial state before strategy setup            |
| `RUNNING`            | Normal operation - creating volume orders      |
| `STOPPED`            | Strategy halted (usually due to balance loss)  |
| `UNDERBALANCED`      | Insufficient balance to place minimum orders   |
| `ARCHITECT_COOLDOWN` | Paused due to conflicting orders in order book |

### State Transitions

```
NOT_INITIALIZED ──(initialize_strategy())──> RUNNING
                                                │
                                                ├──(balance loss)──> STOPPED
                                                │
                                                ├──(insufficient balance)──> UNDERBALANCED
                                                │
                                                └──(conflicting orders)──> ARCHITECT_COOLDOWN
                                                                                │
                                                                                └──(cooldown expires)──> RUNNING
```

---

## Layer Descriptions

### Domain Layer (`volume_pumper/domain/`)

Contains core domain types:

| File | Contents |
|------|----------|
| `enums.py` | `StrategyState`, `MovementType` enums |
| `market_config.py` | `VolumePumperMarketConfig` model |
| `order_plan.py` | `OrderActionPlan` dataclass |

### Protocols Layer (`volume_pumper/protocols/`)

Interface definitions using Python's `Protocol` class:

| Protocol | Purpose |
|----------|---------|
| `IMarketDataProvider` | Market data access (prices, order book) |
| `IOrderAdapter` | Order operations (create, cancel) |
| `IPersistenceAdapter` | Database operations |
| `IVolumeOrderService` | Volume order generation |
| `IBoundaryService` | Boundary management |
| `IArchitectService` | Phase decisions |
| `IRiskService` | Risk monitoring |
| `IReportService` | Reporting and statistics |

### Utils Layer (`volume_pumper/utils/`)

Pure utility functions with no side effects:

| File | Functions |
|------|-----------|
| `price_utils.py` | `round_to_tick_size`, `calculate_spread_bps`, `price_in_range`, `compare_numbers` |
| `math_utils.py` | `random_decimal`, `geometric_amount`, `weighted_random_choice` |

### Adapters Layer (`volume_pumper/adapters/`)

Infrastructure adapters that wrap external systems:

| Adapter | Wraps | Purpose |
|---------|-------|---------|
| `MarketDataAdapter` | `ConnectorBase` | Market data access |
| `OrderAdapter` | `ConnectorBase` | Order operations |
| `PersistenceAdapter` | SQL session | Database operations |

### Services Layer (`volume_pumper/services/`)

Business logic implementations:

| Service | Responsibility |
|---------|----------------|
| `VolumeOrderService` | Generate matched buy/sell order pairs |
| `BoundaryService` | Calculate boundaries, detect conflicts, optimize action plans |
| `ArchitectService` | Make phase decisions, determine movement type |
| `RiskService` | Monitor balance, enforce loss thresholds |
| `ReportService` | Track statistics, generate reports |

---

## Class Architecture

### Inheritance

```
ControllerBase (hummingbot.strategy_v2.controllers.controller_base)
       │
       └── VolumePumperController (volume_pumper/controller.py)
```

### Key Components (New Architecture)

```
VolumePumperController
├── Config (VolumePumperConfigBase)
├── Adapters
│   ├── MarketDataAdapter      # Exchange market data
│   ├── OrderAdapter           # Order operations
│   └── PersistenceAdapter     # Database operations
└── Services
    ├── VolumeOrderService     # Volume order generation
    ├── BoundaryService        # Boundary calculations & conflict detection
    ├── ArchitectService       # Phase decisions
    ├── RiskService            # Risk management
    └── ReportService          # Reporting
```

### Factory Function

All dependencies are injected via `create_volume_pumper_controller()`:

```python
def create_volume_pumper_controller(
    config: VolumePumperConfigBase,
    market_data_provider,
    *args, **kwargs,
) -> VolumePumperController:
    # 1. Get connector from market data provider
    # 2. Create database session
    # 3. Create adapters
    # 4. Create services with adapters
    # 5. Return fully configured controller
```

---

## Initialization Flow

### Factory Function (`create_volume_pumper_controller`)

The controller is created via factory function with dependency injection:

```python
def create_volume_pumper_controller(
    config: VolumePumperConfigBase,
    market_data_provider,
    *args, **kwargs,
) -> VolumePumperController:
```

**Steps:**

1. Get connector from market data provider
2. Create SQL database session
3. Create adapters:
   - `MarketDataAdapter` - Wraps connector for market data
   - `OrderAdapter` - Wraps connector for order operations
   - `PersistenceAdapter` - Wraps database session
4. Create services with adapters:
   - `VolumeOrderService` - Volume order generation
   - `BoundaryService` - Boundary calculations
   - `ArchitectService` - Phase decisions
   - `RiskService` - Risk monitoring
   - `ReportService` - Statistics and reporting
5. Return fully configured controller with all services injected

### Strategy Initialization (`initialize_strategy`)

Called on first tick when state is `NOT_INITIALIZED`:

```python
def initialize_strategy(self):
```

**Steps:**

1. Get tick size from connector via `MarketDataAdapter`
2. Split trading pair into base/quote currencies
3. Get last trade price from order book
4. Initialize `RiskService` with starting balance
5. Load or create market config via `PersistenceAdapter`
6. Check and adjust for starting balance
7. Set state to `RUNNING`

### Balance Check (`check_starting_balance`)

Automatically scales configuration if balance is insufficient:

```python
minimum_available_balance = min(quote_balance / price, base_balance)
total_required = order_upper_amount + max_allowed_depth

if minimum_available_balance < total_required:
    proportion = minimum_available_balance / total_required
    # Scale down: order_upper_amount, order_lower_amount, max_allowed_depth
```

---

## Core Properties

### Timing Properties

| Property                           | Description                      |
| ---------------------------------- | -------------------------------- |
| `current_timestamp`                | Current Unix timestamp (seconds) |
| `ready_to_create_volume_orders`    | True if delay period has passed  |
| `ready_to_create_architect_orders` | True if architect can act        |
| `ready_to_create_periodic_summary` | True if report interval passed   |
| `is_architect_on_cooldown`         | True if architect is paused      |

### Readiness Calculation

```python
@property
def ready_to_create_volume_orders(self):
    elapsed = current_timestamp - last_mid_price_timestamp
    required_delay = delay_order_time + random_delay
    return elapsed >= required_delay
```

### Validation Property

```python
@property
def strategy_validations(self):
    return is_strategy_ready() and not is_balance_changed()
```

---

## Main Execution Loop

### Entry Point (`determine_executor_actions`)

Called every tick by the executor orchestrator:

```python
def determine_executor_actions(self) -> List[ExecutorAction]:
    actions = []
    actions.extend(self.create_actions_proposal())  # Create new orders
    actions.extend(self.stop_actions_proposal())    # Cancel old orders
    return actions
```

### Action Creation Flow (`create_actions_proposal`)

```
create_actions_proposal()
       │
       ├── strategy_validations? ──(No)──> return []
       │
       ├── ready_to_create_periodic_summary? ──(Yes)──> create_periodic_summary()
       │
       ├── ready_to_create_architect_orders? ──(Yes)──> generate_architect_actions()
       │                                                       │
       │                                                       └──(has actions)──> return actions
       │
       └── ready_to_create_volume_orders? ──(Yes)──> generate_volume_actions()
                                                           │
                                                           └──> return actions
```

### Priority Order

1. **Architect actions** (paywall management) - highest priority
2. **Volume actions** (regular trading) - when architect has no work

---

## Volume Order Generation

### Flow (`generate_volume_actions`)

```python
def generate_volume_actions(self) -> List[ExecutorAction]:
```

**Steps:**

1. **Calculate Order Price**

   ```python
   ask_price, bid_price, order_price = self._volume_service.calculate_order_price()
   ```

2. **Spread Validation**

   ```python
   if is_spread_below_thresholds(ask_price, bid_price):
       return []  # Spread too tight, skip
   ```

3. **Price Change Detection**

   ```python
   if is_last_trade_price_changed():
       return []  # Market moved, wait
   ```

4. **Price Position Validation**

   ```python
   if is_order_price_out_of_spread(order_price, ask_price, bid_price):
       return []  # Price outside valid range
   ```

5. **Generate Order Amount**

   ```python
   order_amount = generate_order_amount(order_price)
   # Random amount between order_lower_amount and order_upper_amount
   # Adjusted for available balance on both sides
   ```

6. **Minimum Amount Check**

   ```python
   if is_order_amount_below_minimum_order_amount(order_amount):
       return []  # Set status to UNDERBALANCED
   ```

7. **Create Order Pair**

   ```python
   create_actions = generate_volume(order_price, order_amount)
   # Returns [sell_order_action, buy_order_action]
   ```

8. **Update State**
   ```python
   last_trade_price = order_price
   self._report_service.track_trade(order_amount, order_price)
   start_orders_delay()  # Reset timer with new random delay
   ```

### Order Generation (`generate_volume`)

Creates matched buy/sell pair:

```python
def generate_volume(self, order_price, order_amount):
    order_pair = self._volume_service.generate_order_pair(order_price, order_amount)
    # Returns [sell_order_candidate, buy_order_candidate]

    return [
        CreateExecutorAction(executor_config=get_executor_config(order))
        for order in order_pair
    ]
```

---

## Architect System (Paywalls)

The "Architect" system manages order book boundaries (paywalls) - strategic price levels where orders are placed to influence the order book structure.

### Components (New Architecture)

| Service              | Role                                              |
| -------------------- | ------------------------------------------------- |
| `ArchitectService`   | Decision maker - determines boundaries and phases |
| `BoundaryService`    | Executor - manages boundary orders and conflicts  |
| `PersistenceAdapter` | Database persistence                              |

### Architect Flow (`generate_architect_actions`)

```python
def generate_architect_actions(self) -> List[ExecutorAction]:
```

**Decision Tree:**

```
generate_architect_actions()
       │
       ├── to_be_handled_orders exists?
       │      │
       │      └──(Yes)──> Log warning, start_architect_delay()
       │                  return []  # Pause for conflicting orders
       │
       ├── status == ARCHITECT_COOLDOWN?
       │      │
       │      └──(Yes)──> status = RUNNING, clear handled orders
       │                  return []  # Resume normal operation
       │
       ├── orders_action_plan exists?
       │      │
       │      └──(Yes)──> generate_paywalls_executor_actions(plan)
       │                  return actions  # Execute pending plan
       │
       ├── is_time_to_make_decision()?
       │      │
       │      └──(Yes)──> market_conf = make_decision()
       │                  return []  # Update config, act next tick
       │
       ├── is_time_to_update_boundaries()?
       │      │
       │      └──(Yes)──> update_boundaries_config()
       │                  update_orderbook_boundaries()
       │                  start_orders_delay()
       │                  return []
       │
       └── is_current_order_book_valid()?
              │
              └──(No)──> Check for shutting down executors
                         If none: update_orderbook_boundaries()
                         return []
```

### Paywall Action Execution (`generate_paywalls_executor_actions`)

Converts `OrderActionPlan` to executor actions:

```python
def generate_paywalls_executor_actions(self, order_action_plan: OrderActionPlan):
    actions = []

    # Handle cancellations
    for order_id in order_action_plan.cancellations_ids:
        if order_id in executors_by_order_id:
            # Has executor - use StopExecutorAction
            actions.append(StopExecutorAction(executor_id=...))
        else:
            # No executor - cancel directly
            connector.cancel(trading_pair, order_id)

    # Handle creations
    for order in order_action_plan.creations_candidates:
        actions.append(CreateExecutorAction(
            executor_config=get_executor_config(order, is_paywall=True)
        ))

    return actions
```

### Cooldown Mechanism

When conflicting orders detected:

```python
def start_architect_delay(self):
    update_interval = market_config.current_boundaries_update_interval
    next_architect_update_timestamp = current_timestamp + update_interval
    strategy_status = StrategyState.ARCHITECT_COOLDOWN
```

---

## Conflict Detection System

The conflict detection system protects against balance loss by identifying third-party orders within the flexible boundary range and optimizing order placement to avoid unnecessary churn.

### Key Concepts

| Concept                           | Description                                                                                          |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Conflicting Orders**            | Orders from OTHER traders within the flexible support/resistance range that could cause balance loss |
| **Order Churn**                   | Unnecessary cancellation and re-creation of orders that already exist with same price/amount         |
| **Multiple Orders at Same Price** | The system handles scenarios where multiple orders exist at the same price level                     |

### Conflicting Orders Detection (`detect_conflicting_orders`)

This method identifies third-party orders that could interfere with the paywall system:

```
detect_conflicting_orders(config)
       │
       ├── Get order book snapshot (bids, asks)
       │
       ├── Get my in-flight orders
       │
       ├── For each order book level:
       │      │
       │      ├── Is price outside flexible boundaries?
       │      │      └──(Yes)──> Skip (not a conflict)
       │      │
       │      ├── Sum ALL my orders at this price
       │      │      (handles multiple orders: [50, 150] → total = 200)
       │      │
       │      ├── Subtract my total from order book amount
       │      │
       │      └── Remaining amount > 0?
       │             │
       │             ├──(Yes)──> This is a CONFLICT (third-party order)
       │             │
       │             └──(No)──> My orders fully cover this level
       │
       └── Return (conflicting_bids, conflicting_asks)
```

**Example:**

```
Order Book at price 0.5: amount = 250
My orders at price 0.5: [50, 150] → total = 200
Remaining: 250 - 200 = 50 → CONFLICT (50 units from other trader)

Order Book at price 0.6: amount = 100
My orders at price 0.6: [100] → total = 100
Remaining: 100 - 100 = 0 → NO CONFLICT (fully my orders)
```

### Removing Already Existing Orders (`remove_already_existing_orders`)

This optimization prevents order churn by detecting orders that don't need to be recreated:

```
remove_already_existing_orders(action_plan)
       │
       ├── Get current in-flight orders grouped by price
       │
       ├── For each creation candidate in action_plan:
       │      │
       │      ├── Find my orders at same price
       │      │
       │      └── Any order has same amount?
       │             │
       │             ├──(Yes)──> Remove from creations_candidates
       │             │           Remove from cancellations_ids
       │             │           (Keep existing order as-is)
       │             │
       │             └──(No)──> Keep in action plan
       │
       └── Return optimized action_plan
```

**Example:**

```
Action Plan wants to:
  - Cancel order "abc" at price=0.5, amount=100
  - Create new order at price=0.5, amount=100

Optimization detects these are identical → removes both operations
Result: Order "abc" stays active, no network calls needed
```

### Float vs Decimal Price Handling

The order book may return prices as floats, which can cause comparison issues:

```python
# Problem: Float precision
0.1 + 0.2 == 0.3  # False in Python!

# Solution: Convert via string to Decimal
def compare_numbers(num1, operator, num2) -> bool:
    dec1 = Decimal(str(num1))  # "0.30000000000000004" → "0.3"
    dec2 = Decimal(str(num2))
    return dec1 == dec2  # True
```

### Combined Flow (`check_action_plan_conflicts`)

The main entry point combines both operations:

```
check_action_plan_conflicts(action_plan, config)
       │
       ├── Step 1: remove_already_existing_orders(action_plan)
       │           → Optimized action plan (less churn)
       │
       ├── Step 2: detect_conflicting_orders(config)
       │           → List of third-party orders in range
       │
       ├── Step 3: Convert conflicts to OrderCandidates
       │
       └── Return (optimized_plan, conflicting_orders)
              │
              └── If conflicts not empty:
                     → Trigger ARCHITECT_COOLDOWN state
                     → Skip executing action plan
                     → Resume when cooldown expires
```

### State Transition with Conflicts

```
                    ┌─────────────────────────────┐
                    │          RUNNING            │
                    │   (Normal operation)        │
                    └──────────────┬──────────────┘
                                   │
                    conflicting orders detected
                    in _refresh_order_book()
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    ARCHITECT_COOLDOWN       │
                    │  (Paused, volume orders     │
                    │   continue, paywall orders  │
                    │   skipped)                  │
                    └──────────────┬──────────────┘
                                   │
                    cooldown interval expires OR
                    conflicting orders filled/cancelled
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │          RUNNING            │
                    │   (Resume normal operation) │
                    └─────────────────────────────┘
```

---

## Market Config (VolumePumperMarketConfig)

The `VolumePumperMarketConfig` is a Pydantic model that defines the complete market state and configuration for the architect system. It controls how paywalls (boundaries) are calculated, when they update, and how price phases are managed.

**Location:** `hummingbot/strategy_v2/volume_pumper/domain/market_config.py`

### Complete Field Reference

```python
class VolumePumperMarketConfig(BaseModel):
    # Price Movement
    movement_type: str                          # "upwards", "downwards", or "sideways"

    # Static Boundaries (Fixed price levels)
    static_support: Decimal                     # Fixed support price level
    static_resistance: Decimal                  # Fixed resistance price level

    # Flexible Boundaries (Dynamic price levels)
    flexible_support: Decimal                   # Current dynamic support level
    flexible_resistance: Decimal                # Current dynamic resistance level

    # Phase Timing
    phase_start_time: float                     # Unix timestamp when current phase started
    phase_end_time: float                       # Unix timestamp when current phase should end
    minimum_phase_period: float                 # Minimum duration of a phase (seconds)
    maximum_phase_period: float                 # Maximum duration of a phase (seconds)

    # Phase Pricing
    phase_start_price: Decimal                  # Price when current phase started
    phase_end_price: Decimal                    # Target price for end of phase
    minimum_phase_price_change_perc: Decimal    # Min price change % per phase
    maximum_phase_price_change_perc: Decimal    # Max price change % per phase

    # Drift and Spread
    target_drift_per_interval: Decimal          # How much boundaries should drift per update
    minimum_flexible_wall_spread: Decimal       # Min spread between flexible boundaries
    maximum_flexible_wall_spread: Decimal       # Max spread between flexible boundaries
    current_flexible_wall_spread: Decimal       # Current spread being used

    # Update Intervals
    minimum_boundaries_update_interval: float   # Min time between boundary updates (seconds)
    maximum_boundaries_update_interval: float   # Max time between boundary updates (seconds)
    current_boundaries_update_interval: float   # Current interval being used

    # Order Configuration
    order_levels_steps: Decimal                 # Price step between order levels
```

### Field Categories

#### 1. Movement Type

| Field           | Description                                                           |
| --------------- | --------------------------------------------------------------------- |
| `movement_type` | Current market direction: `"upwards"`, `"downwards"`, or `"sideways"` |

The movement type determines how flexible boundaries drift over time:

- **Upwards**: Boundaries drift upward each interval
- **Downwards**: Boundaries drift downward each interval
- **Sideways**: Boundaries remain relatively stable

#### 2. Static Boundaries

| Field               | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `static_support`    | Absolute floor price - orders won't be placed below this   |
| `static_resistance` | Absolute ceiling price - orders won't be placed above this |

Static boundaries are **fixed** values set at initialization and don't change during strategy execution. They define the hard limits for the trading range.

```
Price
  │
  │  ══════════════════  static_resistance (ceiling)
  │
  │      ┌─────────┐
  │      │ Trading │
  │      │  Range  │
  │      └─────────┘
  │
  │  ══════════════════  static_support (floor)
  │
  └──────────────────────────────────────────────▶ Time
```

#### 3. Flexible Boundaries

| Field                 | Description                                   |
| --------------------- | --------------------------------------------- |
| `flexible_support`    | Dynamic support - moves with market phases    |
| `flexible_resistance` | Dynamic resistance - moves with market phases |

Flexible boundaries **drift** over time based on the movement type and are recalculated each boundaries update.

```
Price                    Movement: Upwards
  │
  │                           ╱── flexible_resistance
  │                      ╱───╱
  │                 ╱───╱
  │            ╱───╱
  │       ╱───╱
  │  ────╱                    ╱── flexible_support
  │                      ╱───╱
  │                 ╱───╱
  │            ╱───╱
  │       ╱───╱
  │  ────╱
  └──────────────────────────────────────────────▶ Time
```

#### 4. Phase Timing

| Field                  | Description                         |
| ---------------------- | ----------------------------------- |
| `phase_start_time`     | When the current market phase began |
| `phase_end_time`       | When the current phase should end   |
| `minimum_phase_period` | Shortest allowed phase duration     |
| `maximum_phase_period` | Longest allowed phase duration      |

Phases represent distinct market periods (e.g., an uptrend, a consolidation). The architect decides when to end a phase and start a new one based on:

- Time elapsed (`phase_end_time - phase_start_time`)
- Price movement achieved

#### 5. Phase Pricing

| Field                             | Description                       |
| --------------------------------- | --------------------------------- |
| `phase_start_price`               | Price when phase started          |
| `phase_end_price`                 | Target price for phase completion |
| `minimum_phase_price_change_perc` | Min % change required in a phase  |
| `maximum_phase_price_change_perc` | Max % change allowed in a phase   |

These control the price targets for each phase:

```
                    maximum_phase_price_change_perc
                           │
Price                      ▼
  │               ┌────────────────┐
  │               │ Target Range   │
  │               └────────────────┘
  │                      ▲
  │    minimum_phase_price_change_perc
  │
  │  ─────────────────────  phase_start_price
  │
  └──────────────────────────────────────────────▶ Time
```

#### 6. Drift and Spread

| Field                          | Description                                   |
| ------------------------------ | --------------------------------------------- |
| `target_drift_per_interval`    | How much to shift boundaries per update cycle |
| `minimum_flexible_wall_spread` | Minimum gap between support and resistance    |
| `maximum_flexible_wall_spread` | Maximum gap between support and resistance    |
| `current_flexible_wall_spread` | Active spread value being used                |

The spread controls the "width" of the tradeable zone between flexible boundaries:

```
                    flexible_resistance ───┐
                                           │ current_flexible_wall_spread
                    flexible_support ──────┘
```

#### 7. Update Intervals

| Field                                | Description                        |
| ------------------------------------ | ---------------------------------- |
| `minimum_boundaries_update_interval` | Fastest update frequency (seconds) |
| `maximum_boundaries_update_interval` | Slowest update frequency (seconds) |
| `current_boundaries_update_interval` | Active interval being used         |

Controls how often the architect recalculates and adjusts the flexible boundaries.

#### 8. Order Configuration

| Field                | Description                                   |
| -------------------- | --------------------------------------------- |
| `order_levels_steps` | Price increment between adjacent order levels |

Determines the granularity of order placement within the boundaries.

### When Fields Are Updated

The market config fields are updated at different times:

#### On Each Decision (Phase Change)

Updated by `ArchitectService.make_decision()`:

```python
# Fields updated on decision:
- movement_type              # New trend direction
- flexible_support           # Reset for new phase
- flexible_resistance        # Reset for new phase
- phase_start_time           # Current timestamp
- phase_end_time             # Calculated end time
- phase_start_price          # Current price
- phase_end_price            # Target price
- target_drift_per_interval  # Calculated drift
- current_flexible_wall_spread       # Selected spread
- current_boundaries_update_interval # Selected interval
```

#### On Each Boundaries Update

Updated by `BoundaryService.apply_drift()`:

```python
# Fields updated on boundary update:
- flexible_support     # Drifted based on movement
- flexible_resistance  # Drifted based on movement
```

#### On Strategy Initialization Only

Set once from database/config and never changed:

```python
# Static configuration fields:
- static_support
- static_resistance
- minimum_phase_period
- maximum_phase_period
- minimum_phase_price_change_perc
- maximum_phase_price_change_perc
- minimum_flexible_wall_spread
- maximum_flexible_wall_spread
- minimum_boundaries_update_interval
- maximum_boundaries_update_interval
- order_levels_steps
```

### Market Config Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    Strategy Initialization                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Load static fields from database:                        │    │
│  │ - static_support, static_resistance                      │    │
│  │ - min/max phase periods                                  │    │
│  │ - min/max price change percentages                       │    │
│  │ - min/max flexible wall spreads                          │    │
│  │ - min/max boundaries update intervals                    │    │
│  │ - order_levels_steps                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Phase Decision                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Architect analyzes market and sets:                      │    │
│  │ - movement_type (up/down/sideways)                       │    │
│  │ - phase_start_time, phase_end_time                       │    │
│  │ - phase_start_price, phase_end_price                     │    │
│  │ - target_drift_per_interval                              │    │
│  │ - current_flexible_wall_spread                           │    │
│  │ - current_boundaries_update_interval                     │    │
│  │ - initial flexible_support, flexible_resistance          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Boundaries Update Loop                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Every current_boundaries_update_interval:                │    │
│  │                                                          │    │
│  │ if movement_type == "upwards":                           │    │
│  │     flexible_support += target_drift_per_interval        │    │
│  │     flexible_resistance += target_drift_per_interval     │    │
│  │                                                          │    │
│  │ elif movement_type == "downwards":                       │    │
│  │     flexible_support -= target_drift_per_interval        │    │
│  │     flexible_resistance -= target_drift_per_interval     │    │
│  │                                                          │    │
│  │ else: # sideways                                         │    │
│  │     # No drift, boundaries stay constant                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ Check if phase should end:                               │    │
│  │ - current_time > phase_end_time?                         │    │
│  │ - price_change >= target?                                │    │
│  │                                                          │    │
│  │ If yes → Go back to Phase Decision                       │    │
│  │ If no  → Continue Boundaries Update Loop                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Visual Representation: Complete Market Config in Action

```
Price
  │
  │  ════════════════════════════════════════  static_resistance
  │
  │         Phase 1 (Upward)           │    Phase 2 (Sideways)
  │                                    │
  │                          ┌─────────┼─────────────────────────  flexible_resistance
  │                     ╱────┘         │
  │                ╱────               │
  │           ╱────                    │
  │      ╱────                         │
  │  ────                              │
  │                          ┌─────────┼─────────────────────────  flexible_support
  │                     ╱────┘         │
  │                ╱────               │
  │           ╱────                    │
  │      ╱────                         │
  │  ────                              │
  │                                    │
  │  ════════════════════════════════════════  static_support
  │
  └────────────────────────────────────┼─────────────────────────▶ Time
                                       │
                               make_decision()
                               (new phase starts)
```

### Example Configuration

```python
market_config = VolumePumperMarketConfig(
    # Current movement
    movement_type="upwards",

    # Static boundaries (absolute limits)
    static_support=Decimal("0.00100"),      # Floor: $0.00100
    static_resistance=Decimal("0.00200"),   # Ceiling: $0.00200

    # Flexible boundaries (current dynamic levels)
    flexible_support=Decimal("0.00120"),    # Current support
    flexible_resistance=Decimal("0.00150"), # Current resistance

    # Phase timing
    phase_start_time=1705000000.0,          # When phase started
    phase_end_time=1705003600.0,            # When phase should end (1 hour later)
    minimum_phase_period=1800.0,            # Min 30 minutes
    maximum_phase_period=7200.0,            # Max 2 hours

    # Phase pricing
    phase_start_price=Decimal("0.00120"),   # Started at this price
    phase_end_price=Decimal("0.00150"),     # Target price
    minimum_phase_price_change_perc=Decimal("0.02"),  # Min 2% change
    maximum_phase_price_change_perc=Decimal("0.10"),  # Max 10% change

    # Drift and spread
    target_drift_per_interval=Decimal("0.00001"),     # Drift per update
    minimum_flexible_wall_spread=Decimal("0.00005"),  # Min spread
    maximum_flexible_wall_spread=Decimal("0.00020"),  # Max spread
    current_flexible_wall_spread=Decimal("0.00010"),  # Current spread

    # Update intervals
    minimum_boundaries_update_interval=60.0,   # Min 1 minute
    maximum_boundaries_update_interval=300.0,  # Max 5 minutes
    current_boundaries_update_interval=120.0,  # Current: 2 minutes

    # Order config
    order_levels_steps=Decimal("0.00001"),     # Order granularity
)
```

---

## Risk Management

### Balance Monitoring (`is_balance_changed`)

```python
def is_balance_changed(self):
    is_safe, notification = self._risk_service.is_balance_safe()

    if not is_safe:
        logger().notify(notification)
        strategy_status = StrategyState.STOPPED
        return True

    return False
```

### Threshold Calculation

The `RiskService` compares current balance against starting balance:

- If loss exceeds `balance_loss_threshold` (in quote currency)
- Strategy stops to prevent further losses

---

## Reporting System

### Periodic Summary

Generated when `ready_to_create_periodic_summary` is True:

```python
def create_periodic_summary(self):
    report = self._report_service.generate_periodic_report()
    logger().notify(report)
```

### Report Tracking

`ReportService` tracks:

- Total orders placed
- Volume generated
- Tight spread occurrences
- Out-of-spread occurrences

### Status Report (`to_format_status`)

Displayed in Hummingbot UI:

```python
def to_format_status(self):
    status = super().to_format_status()
    status.append(self._report_service.generate_summary())
    status.append(formatted_strategy_config())
    return status
```

---

## Order Lifecycle

### Order Creation

```
1. generate_volume() creates order candidates
2. CreateExecutorAction wraps in executor config
3. Executor orchestrator processes action
4. Executor places order via connector
```

### Order Cancellation (`executors_to_cancel`)

Orders are cancelled when:

- Not currently trading (`is_trading == False`)
- Still active (`is_active == True`)
- Older than `active_order_total_lifespan` (20 seconds)
- Not a paywall order

```python
def executors_to_cancel(self):
    executors_to_refresh = filter_executors(
        executors=executors_info,
        filter_func=lambda x: (
            not x.is_trading and
            x.is_active and
            current_timestamp - x.timestamp > active_order_total_lifespan and
            not x.config.is_paywall_order
        )
    )
    return [StopExecutorAction(...) for executor in executors_to_refresh]
```

### Bulk Cancellation (`cancel_all_orders`)

Emergency cancellation of all orders:

```python
def cancel_all_orders(self):
    for order in connector.in_flight_orders:
        if order.age > active_order_total_lifespan:
            safe_ensure_future(connector.cancel_all(20))
```

---

## Configuration Parameters

| Parameter                  | Type  | Description                           |
| -------------------------- | ----- | ------------------------------------- |
| `exchange`                 | str   | Exchange connector name               |
| `trading_pair`             | str   | Trading pair (e.g., "BTC-USDT")       |
| `order_lower_amount`       | int   | Minimum order size (base currency)    |
| `order_upper_amount`       | int   | Maximum order size (base currency)    |
| `delay_order_time`         | int   | Base delay between orders (seconds)   |
| `max_random_delay`         | int   | Max additional random delay (seconds) |
| `balance_loss_threshold`   | float | Max allowed loss (quote currency)     |
| `minimum_ask_bid_spread`   | int   | Min spread in basis points            |
| `periodic_report_interval` | int   | Report frequency (hours)              |
| `max_allowed_depth`        | float | Max depth for paywalls                |

---

## Dependencies

### Volume Pumper Package Structure

```python
# Controller and factory
from hummingbot.strategy_v2.volume_pumper.controller import (
    VolumePumperController,
    create_volume_pumper_controller,
)

# Domain models
from hummingbot.strategy_v2.volume_pumper.domain.enums import StrategyState, MovementType
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig
from hummingbot.strategy_v2.volume_pumper.domain.order_plan import OrderActionPlan

# Protocols (interfaces)
from hummingbot.strategy_v2.volume_pumper.protocols.interfaces import (
    IMarketDataProvider,
    IOrderAdapter,
    IPersistenceAdapter,
    IVolumeOrderService,
    IBoundaryService,
    IArchitectService,
    IRiskService,
    IReportService,
)

# Adapters
from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.order_adapter import OrderAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.persistence_adapter import PersistenceAdapter

# Services
from hummingbot.strategy_v2.volume_pumper.services.volume_order_service import VolumeOrderService
from hummingbot.strategy_v2.volume_pumper.services.boundary_service import BoundaryService
from hummingbot.strategy_v2.volume_pumper.services.architect_service import ArchitectService
from hummingbot.strategy_v2.volume_pumper.services.risk_service import RiskService
from hummingbot.strategy_v2.volume_pumper.services.report_service import ReportService

# Utils
from hummingbot.strategy_v2.volume_pumper.utils.price_utils import (
    round_to_tick_size,
    calculate_spread_bps,
    price_in_range,
    compare_numbers,
)
from hummingbot.strategy_v2.volume_pumper.utils.math_utils import (
    random_decimal,
    geometric_amount,
    weighted_random_choice,
)
```

### External Dependencies

```python
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType, TradeType
from hummingbot.model.sql_connection_manager import SQLConnectionManager
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
```

---

## Flow Diagrams

### Complete Tick Cycle

```
                           ┌─────────────────────────┐
                           │   determine_executor    │
                           │       _actions()        │
                           └───────────┬─────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
                    ▼                                     ▼
        ┌───────────────────────┐           ┌───────────────────────┐
        │ create_actions        │           │ stop_actions          │
        │ _proposal()           │           │ _proposal()           │
        └───────────┬───────────┘           └───────────┬───────────┘
                    │                                   │
        ┌───────────┴───────────┐                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐    ┌───────────────┐       ┌───────────────────┐
│  Architect    │    │   Volume      │       │ executors_to      │
│  Actions      │    │   Actions     │       │ _cancel()         │
└───────────────┘    └───────────────┘       └───────────────────┘
```

### Volume Order Decision Tree

```
                    ┌─────────────────┐
                    │ generate_volume │
                    │ _actions()      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Calculate price │──────────────────┐
                    └────────┬────────┘                  │
                             │                           │
                             ▼                           │
                    ┌─────────────────┐                  │
                    │ Spread OK?      │──(No)──> Delay ──┘
                    └────────┬────────┘
                             │ Yes
                             ▼
                    ┌─────────────────┐
                    │ Price changed?  │──(Yes)─> Delay ──┘
                    └────────┬────────┘
                             │ No
                             ▼
                    ┌─────────────────┐
                    │ Price in spread?│──(No)──> Skip ───┘
                    └────────┬────────┘
                             │ Yes
                             ▼
                    ┌─────────────────┐
                    │ Generate amount │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Amount >= min?  │──(No)──> UNDERBALANCED
                    └────────┬────────┘
                             │ Yes
                             ▼
                    ┌─────────────────┐
                    │ Create buy/sell │
                    │ order pair      │
                    └─────────────────┘
```

---

## Known Issues & TODOs

### Issue X: ...

---

## Usage Example

```python
from hummingbot.strategy_v2.controllers.volume_pumper_controller_base import VolumePumperConfigBase
from hummingbot.strategy_v2.volume_pumper.controller import create_volume_pumper_controller

config = VolumePumperConfigBase(
    exchange="binance",
    trading_pair="BTC-USDT",
    order_lower_amount=10,
    order_upper_amount=50,
    delay_order_time=5,
    max_random_delay=3,
    balance_loss_threshold=100,
    minimum_ask_bid_spread=10,  # basis points
    periodic_report_interval=1,  # hours
    max_allowed_depth=100,
)

# Controller is created via factory function with dependency injection
controller = create_volume_pumper_controller(
    config=config,
    market_data_provider=mdp,
)
```

### Entry Point (controllers/market_making/volume_pumper.py)

```python
from hummingbot.strategy_v2.volume_pumper.controller import (
    VolumePumperController as VolumePumperControllerBase,
    create_volume_pumper_controller,
)

class VolumePumperConfig(VolumePumperConfigBase):
    controller_name: str = "volume_pumper"

class VolumePumperController(VolumePumperControllerBase):
    def __init__(self, config: VolumePumperConfig, *args, **kwargs):
        self.controller = create_volume_pumper_controller(
            config=config, *args, **kwargs
        )
```

---

## Glossary

| Term                              | Definition                                                                                             |
| --------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Paywall**                       | Strategic price level with orders placed to influence order book                                       |
| **Architect**                     | System that decides and manages paywall boundaries                                                     |
| **Volume Order**                  | Matched buy/sell pair to generate trading volume                                                       |
| **Tick Size**                     | Minimum price increment for the trading pair                                                           |
| **Basis Point**                   | 1/100th of a percent (0.01%)                                                                           |
| **Executor**                      | Component that manages individual order lifecycle                                                      |
| **Connector**                     | Exchange integration module                                                                            |
| **Static Boundary**               | Fixed price level (support/resistance) that never changes during execution                             |
| **Flexible Boundary**             | Dynamic price level that drifts over time based on movement type                                       |
| **Phase**                         | A distinct market period with specific movement direction and duration                                 |
| **Movement Type**                 | Direction of price trend: "upwards", "downwards", or "sideways"                                        |
| **Drift**                         | Gradual shift of flexible boundaries per update interval                                               |
| **Wall Spread**                   | Gap between flexible support and resistance boundaries                                                 |
| **Boundaries Update**             | Periodic recalculation of flexible boundary positions                                                  |
| **Market Config**                 | `VolumePumperMarketConfig` - complete market state for architect system                                |
| **Conflicting Order**             | Order from another trader within the flexible boundary range that could cause balance loss             |
| **Order Churn**                   | Unnecessary cancellation and re-creation of orders that already exist with same price/amount           |
| **Action Plan**                   | `OrderActionPlan` - list of order cancellations and creations to execute atomically                    |
| **Multiple Orders at Same Price** | Scenario where several orders exist at same price level; amounts must be summed for conflict detection |
| **Float-to-Decimal Conversion**   | Converting order book floats to Decimal via string to avoid precision issues in comparisons            |
