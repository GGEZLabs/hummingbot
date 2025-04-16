import base64
import hashlib
import hmac
import time
from typing import Dict, List

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class UzxAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication())
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Uzx does not use this
        functionality
        """
        return request  # pass-through

    def header_for_authentication(self) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp)
        headers = {"apiKey": self.api_key, "signature": signature, "timestamp": timestamp}
        return headers

    def _generate_signature(self, timestamp: str) -> str:
        api_key: str = self.api_key
        secret: str = self.secret_key
        pre_hash = f"{api_key}\n{secret}\n{timestamp}"
        hmac_digest = hmac.new(secret.encode(), pre_hash.encode(), hashlib.sha1).digest()
        return base64.b64encode(hmac_digest).decode()

    def _generate_ws_signature(self, timestamp: str) -> str:
        message = timestamp + "GET" + "/api/login"
        signature = hmac.new(self.secret_key.encode(), message.encode(), hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

    def websocket_login_parameters(self) -> List[str]:
        timestamp = str(int(time.time()))
        signature = self._generate_ws_signature(timestamp)
        return {
            "event": "login",
            "params": {"type": "api", "apiKey": self.api_key, "timestamp": timestamp, "sign": signature},
        }
