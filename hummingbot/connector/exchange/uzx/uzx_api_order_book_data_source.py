import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.uzx import uzx_constants as CONSTANTS, uzx_web_utils as web_utils
from hummingbot.connector.exchange.uzx.uzx_order_book import UzxOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.uzx.uzx_exchange import UzxExchange


class UzxAPIOrderBookDataSource(OrderBookTrackerDataSource):
    # FULL_ORDER_BOOK_RESET_DELTA_SECONDS = CONSTANTS.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "UzxExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.DEALS_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.DEPTH_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        params = {
            "interval": "step0",
            "depth": CONSTANTS.DEPTH_LIMIT,
        }
        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(
                path_url=CONSTANTS.DEPTH_PATH_URL.format(symbol=trading_pair), domain=self._domain
            ),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.DEPTH_PATH_URL,
        )

        return data["data"]

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        pass
        try:
            for symbol in self._trading_pairs:
                order_book_subscribe_payload = {
                    "event": CONSTANTS.SUBSCRIBE_METHOD,
                    "params": {
                        "biz": CONSTANTS.SUBSCRIBE_TYPE,
                        "type": f"{CONSTANTS.SUBSCRIBE_TYPE}.{self._snapshot_messages_queue_key}",
                        "symbol": symbol,
                        "interval": "0",
                    },
                    "zip": False,
                }
                order_book_subscribe_request: WSJSONRequest = WSJSONRequest(payload=order_book_subscribe_payload)
                await ws.send(order_book_subscribe_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def _connected_websocket_assistant(self) -> WSAssistant:
        ws: WSAssistant = await self._api_factory.get_ws_assistant()
        await ws.connect(ws_url=CONSTANTS.PUBLIC_WSS_URL, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = UzxOrderBook.snapshot_message_from_exchange(
            snapshot, snapshot_timestamp, metadata={"trading_pair": trading_pair}
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        {
            "id": 744238,
            "ts": 1743670720867,
            "type": "swap.XRPUSDT.fills",
            "product_name": "XRPUSDT",
            "data": [
                {
                    "vol": "4536",
                    "ts": 1743670720867,
                    "id": 7442380000,
                    "price": "2.0503",
                    "direction": "buy"
                }
            ]
        }
        """
        if "result" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message.get("product_name")
            )
            for trade in raw_message["data"]:
                trade_message = UzxOrderBook.trade_message_from_exchange(trade, {"trading_pair": trading_pair})
                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        pass

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        """
        {
            'seq_id': 562,
            'id': 5837979178,
            'bids': [],
            'asks': [],
            'ts': 1751393753513,
            'version': 5837979178,
            'type': 'spot.orderBook',
            'product_name': 'GGEZ1-USDT',
            'interval': '0'
        }
        """
        if "status" not in raw_message:
            trading_pair = raw_message["product_name"]
            snapshot_timestamp: float = raw_message["ts"]
            msg = {
                "trading_pair": trading_pair,
                "cache_time": snapshot_timestamp,
                "bids": raw_message["bids"],
                "asks": raw_message["asks"],
            }
            snapshot_msg: OrderBookMessage = UzxOrderBook.snapshot_message_from_exchange(
                msg,
                snapshot_timestamp,
                metadata={
                    "trading_pair": trading_pair,
                    "channel": raw_message["type"],
                    "seqId": raw_message["seq_id"],
                    "id": raw_message["id"],
                },
            )

        message_queue.put_nowait(snapshot_msg)

    async def _process_message_for_unknown_channel(
        self, event_message: Dict[str, Any], websocket_assistant: WSAssistant
    ):
        """
        Processes a message coming from a not identified channel.
        Does nothing by default but allows subclasses to reimplement

        :param event_message: the event received through the websocket connection
        :param websocket_assistant: the websocket connection to use to interact with the exchange
        """
        if "ping" in event_message:
            await self._send_pong(websocket_assistant=websocket_assistant)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        event_type = event_message.get("type").lower() if "type" in event_message else ""
        if event_type == f"{CONSTANTS.SUBSCRIBE_TYPE}.{self._snapshot_messages_queue_key}".lower():
            return self._snapshot_messages_queue_key
        elif event_type == f"{CONSTANTS.SUBSCRIBE_TYPE}.{self._trade_messages_queue_key}".lower():
            return self._trade_messages_queue_key

        return ""

    async def _send_pong(self, websocket_assistant: WSAssistant):
        pong_request = WSJSONRequest(payload={"pong": int(self._time() * 1000)})
        await websocket_assistant.send(pong_request)
