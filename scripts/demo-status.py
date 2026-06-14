#!/usr/bin/env python3
"""GoldenMCP live demo status — on-chain scores, wallet balances, explorer links.

Run AFTER the live demo so a judge can verify everything on-chain:
  - per-MCP capability scores read live from the Arc MCPRegistry
  - native + USDC balances for the demo wallets
  - clickable arcscan links for the registry, USDC, wallets, and last attestation tx

Usage:
  set -a; . ./.env; set +a
  ./scripts/demo-status.py
  ./scripts/demo-status.py --tx 0x<hash>   # also print a link for a specific tx
"""

from __future__ import annotations

import argparse
import os
import sys

from eth_account import Account
from web3 import Web3

SCAN = "https://testnet.arcscan.app"
USDC_DECIMALS = 6

# (agentId, name, [capabilities to show])
MCPS = [
    (1, "lifi", ["quote", "route"]),
    (2, "1inch", ["quote", "swap"]),
    (3, "odos", ["quote", "swap"]),
    (4, "jupiter", ["quote", "positions"]),
    (5, "kyberswap", ["quote", "route"]),
]

REGISTRY_ABI = [
    {"name": "getCapabilityScore", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "uint256"}, {"type": "string"}],
     "outputs": [{"name": "", "type": "tuple", "components": [
         {"name": "dataScoreBps", "type": "uint16"},
         {"name": "pathScoreBps", "type": "uint16"},
         {"name": "tokenEfficiencyBps", "type": "uint16"},
         {"name": "compositeBps", "type": "uint16"},
         {"name": "failed", "type": "bool"},
         {"name": "walrusBlobId", "type": "string"}]}]},
    {"name": "records", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "uint256"}],
     "outputs": [{"type": "string"}, {"type": "string"}, {"type": "string"}, {"type": "string"},
                 {"name": "lastAttestationId", "type": "string"},
                 {"name": "lastTranscriptHash", "type": "bytes32"}, {"type": "bool"}]},
    {"name": "nextAgentId", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
]

USDC_ABI = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
]


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _addr_from_key(key: str) -> str | None:
    if not key:
        return None
    try:
        return Account.from_key(key).address
    except Exception:
        return None


def _link(kind: str, value: str) -> str:
    return f"{SCAN}/{kind}/{value}"


def main() -> int:
    ap = argparse.ArgumentParser(description="GoldenMCP demo on-chain status")
    ap.add_argument("--tx", action="append", default=[], help="extra tx hash to link (repeatable)")
    args = ap.parse_args()

    rpc = _env("ARC_RPC_URL")
    registry = _env("ARC_REGISTRY_ADDRESS")
    usdc = _env("ARC_USDC_ADDRESS")
    if not (rpc and registry):
        print("ARC_RPC_URL and ARC_REGISTRY_ADDRESS required (run: set -a; . ./.env; set +a)", file=sys.stderr)
        return 1

    w3 = Web3(Web3.HTTPProvider(rpc))
    if not w3.is_connected():
        print(f"cannot connect to Arc RPC {rpc}", file=sys.stderr)
        return 1
    registry = Web3.to_checksum_address(registry)
    reg = w3.eth.contract(address=registry, abi=REGISTRY_ABI)

    print("=" * 72)
    print(f"  GoldenMCP — Arc testnet (chainId {w3.eth.chain_id})")
    print("=" * 72)
    print(f"  MCPRegistry : {registry}")
    print(f"              {_link('address', registry)}")
    if usdc:
        usdc = Web3.to_checksum_address(usdc)
        print(f"  USDC        : {usdc}")
        print(f"              {_link('address', usdc)}")

    # ---- Wallets ----
    wallets = [
        ("Score publisher (seller)", _addr_from_key(_env("MARKETPLACE_WALLET_PRIVATE_KEY"))),
        ("x402 payee", _env("X402_PAYEE_ADDRESS") or None),
        ("Demo payer (buyer)", _env("DEMO_PAYER_ADDRESS") or None),
        ("Eval wallet", _env("EVM_EVAL_ADDRESS") or _addr_from_key(_env("WALLET_PRIVATE_KEY"))),
    ]
    usdc_c = w3.eth.contract(address=usdc, abi=USDC_ABI) if usdc else None
    print("\n--- Wallets ---")
    seen = set()
    for label, addr in wallets:
        if not addr:
            print(f"  {label:26}: (not configured)")
            continue
        addr = Web3.to_checksum_address(addr)
        if addr in seen:
            print(f"  {label:26}: {addr}  (same as above)")
            continue
        seen.add(addr)
        native = w3.eth.get_balance(addr) / 1e18
        bal = ""
        if usdc_c:
            try:
                raw = usdc_c.functions.balanceOf(addr).call()
                bal = f"  USDC={raw / 10 ** USDC_DECIMALS:,.6f}"
            except Exception as e:
                bal = f"  USDC=(err {e})"
        print(f"  {label:26}: {addr}")
        print(f"  {'':26}  native={native:.6f}{bal}")
        print(f"  {'':26}  {_link('address', addr)}")

    # ---- Scores ----
    print("\n--- Capability scores (live from registry) ---")
    for ag, name, caps in MCPS:
        for cap in caps:
            try:
                s = reg.functions.getCapabilityScore(ag, cap).call()
            except Exception as e:
                print(f"  {name}/{cap}: read error {e}")
                continue
            comp, data, path, tok, failed, blob = s[3], s[0], s[1], s[2], s[4], s[5]
            if not blob and comp == 0:
                continue  # unpublished
            flag = " FAILED" if failed else ""
            print(f"  {name + '/' + cap:18}: {comp / 100:5.1f}%  "
                  f"(data={data / 100:.0f} path={path / 100:.0f} tok={tok / 100:.0f}){flag}")
            if blob:
                print(f"  {'':18}  walrus={blob}")

    # ---- Attestation records ----
    print("\n--- Latest attestation per MCP ---")
    for ag, name, _caps in MCPS:
        try:
            r = reg.functions.records(ag).call()
        except Exception as e:
            print(f"  {name}: {e}")
            continue
        att = r[4] or "(none)"
        th = r[5].hex()
        th = "" if set(th) <= {"0"} else f"0x{th}"
        print(f"  {name:10}: attestationId={att}")
        if th:
            print(f"  {'':10}  transcriptHash={th}")

    # ---- Extra tx links ----
    if args.tx:
        print("\n--- Transactions ---")
        for tx in args.tx:
            print(f"  {tx}")
            print(f"    {_link('tx', tx)}")

    print("\n" + "=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
