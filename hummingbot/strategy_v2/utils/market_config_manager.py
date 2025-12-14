import json
import time
from typing import Optional

from sqlalchemy.orm import Query, Session

from hummingbot.model.market_config import MarketConfig
from hummingbot.strategy_v2.utils.market_config_types import VolumePumperMarketConfig


class MarketConfigManager:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_market_config(self, trading_pair: str, strategy_name: str) -> Optional[MarketConfig]:
        query: Query = self.db_session.query(MarketConfig).filter(
            MarketConfig.trading_pair == trading_pair, MarketConfig.strategy_name == strategy_name
        )
        market_config: Optional[MarketConfig] = query.first()

        return market_config

    def update_market_config(self, trading_pair: str, strategy_name: str, new_market_config: VolumePumperMarketConfig):
        result = (
            self.db_session.query(MarketConfig)
            .filter(
                MarketConfig.trading_pair == trading_pair,
                MarketConfig.strategy_name == strategy_name,
            )
            .update(
                {
                    "config": json.loads(new_market_config.model_dump_json()),
                    "last_updated": time.time(),
                }
            )
        )
        self.db_session.commit()
        return result > 0  # Returns True if any row was updated

    def create_market_config(self, new_market_config: MarketConfig):
        self.db_session.add(new_market_config)
        self.db_session.commit()
        return True

    def is_config_exists(self, trading_pair: str, strategy_name: str) -> bool:
        if self.get_market_config(trading_pair, strategy_name):
            return True
        else:
            return False
