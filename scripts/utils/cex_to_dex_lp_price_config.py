import os
from decimal import Decimal

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData


class CexToDexLpPriceConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    cex_exchange: str = Field(
        "coinstore",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "CEX where the bot take price data"),
    )
    cex_trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Trading pair in the CEX"),
    )
    dex_exchange: str = Field(
        "pancakeswapLP_binance-smart-chain_testnet",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Dex where the bot will provide liquidity"),
    )
    dex_trading_pair: str = Field(
        "GGEZ1-USDT",
        client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Trading pair in the Dex"),
    )
    mid_price_threshold: Decimal = Field(
        3,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Mid price change threshold as a percentage (Enter 1 to indicate 1%)"
        ),
    )
    liquidity_amount: Decimal = Field(
        100,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "Amount of liquidity to provide in Dex ( in quote asset , USDT)"
        ),
    )
    upper_lower_price_spread: Decimal = (
        Field(
            1,
            client_data=ClientFieldData(
                prompt_on_new=True,
                prompt=lambda mi: "The upper lower price spread of the liquidity? (Enter 1 to indicate 1%)",
            ),
        ),
    )
    check_price_interval: Decimal = Field(
        300,
        client_data=ClientFieldData(
            prompt_on_new=True, prompt=lambda mi: "The interval for checking price (in seconds)"
        ),
    )
    fee_tier: str = Field(
        "LOWEST",
        client_data=ClientFieldData(
            prompt_on_new=True,
            prompt=lambda mi: "On which fee tier do you want to provide liquidity on? (LOWEST/LOW/MEDIUM/HIGH)",
        ),
    )
