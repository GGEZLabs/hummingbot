import os
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData


class CustomVolumePumperConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    exchange: str = Field(
        "coinstore",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will trade"),
    )
    trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Trading pair in which the bot will place orders"
        ),
    )
    order_lower_amount: int = Field(
        500,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Lower value for order amount (in base asset , GGEZ1)"
        ),
    )
    order_upper_amount: int = Field(
        2000,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Upper value for order amount (in base asset , GGEZ1)"
        ),
    )
    delay_order_time: int = Field(
        120, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Delay time between orders (in seconds)")
    )
    max_random_delay: int = Field(
        120,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Maximum random delay to be add to delay_order_time (in seconds)"
        ),
    )
    balance_loss_threshold: Decimal = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Balance loss threshold (in quote asset , USDT)"
        ),
    )
    minimum_ask_bid_spread: Decimal = Field(
        10,
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Minimum ask bid spread (basis points)"),
    )
    periodic_report_interval: float = Field(
        0,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "The interval for periodic report (in hours)"
        ),
    )
