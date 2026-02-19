# Volume Pumper Controller

| Parameter | Type | Default | Unit | Description |
| ----- | :---- | :---- | :---- | :---- |
| **General Settings** |  |  |  |  |
| exchange | string | "coinstore" | \- | The target exchange for strategy execution. |
| trading\_pair | string | "GGEZ1-USDT" | \- | The specific asset pair for order placement. |
| **Volume Orders** |  |  |  |  |
| order\_lower\_amount | integer | 500 | Base (GGEZ1) | The minimum size for a randomized volume order. |
| order\_upper\_amount | integer | 2000 | Base (GGEZ1) | The maximum size for a randomized volume order. |
| delay\_order\_time | integer | 120 | Seconds | The base wait time between volume orders. |
| max\_random\_delay | integer | 120 | Seconds | Maximum random jitter added to the base delay. |
| minimum\_ask\_bid\_spread | Decimal | 10 | bps | Minimum spread required to trade; skips orders if tighter. |
| **Risk Management** |  |  |  |  |
| balance\_loss\_threshold | Decimal | 0 | Quote (USDT) | Max allowed loss before stopping (0 \= disabled). |
| **Architect \- Static Boundaries** |  |  |  |  |
| static\_support | Decimal | 0.0780 | Quote (USDT) | Absolute floor price; no orders placed below this. |
| static\_resistance | Decimal | 0.0787 | Quote (USDT) | Absolute ceiling price; no orders placed above this. |
| **Architect \- Flexible Walls** |  |  |  |  |
| minimum\_flexible\_wall\_spread | Decimal | 0.05 | % of Price | Minimum gap between flexible support and resistance. |
| maximum\_flexible\_wall\_spread | Decimal | 0.1 | % of Price | Maximum gap between flexible support and resistance. |
| **Architect \- Order Levels** |  |  |  |  |
| order\_levels\_steps | float | 1 | % of Price | Price increment between adjacent paywall levels. |
| max\_allowed\_depth | float | 100 | Base (GGEZ1) | Max total order size for paywall depth between walls. |
| **Architect \- Phase Timing** |  |  |  |  |
| minimum\_phase\_period | float | 604800 | Seconds | Min phase duration (Default: 1 week). |
| maximum\_phase\_period | float | 1814400 | Seconds | Max phase duration (Default: 3 weeks). |
| minimum\_phase\_price\_change\_perc | Decimal | 0.01 | % (1 \= 1%) | Minimum target price change percentage per phase. |
| maximum\_phase\_price\_change\_perc | Decimal | 5 | % (1 \= 1%) | Maximum target price change percentage per phase. |
| **Architect \- Boundaries Update** |  |  |  |  |
| minimum\_boundaries\_update\_interval | float | 60 | Seconds | Fastest frequency for recalculating flexible boundaries. |
| maximum\_boundaries\_update\_interval | float | 86400 | Seconds | Slowest frequency for recalculating boundaries. |
| architect\_failover\_delay | float | 30 | Seconds | Delay for architect decisions to prevent race conditions between multiple bot instances running on the same pair |
| **Reporting** |  |  |  |  |
| periodic\_report\_interval | float | 0 | Hours | Frequency of status reports (0 \= disabled). |

## Current Live iWeb Server Config (hbot 2.2) — Volume Only

> Volume orders only. Architect/paywall system not used.

| Parameter | Value |
| :---- | :---- |
| exchange | coinstore |
| trading\_pair | GGEZ1-USDT |
| order\_lower\_amount | 400 |
| order\_upper\_amount | 800 |
| delay\_order\_time | 40 |
| max\_random\_delay | 20 |
| balance\_loss\_threshold | 0 |
| minimum\_ask\_bid\_spread | 2.5 |
| periodic\_report\_interval | 3 |

## Current Live AWS Servers Config

| Parameter | Value |
| :---- | :---- |
| id | uzx\_volume-pumper\_0.1   \- config name  |
| controller\_name | volume\_pumper |
| controller\_type | market\_making |
| connector\_name | uzx  \- exchange name  |
| exchange | uzx \- exchange name  |
| trading\_pair | GGEZ1-USDT |
| order\_lower\_amount | 300 |
| order\_upper\_amount | 700 |
| delay\_order\_time | 30 |
| max\_random\_delay | 30 |
| minimum\_ask\_bid\_spread | 0 |
| balance\_loss\_threshold | 0 |
| static\_support | 0.087 |
| static\_resistance | 0.09 |
| minimum\_flexible\_wall\_spread | 0.15 |
| maximum\_flexible\_wall\_spread | 0.7 |
| order\_levels\_steps | 1.0 |
| max\_allowed\_depth | 200.0 |
| minimum\_phase\_period | 259200.0 |
| maximum\_phase\_period | 518400.0 |
| minimum\_phase\_price\_change\_perc | 0.01 |
| maximum\_phase\_price\_change\_perc | 0.5 |
| minimum\_boundaries\_update\_interval | 3600.0 |
| maximum\_boundaries\_update\_interval | 86400.0 |
| architect\_failover\_delay | 10.0 \- should be different for each exchange  |
| periodic\_report\_interval | 6 |
