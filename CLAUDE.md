# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hummingbot is an open-source framework for building and deploying automated trading bots on centralized (CEX) and decentralized (DEX) exchanges. It uses Python with Cython extensions for performance-critical components.

## Development Setup

### Initial Installation
```bash
./install              # Creates conda environment and installs dependencies
./compile              # Builds Cython extensions (required after code changes to .pyx files)
```

For dYdX support: `./install --dydx`

### Running Hummingbot
```bash
conda activate hummingbot
python bin/hummingbot.py
```

Or with a v2 strategy:
```bash
make run-v2 <config_name>
```

## Testing

### Run All Tests
```bash
make test              # Runs pytest with coverage
```

### Run Single Test File
```bash
pytest test/path/to/test_file.py
```

### Run Single Test Function
```bash
pytest test/path/to/test_file.py::TestClass::test_function -v
```

### Coverage
```bash
make run_coverage           # Runs tests and generates HTML report
make development-diff-cover # Shows coverage diff vs development branch
```

Coverage minimum: 70% overall, 80% for PR changes.

### Ignored Test Directories
Tests in these directories are currently skipped (see Makefile):
- `test/hummingbot/connector/exchange/ndax/`
- `test/hummingbot/connector/derivative/dydx_v4_perpetual/`
- `test/hummingbot/remote_iface/`
- `test/hummingbot/strategy/amm_arb/`
- `test/hummingbot/strategy/cross_exchange_market_making/`

## Code Style

- Line length: 120 characters
- Formatter: Black, autopep8
- Import sorting: isort
- Pre-commit hooks are installed automatically by `./install`

To manually run pre-commit: `pre-commit run --all-files`

## Architecture

### Main Package Structure (`hummingbot/`)

```
hummingbot/
├── client/          # CLI interface, commands, config management
├── connector/       # Exchange integrations
│   ├── exchange/    # Spot CEX connectors (binance, kucoin, okx, etc.)
│   ├── derivative/  # Perpetual/futures connectors
│   ├── gateway/     # DEX connectors via Gateway service
│   └── test_support/# Testing utilities for connectors
├── core/            # Infrastructure layer
│   ├── api_throttler/   # Rate limiting
│   ├── cpp/             # C++ optimized data structures
│   ├── data_type/       # Core data types (OrderBook, Trade, etc.)
│   ├── event/           # Event system
│   ├── rate_oracle/     # Exchange rate management
│   └── web_assistant/   # HTTP/WebSocket client
├── data_feed/       # External price feeds
├── strategy/        # Legacy strategies (v1)
├── strategy_v2/     # Modern strategy framework
│   ├── controllers/ # Trading logic controllers
│   ├── executors/   # Order execution components
│   ├── backtesting/ # Backtesting engine
│   └── models/      # Configuration models
└── scripts/         # User scripts (v2 strategies live here)
```

### Key Architectural Concepts

**Connectors**: Each exchange has a connector implementing a standard interface. Spot connectors inherit from `ExchangePyBase`, perpetual from `PerpetualDerivativePyBase`. Connectors handle REST/WebSocket communication, order management, and data streaming.

**Strategy v2 Framework**: The modern approach using:
- **Controllers**: Define trading logic (what/when to trade)
- **Executors**: Execute orders (DCA, Grid, TWAP, XEMM, Position, Arbitrage)
- **ExecutorOrchestrator**: Manages multiple executors

**Cython Extensions**: Performance-critical code in `.pyx` files (connector_base, exchange_base, clock, order_book). Run `./compile` after modifying these.

**Event System**: Components communicate via `pubsub` events. Core events defined in `hummingbot/core/event/events.py`.

### Adding a New Exchange Connector

Exchange connectors follow a standard structure in `hummingbot/connector/exchange/<exchange_name>/`:
- `<name>_exchange.py` - Main exchange class
- `<name>_api_order_book_data_source.py` - Order book streaming
- `<name>_api_user_stream_data_source.py` - User data streaming
- `<name>_auth.py` - Authentication
- `<name>_web_utils.py` - HTTP utilities
- `<name>_constants.py` - API endpoints, URLs

### Scripts Directory

User trading scripts go in `scripts/`. These are Python files that define trading logic using the v2 framework. Examples: `simple_pmm.py`, `v2_directional_rsi.py`.

## Documentation

The `docs/` folder contains all project documentation. When a user asks about any of the topics below, **always read the relevant file(s) first** before answering. Treat these files as the authoritative source of truth, taking precedence over general knowledge.

### Operational Docs

| Topic | File |
|-------|------|
| Repository overview, component list | `docs/repository-overview.md` |
| Server instances (local, iWeb, AWS) | `docs/hbot-instance.md` |
| Installation and running (source, Docker, debug) | `docs/hbot-installation-running.md` |
| AWS ECR image push/pull | `docs/aws-ecr.md` |
| Hummingbot configuration (conf_client.yml) | `docs/hbot-configuration.md` |
| Running strategies via CLI or Dashboard | `docs/running-strategies.md` |
| Running multiple bot instances | `docs/running-multiple-instances.md` |
| Important links (exchanges, APIs, resources) | `docs/important-links.md` |
| CLI clipboard copy/paste | `docs/cli-clipboard-operations.md` |
| Exchange constraints and troubleshooting | `docs/general-notes-troubleshooting.md` |
| Dev-to-production deployment workflow | `docs/development-deployment-workflow.md` |
| Linux memory management and Docker limits | `docs/memory-management.md` |
| Docker and conda command reference | `docs/useful-command-reference.md` |
| Developing a strategy (overview) | `docs/developing-a-strategy.md` |
| Database connections and Hasura GraphQL | `docs/database-hasura.md` |
| Environment variables | `docs/environment-variables.md` |
| Volume pumper controller parameters and live config | `docs/volume-pumper-controller.md` |
| Telegram bot tokens and chat IDs | `docs/telegram-tokens.md` |

### Technical Guides

| Topic | File |
|-------|------|
| Creating or developing a new exchange connector | `docs/connector-development-guide.md` |
| Creating or developing a new strategy (v1 or v2) | `docs/strategy-development-guide.md` |
| Volume pumper controller, volume trading logic | `docs/volume-pumper-controller-guide.md` |

If a question could relate to multiple files, read all relevant ones.

## Git Workflow

- Branch from `development` (not `master`)
- Branch naming: `feat/`, `fix/`, `refactor/`, `doc/`
- Commit prefix: `(feat)`, `(fix)`, `(refactor)`, `(cleanup)`, `(doc)`
- PRs go to `development` branch
- Enable "Allow edits by maintainers" on PRs
