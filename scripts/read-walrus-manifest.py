import json
import os
import urllib.request

from web3 import Web3

w3 = Web3(Web3.HTTPProvider(os.environ["ARC_RPC_URL"]))
R = Web3.to_checksum_address(os.environ["ARC_REGISTRY_ADDRESS"])
agg = os.environ.get("WALRUS_AGGREGATOR_URL", "https://aggregator.walrus-testnet.walrus.space").rstrip("/")
abi = [{"name": "getCapabilityScore", "type": "function", "stateMutability": "view",
        "inputs": [{"type": "uint256"}, {"type": "string"}],
        "outputs": [{"name": "", "type": "tuple", "components": [
            {"name": "dataScoreBps", "type": "uint16"}, {"name": "pathScoreBps", "type": "uint16"},
            {"name": "tokenEfficiencyBps", "type": "uint16"}, {"name": "compositeBps", "type": "uint16"},
            {"name": "failed", "type": "bool"}, {"name": "walrusBlobId", "type": "string"}]}]}]
c = w3.eth.contract(address=R, abi=abi)


def fetch(blob_id):
    url = f"{agg}/v1/blobs/{blob_id}"
    with urllib.request.urlopen(url, timeout=25) as r:
        return r.read()


for ag, mcp, cap in [(1, "lifi", "quote"), (3, "odos", "quote"),
                     (4, "jupiter", "quote"), (4, "jupiter", "positions"),
                     (5, "kyberswap", "quote"), (2, "1inch", "swap")]:
    s = c.functions.getCapabilityScore(ag, cap).call()
    blob = s[5]
    print(f"=== {mcp}/{cap}  on-chain walrusBlobId={blob}")
    try:
        raw = fetch(blob)
        m = json.loads(raw)
        print(f"   manifest keys: {sorted(m.keys())}")
        print(f"   composite={m.get('composite')} latency_ms={m.get('latency_ms')} run_id={m.get('run_id')}")
        print(f"   walrus_blob_id(eval path)={m.get('walrus_blob_id')}")
        print(f"   walrus_eval_blob_id={m.get('walrus_eval_blob_id')}")
        print(f"   walrus_index_blob_id={m.get('walrus_index_blob_id')}")
        att = m.get("attestation")
        if att:
            print(f"   attestation.model={att.get('model')} verdict_len={len(att.get('verdict','') or '')}")
        # is the eval transcript fetchable?
        evp = m.get("walrus_eval_blob_id") or m.get("walrus_blob_id")
        if evp and not str(evp).startswith("walrus://"):
            try:
                ev = fetch(evp)
                print(f"   -> eval blob fetch OK ({len(ev)} bytes)")
            except Exception as e:
                print(f"   -> eval blob fetch FAILED: {e}")
        elif evp:
            print(f"   -> eval path is indexed ({evp}); needs walrus_index_blob_id to resolve")
    except Exception as e:
        print(f"   manifest fetch/parse FAILED: {e}")
