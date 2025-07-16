from decimal import Decimal
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.006"),
    taker_percent_fee_decimal=Decimal("0.003"),
    buy_percent_fee_deducted_from_returns=True,
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    # is_spot = False
    is_trading = False

    if exchange_info.get("openTrade", None):
        is_trading = True

    # permissions_sets = exchange_info.get("permissionSets", list())
    # for permission_set in permissions_sets:
    #     # PermissionSet is a list, find if in this list we have "SPOT" value or not
    #     if "SPOT" in permission_set:
    #         is_spot = True
    #         break

    # return is_trading and is_spot
    return is_trading


class CoinstoreConfigMap(BaseConnectorConfigMap):
    connector: str = "coinstore"
    coinstore_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Coinstore API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    coinstore_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your Coinstore API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="coinstore")


KEYS = CoinstoreConfigMap.model_construct()

OTHER_DOMAINS = ["coinstore_2"]
OTHER_DOMAINS_PARAMETER = {"coinstore_2": "2"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"coinstore_2": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"coinstore_2": DEFAULT_FEES}



class Coinstore2ConfigMap(BaseConnectorConfigMap):
    connector: str = "coinstore_2"
    coinstore_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your coinstore_2 API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )
    coinstore_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": lambda cm: "Enter your coinstore_2 API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        },
    )

    model_config = ConfigDict(title="coinstore_2")


OTHER_DOMAINS_KEYS = {"coinstore_2": Coinstore2ConfigMap.construct()}
