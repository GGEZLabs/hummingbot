import os
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData


class CustomVolumePumperConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field(
        "coinstore",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Exchange where the bot will trade",
        },
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Trading pair in which the bot will place orders",
        },
    )
    order_lower_amount: int = Field(
        500,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Lower value for order amount (in base asset , GGEZ1)",
        },
    )
    order_upper_amount: int = Field(
        2000,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Upper value for order amount (in base asset , GGEZ1)",
        },
    )
    delay_order_time: int = Field(
        120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Delay time between orders (in seconds)",
        },
    )
    max_random_delay: int = Field(
        120,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Maximum random delay to be add to delay_order_time (in seconds)",
        },
    )
    balance_loss_threshold: Decimal = Field(
        0,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Balance loss threshold (in quote asset , USDT)",
        },
    )
    minimum_ask_bid_spread: Decimal = Field(
        10,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Minimum ask bid spread (basis points)",
        },
    )
    periodic_report_interval: float = Field(
        0,
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "The interval for periodic report (in hours)",
        },
    )
