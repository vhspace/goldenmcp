"""ENS and onchain MCP registry SDK."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from web3 import Web3

logger = logging.getLogger(__name__)

REGISTRY_ABI = [
    {
        "inputs": [
            {"name": "name", "type": "string"},
            {"name": "mcpEndpoint", "type": "string"},
            {"name": "agentUri", "type": "string"},
            {"name": "ensName", "type": "string"},
        ],
        "name": "register",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "capability", "type": "string"},
            {"name": "dataScoreBps", "type": "uint16"},
            {"name": "pathScoreBps", "type": "uint16"},
            {"name": "tokenEfficiencyBps", "type": "uint16"},
            {"name": "compositeBps", "type": "uint16"},
            {"name": "failed", "type": "bool"},
            {"name": "walrusBlobId", "type": "string"},
        ],
        "name": "updateCapabilityScore",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "getRecord",
        "outputs": [
            {
                "components": [
                    {"name": "name", "type": "string"},
                    {"name": "mcpEndpoint", "type": "string"},
                    {"name": "agentUri", "type": "string"},
                    {"name": "ensName", "type": "string"},
                    {"name": "lastAttestationId", "type": "string"},
                    {"name": "lastTranscriptHash", "type": "bytes32"},
                    {"name": "exists", "type": "bool"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "capability", "type": "string"},
        ],
        "name": "getCapabilityScore",
        "outputs": [
            {
                "components": [
                    {"name": "dataScoreBps", "type": "uint16"},
                    {"name": "pathScoreBps", "type": "uint16"},
                    {"name": "tokenEfficiencyBps", "type": "uint16"},
                    {"name": "compositeBps", "type": "uint16"},
                    {"name": "failed", "type": "bool"},
                    {"name": "walrusBlobId", "type": "string"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

ENS_RESOLVER_ABI = [
    {
        "inputs": [{"name": "node", "type": "bytes32"}, {"name": "key", "type": "string"}],
        "name": "text",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    }
]


class IdentitySettings(BaseSettings):
    arc_rpc_url: str = ""
    arc_registry_address: str = ""
    ens_rpc_url: str = ""
    marketplace_wallet_private_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


class MCPRegistration(BaseModel):
    agent_id: int
    name: str
    mcp_endpoint: str
    agent_uri: str
    ens_name: str
    # CAI inference id + bytes32 transcript hash (response digest) of the last attestation.
    last_attestation_id: str = ""
    last_transcript_hash: str = ""


def score_to_bps(score: float) -> int:
    return int(round(max(0.0, min(1.0, score)) * 10000))


def _format_bytes32(value: bytes | bytearray | str) -> str:
    """0x-prefix a bytes32; return '' for the all-zero (unset) value."""
    raw = value.hex() if isinstance(value, (bytes, bytearray)) else str(value).replace("0x", "")
    return f"0x{raw}" if raw and int(raw, 16) != 0 else ""


class RegistryClient:
    def __init__(self, settings: IdentitySettings | None = None):
        self.settings = settings or IdentitySettings()
        if not self.settings.arc_rpc_url:
            raise EnvironmentError("ARC_RPC_URL is required")
        if not self.settings.arc_registry_address:
            raise EnvironmentError("ARC_REGISTRY_ADDRESS is required")
        self.w3 = Web3(Web3.HTTPProvider(self.settings.arc_rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to Arc RPC: {self.settings.arc_rpc_url}")
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.settings.arc_registry_address),
            abi=REGISTRY_ABI,
        )
        logger.info("RegistryClient connected registry=%s", self.settings.arc_registry_address)

    def _account(self):
        if not self.settings.marketplace_wallet_private_key:
            raise EnvironmentError("MARKETPLACE_WALLET_PRIVATE_KEY required for writes")
        return self.w3.eth.account.from_key(self.settings.marketplace_wallet_private_key)

    def register(
        self, name: str, mcp_endpoint: str, agent_uri: str, ens_name: str
    ) -> int:
        account = self._account()
        tx = self.contract.functions.register(name, mcp_endpoint, agent_uri, ens_name).build_transaction(
            {
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 500000,
                "chainId": self.w3.eth.chain_id,
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"register transaction failed: {tx_hash.hex()}")
        logger.info("registered MCP %s tx=%s", name, tx_hash.hex())
        return self.contract.functions.nextAgentId().call() - 1

    def update_score(
        self,
        agent_id: int,
        capability: str,
        *,
        data_score: float,
        path_score: float,
        token_efficiency: float,
        composite: float,
        failed: bool,
        walrus_blob_id: str,
    ) -> str:
        account = self._account()
        tx = self.contract.functions.updateCapabilityScore(
            agent_id,
            capability,
            score_to_bps(data_score),
            score_to_bps(path_score),
            score_to_bps(token_efficiency),
            score_to_bps(composite),
            failed,
            walrus_blob_id,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": self.w3.eth.get_transaction_count(account.address),
                "gas": 500000,
                "chainId": self.w3.eth.chain_id,
            }
        )
        signed = account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        if receipt.status != 1:
            raise RuntimeError(f"updateCapabilityScore failed: {tx_hash.hex()}")
        return tx_hash.hex()

    def get_record(self, agent_id: int) -> MCPRegistration:
        rec = self.contract.functions.getRecord(agent_id).call()
        return MCPRegistration(
            agent_id=agent_id,
            name=rec[0],
            mcp_endpoint=rec[1],
            agent_uri=rec[2],
            ens_name=rec[3],
            last_attestation_id=rec[4],
            last_transcript_hash=_format_bytes32(rec[5]),
        )

    def list_agent_ids(self, max_id: int = 100) -> list[int]:
        next_id = self.contract.functions.nextAgentId().call()
        return list(range(1, min(next_id, max_id)))


class ENSClient:
    """Resolve ENS text records via Ethereum RPC."""

    def __init__(self, rpc_url: str | None = None):
        url = rpc_url or os.environ.get("ENS_RPC_URL", "")
        if not url:
            raise EnvironmentError("ENS_RPC_URL is required")
        self.w3 = Web3(Web3.HTTPProvider(url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to ENS RPC: {url}")

    def resolve_text(self, name: str, key: str) -> str:
        """Resolve ENS text record via universal resolver."""
        # Use eth_call to universal resolver - simplified via namehash + public resolver
        node = self.w3.ens.namehash(name)
        resolver = self.w3.ens.get_resolver(name)
        if resolver is None:
            raise LookupError(f"No resolver for ENS name: {name}")
        text_fn = resolver.functions.text(node, key)
        return text_fn.call()

    def resolve_agent_context(self, name: str) -> dict[str, Any]:
        raw = self.resolve_text(name, "agent-context")
        return json.loads(raw)

    def resolve_eval_blob(self, name: str) -> str:
        return self.resolve_text(name, "goldenmcp/eval-blob")

    def resolve_mcp_endpoint(self, name: str) -> str:
        return self.resolve_text(name, "agent-endpoint[mcp]")
