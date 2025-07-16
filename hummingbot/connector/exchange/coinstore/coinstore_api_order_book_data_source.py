import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.coinstore import coinstore_constants as CONSTANTS, coinstore_web_utils as web_utils
from hummingbot.connector.exchange.coinstore.coinstore_order_book import CoinstoreOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinstore.coinstore_exchange import CoinstoreExchange


class CoinstoreAPIOrderBookDataSource(OrderBookTrackerDataSource):
    HEARTBEAT_TIME_INTERVAL = 30.0
    TRADE_STREAM_ID = 1
    DIFF_STREAM_ID = 2
    ONE_HOUR = 60 * 60

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        trading_pairs: List[str],
        connector: "CoinstoreExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__(trading_pairs)
        self._connector = connector
        self._trade_messages_queue_key = CONSTANTS.TRADE_EVENT_TYPE
        self._diff_messages_queue_key = CONSTANTS.DIFF_EVENT_TYPE
        self._domain = domain
        self._api_factory = api_factory

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        params = {
            "depth": "20",
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL + f"/{symbol}", domain=self._domain),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.SNAPSHOT_PATH_URL,
        )

        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in self._trading_pairs
            ]

            order_book_subscribe_payload = {
                "op": "SUB",
                "channel": [f"{symbol.lower()}@{CONSTANTS.DEPTH_EVENT_TYPE}" for symbol in symbols],
                "id": 1,
            }
            trade_subscribe_payload = {
                "op": "SUB",
                "channel": [f"{symbol.lower()}@{CONSTANTS.TRADE_EVENT_TYPE}" for symbol in symbols],
                "param": {"size": 1},
                "id": 2,
            }

            order_book_subscribe_request: WSJSONRequest = WSJSONRequest(payload=order_book_subscribe_payload)
            trade_subscribe_request: WSJSONRequest = WSJSONRequest(payload=trade_subscribe_payload)
            await ws.send(order_book_subscribe_request)
            await ws.send(trade_subscribe_request)

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
        await ws.connect(
            ws_url=CONSTANTS.WSS_URL.format(self._domain), ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        return ws

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        snapshot = snapshot["data"]
        snapshot_timestamp: float = time.time()
        snapshot_msg: OrderBookMessage = CoinstoreOrderBook.snapshot_message_from_exchange(
            snapshot,
            snapshot_timestamp,
            metadata={
                "trading_pair": trading_pair,
                "channel": snapshot["channel"],
                "level": snapshot["level"],
                "instrumentId": snapshot["instrumentId"],
            },
        )
        return snapshot_msg

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["symbol"]
            )
            trade_message = CoinstoreOrderBook.trade_message_from_exchange(raw_message, {"trading_pair": trading_pair})
            message_queue.put_nowait(trade_message)
        else:
            for trade in raw_message["data"]:
                trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=trade["symbol"])
                trade_message = CoinstoreOrderBook.trade_message_from_exchange(trade, {"trading_pair": trading_pair})
                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        # if "result" not in raw_message:
        #     trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=raw_message["s"])
        #     order_book_message: OrderBookMessage = CoinstoreOrderBook.diff_message_from_exchange(
        #         raw_message, time.time(), {"trading_pair": trading_pair}
        #     )
        #     message_queue.put_nowait(order_book_message)
        ...

    async def _parse_order_book_snapshot_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "data" not in raw_message:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(
                symbol=raw_message["symbol"]
            )
            snapshot_timestamp: float = time.time()
            snapshot_msg: OrderBookMessage = CoinstoreOrderBook.snapshot_message_from_exchange(
                raw_message,
                snapshot_timestamp,
                metadata={
                    "trading_pair": trading_pair,
                    "channel": raw_message["channel"],
                    "level": raw_message["level"],
                    "instrumentId": raw_message["instrumentId"],
                },
            )

        message_queue.put_nowait(snapshot_msg)

    def _channel_originating_message(self, event_message: Dict[str, Any]) -> str:
        channel = ""
        if "result" not in event_message:
            event_type = event_message.get("T")
            if event_type == CONSTANTS.TRADE_EVENT_TYPE:
                channel = self._trade_messages_queue_key
            elif event_type == CONSTANTS.DEPTH_EVENT_TYPE:
                channel = self._diff_messages_queue_key
        return channel

    def _get_messages_queue_keys(self) -> List[str]:
        return [CONSTANTS.DEPTH_EVENT_TYPE, CONSTANTS.TRADE_EVENT_TYPE]

    async def listen_for_order_book_snapshots(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        """
        Coinstore sends always full snapshots through the depth channel. That is why they are processed here.

        :param ev_loop: the event loop the method will run in
        :param output: a queue to add the created diff messages
        """
        message_queue = self._message_queue[self._diff_messages_queue_key]
        while True:
            try:
                snapshot_event = await message_queue.get()
                await self._parse_order_book_snapshot_message(raw_message=snapshot_event, message_queue=output)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public order book updates from exchange")
