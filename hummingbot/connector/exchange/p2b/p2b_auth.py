import base64
import hashlib
import hmac
import json
from random import randint
from typing import Any, Dict

import hummingbot.connector.exchange.p2b.p2b_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class P2bAuth(AuthBase):
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
        if request.method == RESTMethod.POST:
            request.data = self.add_auth_to_params(params=json.loads(request.data), request_url=request.url)
            request.data = json.dumps(request.data, separators=(",", ":"))
        else:
            request.params = self.add_auth_to_params(params=request.params, request=request.endpoint_url)

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.header_for_authentication(data=request.data))
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. P2b does not use this
        functionality
        """
        return request  # pass-through

    def add_auth_to_params(self, params: Dict[str, Any], request_url: str) -> Dict[str, Any]:
        """
        Mandatory parameters:
        request	STRING  -> Request endpoint
        nonce	INT	    -> Timestamp in millisecond
        """

        request_params = params or {}
        request_params["request"] = request_url.replace(CONSTANTS.REST_URL, "")

        timestamp = int(self.time_provider.time() * 1e3)
        request_params["nonce"] = timestamp + randint(1, 1000)

        return request_params

    def header_for_authentication(self, data: str) -> Dict[str, str]:
        """
        X-TXC-APIKEY	    Account 'API key'
        X-TXC-PAYLOAD		Body json encoded in base64
        X-TXC-SIGNATURE		'Payload' encrypted using HMAC with SHA512 algorithm and 'API secret'
        """
        encrypted_data = base64.b64encode(data.encode("utf8")).decode("utf8")
        signature = self._generate_signature(params=encrypted_data)
        header = {
            "X-TXC-APIKEY": self.api_key,
            "X-TXC-SIGNATURE": signature,
            "X-TXC-PAYLOAD": encrypted_data,
        }
        return header

    def _generate_signature(self, params: str) -> str:
        digest = hmac.new(self.secret_key.encode("utf8"), params.encode("utf8"), hashlib.sha512).hexdigest()
        return digest
