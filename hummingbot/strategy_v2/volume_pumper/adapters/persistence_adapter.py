"""
Persistence adapter for the Volume Pumper strategy.

This adapter wraps database operations to provide a clean interface
for loading and saving market configuration.
"""

import json
import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from hummingbot.model.market_config import MarketConfig
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig

logger = logging.getLogger(__name__)


class PersistenceAdapter:
    """
    Adapter for database persistence operations.

    This class implements the IPersistenceAdapter protocol and wraps
    SQLAlchemy operations to provide a clean interface for market
    configuration persistence.

    Attributes:
        db_session: The SQLAlchemy database session
        trading_pair: The trading pair (e.g., "BTC-USDT")
        strategy_name: The strategy name for this config
    """

    def __init__(
        self,
        db_session: Session,
        trading_pair: str,
        strategy_name: str = "volume_pumper",
    ):
        """
        Initialize the persistence adapter.

        Args:
            db_session: SQLAlchemy session for database operations
            trading_pair: The trading pair
            strategy_name: The strategy name (default: "volume_pumper")
        """
        self._session = db_session
        self._trading_pair = trading_pair
        self._strategy_name = strategy_name

    @property
    def trading_pair(self) -> str:
        """Get the trading pair."""
        return self._trading_pair

    @property
    def strategy_name(self) -> str:
        """Get the strategy name."""
        return self._strategy_name

    def config_exists(self) -> bool:
        """
        Check if a configuration exists for this trading pair/strategy.

        Returns:
            True if configuration exists, False otherwise
        """
        try:
            return self._get_raw_config() is not None
        except Exception as e:
            logger.error(
                f"Error in config_exists: {type(e).__name__}: {e}"
            )
            raise

    def _get_raw_config(self) -> Optional[MarketConfig]:
        """
        Get the raw MarketConfig from database.

        Returns:
            MarketConfig or None if not found
        """
        try:
            return (
                self._session.query(MarketConfig)
                .filter(
                    MarketConfig.trading_pair == self._trading_pair,
                    MarketConfig.strategy_name == self._strategy_name,
                )
                .first()
            )
        except Exception as e:
            logger.error(
                f"Error in _get_raw_config: {type(e).__name__}: {e}"
            )
            raise

    def load_config(self) -> Optional[VolumePumperMarketConfig]:
        """
        Load the market configuration from the database.

        Returns:
            VolumePumperMarketConfig or None if not found
        """
        try:
            raw_config = self._get_raw_config()
            if raw_config is None:
                return None

            return VolumePumperMarketConfig(**raw_config.config)
        except Exception as e:
            logger.error(
                f"Error in load_config: {type(e).__name__}: {e}"
            )
            raise

    def save_config(self, config: VolumePumperMarketConfig) -> bool:
        """
        Save the market configuration to the database.

        If a configuration already exists, it will be updated.
        Otherwise, a new configuration will be created.

        Args:
            config: The market configuration to save

        Returns:
            True if saved successfully
        """
        try:
            current_time = time.time()
            config_dict = json.loads(config.model_dump_json())

            existing = self._get_raw_config()

            if existing:
                # Update existing config
                result = (
                    self._session.query(MarketConfig)
                    .filter(
                        MarketConfig.trading_pair == self._trading_pair,
                        MarketConfig.strategy_name == self._strategy_name,
                    )
                    .update({
                        "config": config_dict,
                        "last_updated": current_time,
                    })
                )
                self._session.commit()
                return result > 0
            else:
                # Create new config
                new_config = MarketConfig(
                    trading_pair=self._trading_pair,
                    strategy_name=self._strategy_name,
                    config=config_dict,
                    last_updated=current_time,
                )
                self._session.add(new_config)
                self._session.commit()
                return True
        except Exception as e:
            logger.error(
                f"Error in save_config: {type(e).__name__}: {e}"
            )
            raise

    def get_last_updated(self) -> float:
        """
        Get the timestamp of the last configuration update.

        Returns:
            Unix timestamp of last update, or 0 if not found
        """
        try:
            raw_config = self._get_raw_config()
            if raw_config is None:
                return 0
            return raw_config.last_updated
        except Exception as e:
            logger.error(
                f"Error in get_last_updated: {type(e).__name__}: {e}"
            )
            raise

    def delete_config(self) -> bool:
        """
        Delete the configuration from the database.

        Returns:
            True if deleted successfully
        """
        try:
            result = (
                self._session.query(MarketConfig)
                .filter(
                    MarketConfig.trading_pair == self._trading_pair,
                    MarketConfig.strategy_name == self._strategy_name,
                )
                .delete()
            )
            self._session.commit()
            return result > 0
        except Exception as e:
            logger.error(
                f"Error in delete_config: {type(e).__name__}: {e}"
            )
            raise

    def refresh(self) -> None:
        """
        Refresh the database session.

        This clears any cached data and ensures fresh reads.
        """
        try:
            self._session.expire_all()
        except Exception as e:
            logger.error(
                f"Error in refresh: {type(e).__name__}: {e}"
            )
            raise
