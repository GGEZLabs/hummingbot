# Database & Hasura Changes

# Database Connections

Currently, two PostgreSQL database instances are in use — one for development and testing, and one for live production operations.

The callisto database serves as the shared persistence layer across two core Hummingbot components, each maintaining its own set of tables while operating within the same environment.

The **Hummingbot CLI** creates and tracks live orders, recording order lifecycle events in market."Order" and market."OrderStatus", and logs all trade executions and fill history in market."TradeFill", alongside real-time market data captured in market."MarketData" — all model definitions can be found at hummingbot/hummingbot/model.

The **Hummingbot Backend API** uses the database to persist metadata about launched bot instances, as well as their balance snapshots and historical performance metrics — with model definitions located at hummingbot-backend-api/models. Although both components share the same database, they each own and manage distinct tables, ensuring a clean separation of concerns between trading operations and infrastructure management.

## Connection Details

| Property | Demo DB (Dev/Test) | Live DB (Production) |
| :---- | :---- | :---- |
| **Environment** | Development & Testing | Live Production |
| **Server Host** | iWeb Server | iWeb Server |
| **Local IP Address** | `<DEMO_DB_PRIVATE_IP>` | `<LIVE_DB_PRIVATE_IP>` |
| **Public IP Address** | — | `<LIVE_DB_PUBLIC_IP>` |
| **Port** | `5432` | `5432` |
| **Database** | `callisto` | `callisto` |
| **Username** | `<DB_USER>` | `<DB_USER>` |
| **Password** | `<DB_PASSWORD>` | `<DB_PASSWORD>` |
| **Schema** | `market` | `market` |

## Hasura GraphQL API

Hasura provides a real-time GraphQL layer over the PostgreSQL callisto database. It is currently consumed by the **Chain Admin Dashboard** and the **Hummingbot Dashboard**.

### Endpoints

| Property | Demo / Testing | Production / Live |
| :---- | :---- | :---- |
| **GraphQL Endpoint** | `<DEMO_HASURA_URL>` | `<LIVE_HASURA_URL>` |
| **Connected Database** | Demo PostgreSQL | Live PostgreSQL |
| **Used By** | demo Chain Admin Dashboard, demo Hummingbot Dashboard | live Chain Admin Dashboard, live Hummingbot Dashboard |

#### **Authentication**

Hasura is configured to use the **public anonymous role** for all requests.

Include the following header in every GraphQL request:

*"isAnonymous": "True"*

### **Database Schema: market (Callisto DB)**

All tracked objects reside in the market schema of the callisto database.

| Name | Type | Description |
| :---- | :---- | :---- |
| MarketData | Table | Core data table populated by the Hummingbot CLI. Records real-time bid, ask, and mid prices, order book snapshots, and account balances. |
| balance\_data\_view | View | Typed return view for the get\_balance\_data function. |
| candlestick\_data\_view | View | Typed return view for the get\_candlestick\_data function. |
| price\_change\_summary | View | Calculates price changes for a trading pair across multiple time periods using MarketData. |

Supported periods for price\_change\_summary:

* 1 Hour
* 1 Day
* 1 Week
* 1 Month
* 3 Months
* All Time

#### **Functions**

| Name | Returns | Description |
| :---- | :---- | :---- |
| get\_balance\_data | balance\_data\_view | Returns the current balance across all connected exchanges, sourced from MarketData. |
| get\_candlestick\_data | candlestick\_data\_view | Generates OHLCV candlestick data for a specified trading pair from MarketData. |
| cleanup\_old\_orders | void | Purges all order, order status, and trade fill records older than 1 day from the database. |

### Database Maintenance

#### **Function: `cleanup_old_orders`**

This function performs a scheduled purge of stale transactional records across three tables in the market schema. All rows with a timestamp older than **24 hours** are permanently deleted.

**Affected Tables:**

| Table | Timestamp Column | Retention Policy |
| :---- | :---- | :---- |
| market."Order" | creation\_timestamp | Records older than 1 day are deleted |
| market."OrderStatus" | timestamp | Records older than 1 day are deleted |
| market."TradeFill" | timestamp | Records older than 1 day are deleted |

#### **Scheduled Job: cleanup\_1\_day\_old\_orders\_job (Currently not working)**

A recurring database job that automatically invokes the cleanup\_old\_orders function to maintain database hygiene and prevent unbounded table growth.

| Property | Value |
| :---- | :---- |
| **Job Name** | cleanup\_1\_day\_old\_orders\_job |
| **SQL Command** | SELECT market.cleanup\_old\_orders(); |
| **Schedule** | Every **24 hours** |
| **Purpose** | Purge stale order and trade records older than 1 day |
