import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.p2b import p2b_constants as CONSTANTS
from hummingbot.connector.exchange.p2b.p2b_auth import P2bAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.p2b.p2b_exchange import P2bExchange


class P2bAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 1800  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 30.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: P2bAuth,
        trading_pairs: List[str],
        connector: "P2bExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth: P2bAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = CONSTANTS.WSS_URL
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.

        P2b does not require any channel subscription.

        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            symbols = [
                await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                for trading_pair in self._trading_pairs
            ]
            # TODO : THIS wont work p2b ws does not support multiple symbols for DEPTH_EVENT_TYPE
            for symbol in symbols:
                order_book_subscribe_payload = {
                    "method": f"{CONSTANTS.DEPTH_EVENT_TYPE}.{CONSTANTS.SUBSCRIBE_METHOD}",
                    "params": [symbol, CONSTANTS.DEPTH_LIMIT, CONSTANTS.DEPTH_INTERVAL],
                    "id": 1,
                }
                order_book_subscribe_request: WSJSONRequest = WSJSONRequest(payload=order_book_subscribe_payload)
                await websocket_assistant.send(order_book_subscribe_request)

            trade_subscribe_payload = {
                "method": f"{CONSTANTS.DEALS_EVENT_TYPE}.{CONSTANTS.SUBSCRIBE_METHOD}",
                "params": [f"{symbol}" for symbol in symbols],
                "id": 2,
            }
            trade_subscribe_request: WSJSONRequest = WSJSONRequest(payload=trade_subscribe_payload)
            await websocket_assistant.send(trade_subscribe_request)

            self.logger().info("Subscribed to public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to order book trading and delta streams...", exc_info=True
            )
            raise

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
