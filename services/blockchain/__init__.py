"""Blockchain service for Web3 interactions."""

import json
import logging

from web3 import Web3
from web3.constants import ADDRESS_ZERO

from config.settings import Settings

logger = logging.getLogger(__name__)

_blockchain_service: "BlockchainService | None" = None


def set_blockchain_service(service: "BlockchainService | None") -> None:
    """Enregistre le singleton chargé au lifespan (même pattern que services/ml)."""
    global _blockchain_service
    _blockchain_service = service


def get_blockchain_service() -> "BlockchainService | None":
    """Retourne le singleton (None si blockchain désactivée/indisponible)."""
    return _blockchain_service


def _is_configured_address(address: str | None) -> bool:
    """True when address is a non-zero Ethereum address."""
    if not address:
        return False
    try:
        return Web3.is_address(address) and Web3.to_checksum_address(address) != ADDRESS_ZERO
    except ValueError:
        return False


class BlockchainService:
    """Service for Web3 blockchain interactions."""

    def __init__(self, settings: Settings):
        """Initialize blockchain connection and contracts."""
        self.settings = settings
        self.w3: Web3 | None = None
        self.connected = False
        self.token_contract = None
        self.registry_contract = None
        self.optimizer_contract = None

        if settings.enable_blockchain:
            self._initialize_connection()

    def _initialize_connection(self) -> None:
        """Initialize Web3 connection and load contracts."""
        try:
            if not self.settings.rpc_url:
                logger.warning("⚠️  RPC_URL not configured - blockchain disabled")
                return

            self.w3 = Web3(Web3.HTTPProvider(self.settings.rpc_url))

            if not self.w3.is_connected():
                logger.error(f"❌ Failed to connect to blockchain at {self.settings.rpc_url}")
                return

            logger.info(f"✅ Connected to blockchain | Chain ID: {self.w3.eth.chain_id}")
            self.connected = True

            # Load contract ABIs
            self._load_contracts()

        except Exception as e:
            logger.error(f"❌ Blockchain initialization failed: {e}")
            self.connected = False

    def _load_contracts(self) -> None:
        """Load smart contract instances."""
        try:
            # Token contract
            if _is_configured_address(self.settings.token_address):
                token_abi = self._load_abi("FintechToken")
                self.token_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.settings.token_address),
                    abi=token_abi,
                )
                logger.info(f"✅ Token contract loaded: {self.settings.token_address}")

            # Registry contract
            if _is_configured_address(self.settings.registry_address):
                registry_abi = self._load_abi("FraudRegistry")
                self.registry_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.settings.registry_address),
                    abi=registry_abi,
                )
                logger.info(f"✅ Registry contract loaded: {self.settings.registry_address}")

            # Optimizer contract
            if _is_configured_address(self.settings.optimizer_address):
                optimizer_abi = self._load_abi("TransactionOptimizer")
                self.optimizer_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.settings.optimizer_address),
                    abi=optimizer_abi,
                )
                logger.info(f"✅ Optimizer contract loaded: {self.settings.optimizer_address}")

        except Exception as e:
            logger.error(f"❌ Failed to load contracts: {e}")

    def _load_abi(self, contract_name: str) -> list:
        """Load contract ABI from JSON file."""
        try:
            with open(f"abi/{contract_name}.json") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"⚠️  ABI file not found: abi/{contract_name}.json")
            return []

    def get_balance(self, address: str) -> float | None:
        """Get token balance for an address."""
        if not self.connected or not self.token_contract:
            logger.warning("⚠️  Blockchain not connected or token contract not loaded")
            return None

        try:
            checksum_addr = Web3.to_checksum_address(address)
            balance_wei = self.token_contract.functions.balanceOf(checksum_addr).call()
            return balance_wei / 10**18
        except Exception as e:
            logger.error(f"❌ Failed to get balance for {address}: {e}")
            return None

    def send_transaction(
        self,
        to_address: str,
        amount_tokens: float,
        from_address: str | None = None,
    ) -> dict | None:
        """Send tokens (requires admin key or signed transaction)."""
        if not self.connected or not self.token_contract:
            return {"error": "Blockchain not connected"}

        try:
            amount_wei = int(amount_tokens * 10**18)
            to_checksum = Web3.to_checksum_address(to_address)

            # Build transaction
            tx = self.token_contract.functions.transfer(to_checksum, amount_wei).build_transaction(
                {
                    "from": from_address or self.settings.admin_address,
                    "gas": 100000,
                    "gasPrice": self.w3.eth.gas_price,
                    "nonce": self.w3.eth.get_transaction_count(
                        from_address or self.settings.admin_address
                    ),
                }
            )

            logger.info(f"🔗 Transaction built: {amount_tokens} FTK to {to_address}")
            return {"tx": tx, "amount": amount_tokens}

        except Exception as e:
            logger.error(f"❌ Transaction building failed: {e}")
            return {"error": str(e)}

    def transfer_from_admin(self, to_address: str, amount_tokens: float) -> dict:
        """Transfert FTK signé par la clé privée admin et envoyé on-chain.

        Utilisé pour le bonus d'inscription (1 000 FTK) et les crédits
        opérés par la plateforme. Retourne {"tx_hash": ...} ou {"error": ...}.
        """
        if not self.connected or not self.token_contract:
            return {"error": "Blockchain non connectée"}
        if not self.settings.admin_private_key or not self.settings.admin_address:
            return {"error": "Clé admin non configurée"}

        try:
            admin = Web3.to_checksum_address(self.settings.admin_address)
            tx = self.token_contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                int(amount_tokens * 10**18),
            ).build_transaction(
                {
                    "from": admin,
                    "gas": 100_000,
                    "gasPrice": self.w3.eth.gas_price,
                    "nonce": self.w3.eth.get_transaction_count(admin),
                    "chainId": self.w3.eth.chain_id,
                }
            )
            signed = self.w3.eth.account.sign_transaction(
                tx, private_key=self.settings.admin_private_key
            )
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            tx_hash = self.w3.eth.send_raw_transaction(raw)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
            if receipt.status != 1:
                return {"error": "Transaction on-chain rejetée (revert)"}
            logger.info("🔗 %s FTK transférés à %s (tx %s)", amount_tokens, to_address, tx_hash.hex())
            return {"tx_hash": tx_hash.hex(), "block": receipt.blockNumber}
        except Exception as e:
            logger.error("❌ Transfert admin échoué: %s", e)
            return {"error": str(e)}

    def get_transaction_receipt(self, tx_hash: str) -> dict | None:
        """Reçu on-chain d'une transaction (None si introuvable/hors ligne)."""
        if not self.connected:
            return None
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return {
                "status": int(receipt.status),
                "block": receipt.blockNumber,
                "from": receipt["from"],
                "to": receipt["to"],
            }
        except Exception:
            return None

    def get_network_info(self) -> dict:
        """Get blockchain network information."""
        if not self.connected:
            return {"connected": False, "error": "Blockchain not connected"}

        try:
            return {
                "connected": True,
                "chain_id": self.w3.eth.chain_id,
                "latest_block": self.w3.eth.block_number,
                "gas_price": float(self.w3.eth.gas_price),
                "rpc_url": self.settings.rpc_url,
            }
        except Exception as e:
            logger.error(f"❌ Failed to get network info: {e}")
            return {"connected": False, "error": str(e)}
