from typing import Dict, Optional

from hummingbot.connector.exchange.uzx import uzx_constants as CONSTANTS
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class UzxOrderBook(OrderBook):

    @classmethod
    def snapshot_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: float, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange

        {
        "ask": {
            "minAmount": 0.0297786,
            "highestPrice": 92210.0,
            "symbol": "BTC/USDT",
            "lowestPrice": 85832.42,
            "maxAmount": 1.9477029,
            "items": [
                        {
                            "price": 85832.42,
                            "amount": 0.20450935
                        }
                    ],
                "direction": "SELL"
            },
        "bid": {
            "minAmount": 0.00324297,
            "highestPrice": 85832.4,
            "symbol": "BTC/USDT",
            "lowestPrice": 79503.0,
            "maxAmount": 1.9938553,
            "items": [
                        {
                            "price": 85404.55,
                            "amount": 0.22750804
                        }
                    ],
                "direction": "BUY"
            }
        }
        """

        if metadata:
            msg.update(metadata)
        return OrderBookMessage(
            OrderBookMessageType.SNAPSHOT,
            {
                "trading_pair": msg["trading_pair"],
                "update_id": int(timestamp),
                "instrument_id": int(timestamp),
                "bids": [[bid["price"], bid["amount"]] for bid in msg["bid"]["items"]],
                "asks": [[ask["price"], ask["amount"]] for ask in msg["ask"]["items"]],
            },
            timestamp=timestamp,
        )

    @classmethod
    def diff_message_from_exchange(
        cls, msg: Dict[str, any], timestamp: Optional[float] = None, metadata: Optional[Dict] = None
    ) -> OrderBookMessage:
        pass

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        {
            "vol": "4536",
            "ts": 1743670720867,
            "id": 7442380000,
            "price": "2.0503",
            "direction": "buy"
        }
        """
        if metadata:
            msg.update(metadata)
        ts = msg["ts"]
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": (
                    float(TradeType.SELL.value)
                    if msg["direction"] == CONSTANTS.TAKER_SIDE_SELL
                    else float(TradeType.BUY.value)
                ),
                "trade_id": msg["id"],
                "update_id": ts,
                "price": msg["price"],
                "amount": msg["vol"],
            },
            timestamp=ts * 1e-3,
        )
