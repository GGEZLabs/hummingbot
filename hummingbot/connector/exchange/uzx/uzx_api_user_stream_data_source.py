import asyncio
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.uzx import uzx_constants as CONSTANTS
from hummingbot.connector.exchange.uzx.uzx_auth import UzxAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.uzx.uzx_exchange import UzxExchange


class UzxAPIUserStreamDataSource(UserStreamTrackerDataSource):

    LISTEN_KEY_KEEP_ALIVE_INTERVAL = 10  # Recommended to Ping/Update listen key to keep connection alive
    HEARTBEAT_TIME_INTERVAL = 5.0

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        auth: UzxAuth,
        trading_pairs: List[str],
        connector: "UzxExchange",
        api_factory: WebAssistantsFactory,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
    ):
        super().__init__()
        self._auth: UzxAuth = auth
        self._current_listen_key = None
        self._domain = domain
        self._api_factory = api_factory
        self._trading_pairs = trading_pairs
        self._connector = connector
        self._listen_key_initialized_event: asyncio.Event = asyncio.Event()
        self._last_listen_key_ping_ts = 0
        self._trade_messages_queue_key = CONSTANTS.DEALS_EVENT_TYPE
        self._snapshot_messages_queue_key = CONSTANTS.DEPTH_EVENT_TYPE

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        url = CONSTANTS.PUBLIC_WSS_URL
        await ws.connect(ws_url=url, ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL)
        return ws

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        pass

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
