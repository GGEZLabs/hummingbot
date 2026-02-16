import base64
import hashlib
import hmac
import time
from typing import Dict, List

import hummingbot.connector.exchange.uzx.uzx_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class UzxAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str, passphrase: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self.passphrase = passphrase

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(request))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Uzx does not use this
        functionality
        """
        return request  # pass-through

    def header_for_authentication(self, request: RESTRequest) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        signature = self._generate_signature(
            timestamp=timestamp,
            method=request.method.value,
            end_point=request.url.replace(CONSTANTS.REST_URL, ""),
            params=request.params,
            data=request.data,
        )
        headers = {
            "UZX-ACCESS-KEY": self.api_key,
            "UZX-ACCESS-SIGN": signature,
            "UZX-ACCESS-TIMESTAMP": timestamp,
            "UZX-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        return headers

    def _parse_params_to_str(self, params: Dict[str, any]) -> str:
        url = "?"
        for key, value in params.items():
            url = url + str(key) + "=" + str(value) + "&"
        return url[0:-1]

    def _generate_signature(
        self, timestamp: str, method: str, end_point: str, params: Dict[str, any], data: Dict[str, any]
    ) -> str:
        query = self._parse_params_to_str(params) if params else ""
        body = data if data else ""
        pre_hash = f"{timestamp}{method.upper()}{end_point}{query}{body}"
        signature = hmac.new(self.secret_key.encode(), pre_hash.encode(), hashlib.sha256).digest()
        return base64.b64encode(signature).decode()

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
