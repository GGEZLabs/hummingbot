import hashlib
from typing import Any, Dict

import grpc
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Changes, Bip44Coins

# Cryptography & Keys
from ecdsa import SECP256k1, SigningKey
from ecdsa.util import sigencode_string

# Protobuf Imports (cosmospy-protobuf)
from google.protobuf.any_pb2 import Any as ProtoAny
from pyinjective.proto.cosmos.auth.v1beta1 import auth_pb2, query_pb2 as auth_query, query_pb2_grpc as auth_grpc
from pyinjective.proto.cosmos.bank.v1beta1 import (
    query_pb2 as bank_query,
    query_pb2_grpc as bank_grpc,
    tx_pb2 as bank_tx,
)
from pyinjective.proto.cosmos.base.v1beta1 import coin_pb2
from pyinjective.proto.cosmos.crypto.secp256k1 import keys_pb2 as secp_keys
from pyinjective.proto.cosmos.tx.signing.v1beta1 import signing_pb2
from pyinjective.proto.cosmos.tx.v1beta1 import service_pb2, service_pb2_grpc, tx_pb2

from hummingbot.strategy_v2.utils.Icosmos_grpc_client import IChainClient


class CosmosGrpcClient(IChainClient):
    def __init__(self, grpc_url: str, chain_id: str):
        self.grpc_url = grpc_url
        self.chain_id = chain_id

        # Initialize Channel
        self.channel = grpc.insecure_channel(self.grpc_url)

        # Initialize Stubs
        self.auth_stub = auth_grpc.QueryStub(self.channel)
        self.bank_stub = bank_grpc.QueryStub(self.channel)
        self.tx_stub = service_pb2_grpc.ServiceStub(self.channel)

    def get_balance(self, address: str, denom: str) -> int:
        try:
            req = bank_query.QueryBalanceRequest(address=address, denom=denom)
            resp = self.bank_stub.Balance(req)
            return int(resp.balance.amount) if resp.balance.amount else 0
        except grpc.RpcError as e:
            print(f"Error fetching balance: {e}")
            return 0

    def get_account_info(self, address: str) -> Dict[str, Any]:
        try:
            req = auth_query.QueryAccountRequest(address=address)
            resp = self.auth_stub.Account(req)

            # Parse the Any account wrapper
            account = auth_pb2.BaseAccount.FromString(resp.account.value)
            return {"account_number": account.account_number, "sequence": account.sequence, "pub_key": account.pub_key}
        except grpc.RpcError as e:
            print(f"Error fetching account info: {e}")
            raise

    def _derive_key_pair(self, mnemonic: str):
        """Helper to derive private key and pubkey bytes from mnemonic."""
        seed = Bip39SeedGenerator(mnemonic).Generate()
        bip44 = Bip44.FromSeed(seed, Bip44Coins.COSMOS)
        wallet = bip44.Purpose().Coin().Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(0)

        private_key_bytes = wallet.PrivateKey().Raw().ToBytes()
        sk = SigningKey.from_string(private_key_bytes, curve=SECP256k1)
        vk = sk.get_verifying_key()
        public_key_bytes = vk.to_string("compressed")

        return sk, public_key_bytes

    def send_tokens(
        self,
        sender_mnemonic: str,
        from_address: str,
        to_address: str,
        amount: int,
        denom: str,
        memo: str = "",
        gas_limit: int = 200_000,
        fee_amount: int = 200_000,
    ) -> str:

        # 1. Fetch Account Info
        acc_info = self.get_account_info(from_address)
        account_number = acc_info["account_number"]
        sequence = acc_info["sequence"]

        # 2. Derive Keys
        sk, public_key_bytes = self._derive_key_pair(sender_mnemonic)

        # 3. Build MsgSend
        msg = bank_tx.MsgSend(
            from_address=from_address, to_address=to_address, amount=[coin_pb2.Coin(denom=denom, amount=str(amount))]
        )

        msg_any = ProtoAny()
        msg_any.type_url = "/cosmos.bank.v1beta1.MsgSend"
        msg_any.value = msg.SerializeToString()

        # 4. Build TxBody
        tx_body = tx_pb2.TxBody(messages=[msg_any], memo=memo)
        tx_body_bytes = tx_body.SerializeToString(deterministic=True)

        # 5. Build PubKey
        pubkey_any = ProtoAny()
        pubkey_any.type_url = "/cosmos.crypto.secp256k1.PubKey"
        pubkey_any.value = secp_keys.PubKey(key=public_key_bytes).SerializeToString()

        # 6. Signer Info
        signer_info = tx_pb2.SignerInfo(
            public_key=pubkey_any,
            mode_info=tx_pb2.ModeInfo(single=tx_pb2.ModeInfo.Single(mode=signing_pb2.SIGN_MODE_DIRECT)),
            sequence=sequence,
        )

        # 7. Auth Info
        fee = tx_pb2.Fee(amount=[coin_pb2.Coin(denom=denom, amount=str(fee_amount))], gas_limit=gas_limit)
        auth_info = tx_pb2.AuthInfo(signer_infos=[signer_info], fee=fee)
        auth_info_bytes = auth_info.SerializeToString(deterministic=True)

        # 8. SignDoc
        sign_doc = tx_pb2.SignDoc(
            body_bytes=tx_body_bytes,
            auth_info_bytes=auth_info_bytes,
            chain_id=self.chain_id,
            account_number=account_number,
        )
        sign_bytes = sign_doc.SerializeToString(deterministic=True)
        digest = hashlib.sha256(sign_bytes).digest()

        # 9. Sign
        signature = sk.sign_digest(digest, sigencode=sigencode_string)

        # 10. Broadcast
        tx_raw = tx_pb2.TxRaw(body_bytes=tx_body_bytes, auth_info_bytes=auth_info_bytes, signatures=[signature])
        tx_raw_bytes = tx_raw.SerializeToString(deterministic=True)

        resp = self.tx_stub.BroadcastTx(
            service_pb2.BroadcastTxRequest(tx_bytes=tx_raw_bytes, mode=service_pb2.BroadcastMode.BROADCAST_MODE_SYNC)
        )

        if resp.tx_response.code != 0:
            raise Exception(f"Tx Failed: {resp.tx_response.raw_log}")

        return resp.tx_response.txhash
