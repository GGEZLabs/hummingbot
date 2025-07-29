from typing import List

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.volume_pumper_controller_base import (
    VolumePumperConfig,
    VolumePumperControllerBase,
)
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig


class VolumePumperConfig(VolumePumperConfig):
    controller_name = "volume_pumper"
    # As this controller is a simple version of the PMM, we are not using the candles feed
    candles_config: List[CandlesConfig] = Field(default=[], client_data=ClientFieldData(prompt_on_new=False))


class VolumePumperController(VolumePumperControllerBase):
    def __init__(self, config: VolumePumperConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config

    def get_executor_config(self, order: OrderCandidate):
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            entry_price=order.price,
            amount=order.amount,
            # triple_barrier_config=self.config.triple_barrier_config,
            side=order.order_side,
        )
