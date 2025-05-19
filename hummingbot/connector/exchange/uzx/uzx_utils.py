from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.006"),
    taker_percent_fee_decimal=Decimal("0.003"),
    buy_percent_fee_deducted_from_returns=True,
)


class UzxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="uzx", const=True, client_data=None)
    uzx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Uzx API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    uzx_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Uzx API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "uzx"


KEYS = UzxConfigMap.construct()


OTHER_DOMAINS = ["uzx_2"]
OTHER_DOMAINS_PARAMETER = {"uzx_2": "_2"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"uzx_2": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"uzx_2": DEFAULT_FEES}


class UzxUSConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="uzx_2", const=True, client_data=None)
    uzx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Uzx 2 API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    uzx_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Uzx 2 API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "uzx_2"


OTHER_DOMAINS_KEYS = {"uzx_2": UzxUSConfigMap.construct()}
