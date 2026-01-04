from abc import ABC, abstractmethod
from typing import Any, Dict


class IChainClient(ABC):
    """
    Interface for interacting with Cosmos SDK chains via gRPC.
    """

    @abstractmethod
    def get_balance(self, address: str, denom: str) -> int:
        """Fetch the balance of a specific denomination for an address."""
        pass

    @abstractmethod
    def get_account_info(self, address: str) -> Dict[str, Any]:
        """Fetch account number and sequence."""
        pass

    @abstractmethod
    def send_tokens(
        self,
        sender_mnemonic: str,
        from_address: str,
        to_address: str,
        amount: int,
        denom: str,
        memo: str = "",
        gas_limit: int = 1000000,
        fee_amount: int = 1000000,
    ) -> str:
        """Send tokens and return the transaction hash."""
        pass
