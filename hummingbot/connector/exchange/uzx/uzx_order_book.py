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
            "code": 200,
            "interval": "step0",
            "msg": "success",
            "status": "ok",
            "ts": 1750844216172,
            "type": "spot.orderBook",
            "data": {
                "seq_id": 48,
                "id": 5836147386,
                "bids": [
                    [
                        "0.087",
                        "7500"
                    ]
                ],
                "asks": [
                    [
                        "0.0877",
                        "20000"
                    ]
                ],
                "ts": 1750844215897,
                "version": 5836147386,
                "type": "spot.orderBook",
                "product_name": "GGEZ1-USDT",
                "interval": "0"
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
                "bids": msg["bids"],
                "asks": msg["asks"],
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
