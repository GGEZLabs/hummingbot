from decimal import Decimal

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict
from hummingbot.strategy_v2.controllers.controller_base import ControllerConfigBase


class VolumePumperConfigBase(ControllerConfigBase):
    controller_type: str = "market_making"
    strategy_name: str = "volume_pumper"
    exchange: str = Field(
        default="coinstore",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Exchange where the bot will trade",
        },
    )
    trading_pair: str = Field(
        default="GGEZ1-USDT",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Trading pair in which the bot will place orders",
        },
    )
    order_lower_amount: int = Field(
        default=500,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Lower value for order amount (in base asset , GGEZ1)",
        },
    )
    order_upper_amount: int = Field(
        default=2000,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Upper value for order amount (in base asset , GGEZ1)",
        },
    )
    delay_order_time: int = Field(
        default=120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Delay time between orders (in seconds)",
        },
    )
    max_random_delay: int = Field(
        default=120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Maximum random delay to be add to delay_order_time (in seconds)",
        },
    )
    balance_loss_threshold: Decimal = Field(
        default=Decimal(0),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Balance loss threshold (in quote asset , USDT)",
        },
    )
    minimum_ask_bid_spread: Decimal = Field(
        default=Decimal(10),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Minimum ask bid spread (basis points)",
        },
    )
    periodic_report_interval: float = Field(
        default=0,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "The interval for periodic report (in hours)",
        },
    )
    connector_name: str = exchange
    static_support: Decimal = Field(
        default=Decimal(0.0780),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Static support level price (in quote asset , USDT)",
        },
    )
    static_resistance: Decimal = Field(
        default=Decimal(0.0787),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Static resistance level price (in quote asset , USDT)",
        },
    )
    minimum_flexible_wall_spread: Decimal = Field(
        default=Decimal(0.05),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Minimum flexible wall spread (in percentage of price , e.g. 1 for 1%)",
        },
    )
    maximum_flexible_wall_spread: Decimal = Field(
        default=Decimal(0.1),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Maximum flexible wall spread (in percentage of price , e.g. 1 for 1%)",
        },
    )

    order_levels_steps: float = Field(
        default=1,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Order levels steps (in percentage of price , e.g. 1 for 1%)",
        },
    )
    max_allowed_depth: float = Field(
        default=100,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Maximum allowed orders size depth between static and flexible walls in (base currency , GGEZ1)",
        },
    )
    minimum_phase_period: float = Field(
        default=604800, description="The minimum period for a phase in seconds.", ge=0  # 1 week
    )
    maximum_phase_period: float = Field(
        default=1814400, description="The maximum period for a phase in seconds.", ge=0  # 3 weeks
    )
    minimum_phase_price_change_perc: Decimal = Field(
        default=Decimal("0.01"), description="The minimum price change percentage for a phase. (1 mean 1%)", ge=0
    )
    maximum_phase_price_change_perc: Decimal = Field(
        default=Decimal("5"), description="The maximum price change percentage for a phase. (1 mean 1%)", ge=0
    )
    minimum_boundaries_update_interval: float = Field(
        default=60.0, description="The minimum interval to update the boundaries in seconds.", ge=0
    )
    maximum_boundaries_update_interval: float = Field(
        default=86400, description="The maximum interval to update the boundaries in seconds.", ge=0
    )

    architect_failover_delay: float = Field(
        default=30,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Architect failover delay (delayed decisions ) (in seconds)",
        },
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.exchange, self.trading_pair)
