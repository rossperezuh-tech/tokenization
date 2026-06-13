"""
Optional on-chain bridge to the ComplianceRegistry.

If the platform holds the transfer agent's key (AGENT_PRIVATE_KEY) you can have
the backend push approvals straight to the registry. If not, leave these env
vars unset — the transfer agent whitelists investors from their own tooling and
this backend only mirrors status.

Env:
  CHAIN_RPC_URL          e.g. https://sepolia.base.org
  COMPLIANCE_REGISTRY    deployed ComplianceRegistry address
  AGENT_PRIVATE_KEY      the transfer agent's controller key (sensitive!)
"""

import logging
import os

logger = logging.getLogger(__name__)

REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "investor", "type": "address"},
            {"internalType": "bool", "name": "status", "type": "bool"},
        ],
        "name": "setWhitelisted",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "investor", "type": "address"},
            {"internalType": "uint64", "name": "until", "type": "uint64"},
        ],
        "name": "setLockup",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]


def onchain_enabled() -> bool:
    return bool(
        os.environ.get("CHAIN_RPC_URL")
        and os.environ.get("COMPLIANCE_REGISTRY")
        and os.environ.get("AGENT_PRIVATE_KEY")
    )


def set_whitelisted(wallet_address: str, status: bool) -> str | None:
    """Whitelist (or revoke) an investor on-chain. Returns the tx hash, or None
    if on-chain pushing isn't configured / fails (status is still mirrored in DB)."""
    if not onchain_enabled():
        logger.info("On-chain whitelist skipped (not configured): %s -> %s", wallet_address, status)
        return None
    try:
        from web3 import Web3

        w3 = Web3(Web3.HTTPProvider(os.environ["CHAIN_RPC_URL"]))
        acct = w3.eth.account.from_key(os.environ["AGENT_PRIVATE_KEY"])
        registry = w3.eth.contract(
            address=Web3.to_checksum_address(os.environ["COMPLIANCE_REGISTRY"]),
            abi=REGISTRY_ABI,
        )
        tx = registry.functions.setWhitelisted(
            Web3.to_checksum_address(wallet_address), status
        ).build_transaction({
            "from": acct.address,
            "nonce": w3.eth.get_transaction_count(acct.address),
        })
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        logger.info("Whitelist tx sent: %s", tx_hash.hex())
        return tx_hash.hex()
    except Exception as exc:
        logger.error("On-chain whitelist failed (status still saved in DB): %s", exc)
        return None
