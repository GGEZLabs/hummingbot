import hashlib
import hmac
import json
from collections import OrderedDict
import math
import time
from typing import Any, Dict, List

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class CoinstoreAuth(AuthBase):
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
        if request.method == RESTMethod.GET:
            data = self._parse_params_to_str(request.params)
            data = data[1:]
        else:
            data = request.data
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(data=data))
        request.headers = headers

        return request
    

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Coinstore does not use this
        functionality
        """
        return request  # pass-through

    def _parse_params_to_str(self, params: Dict[str, Any]) -> str:
        url = "?"
        for key, value in params.items():
            url = url + str(key) + "=" + str(value) + "&"

        return url[0:-1]

    def header_for_authentication(self, data: str) -> Dict[str, str]:
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(params=data, timestamp=timestamp)
        header = {"X-CS-APIKEY": self.api_key, "X-CS-EXPIRES": str(timestamp), "X-CS-SIGN": signature}
        return header

    def _generate_Encryption_key(self, timestamp: int) -> bytes:
        expires_key = str(math.floor(timestamp / 30000))
        expires_key = expires_key.encode("utf-8")
        secret_key = self.secret_key.encode("utf-8")
        key = hmac.new(secret_key, expires_key, hashlib.sha256).hexdigest()
        key = key.encode("utf-8")
        return key

    def _generate_signature(self, params: str, timestamp: int) -> str:
        key = self._generate_Encryption_key(timestamp)
        digest = hmac.new(key, params.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest

    def websocket_login_parameters(self) -> List[str]:
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(params="LOGIN", timestamp=timestamp)
        return {"X-CS-APIKEY": self.api_key, "X-CS-EXPIRES": str(timestamp), "X-CS-SIGN": signature}
