from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.001"),
    buy_percent_fee_deducted_from_returns=True,
)


class P2bConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="p2b", const=True, client_data=None)
    p2b_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2b API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    p2b_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2b API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "p2b"


KEYS = P2bConfigMap.construct()

OTHER_DOMAINS = ["p2b_2"]
OTHER_DOMAINS_PARAMETER = {"p2b_2": "_2"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"p2b_2": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"p2b_2": DEFAULT_FEES}


class P2bUSConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="p2b_2", const=True, client_data=None)
    p2b_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2b 2 API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )
    p2b_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your P2b 2 API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        ),
    )

    class Config:
        title = "p2b_2"


OTHER_DOMAINS_KEYS = {"p2b_2": P2bUSConfigMap.construct()}
