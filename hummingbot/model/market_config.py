from sqlalchemy import JSON, Column, Float, String

from hummingbot.model import HummingbotBase


class MarketConfig(HummingbotBase):
    __tablename__ = "market_configs"
    trading_pair = Column(String(255), primary_key=True, nullable=False)
    strategy_name = Column(String(255), primary_key=True, nullable=False)
    config = Column(JSON, nullable=False)
    last_updated = Column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"MarketConfig(trading_pair='{self.trading_pair}', "
            f"strategy_name='{self.strategy_name}', "
            f"config={self.config}, "
            f"last_updated={self.last_updated})"
        )
