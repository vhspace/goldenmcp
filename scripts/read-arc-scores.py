import os
from web3 import Web3

w3 = Web3(Web3.HTTPProvider(os.environ["ARC_RPC_URL"]))
R = Web3.to_checksum_address(os.environ["ARC_REGISTRY_ADDRESS"])
abi = [
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
]
c = w3.eth.contract(address=R, abi=abi)

targets = [(1, "lifi", "quote"), (1, "lifi", "route"),
           (2, "1inch", "quote"), (2, "1inch", "swap"),
           (3, "odos", "quote"), (3, "odos", "swap"),
           (4, "jupiter", "quote"), (4, "jupiter", "positions"),
           (5, "kyberswap", "quote"), (5, "kyberswap", "route")]
for ag, mcp, cap in targets:
    try:
        s = c.functions.getCapabilityScore(ag, cap).call()
        blob = s[5]
        if not blob and s[3] == 0:
            print(f"agent {ag} {mcp}/{cap}: (no score on-chain)")
            continue
        print(f"agent {ag} {mcp}/{cap}: composite={s[3]}bps data={s[0]} path={s[1]} tokEff={s[2]} failed={s[4]} walrus={blob[:20]}")
    except Exception as e:
        print(f"agent {ag} {mcp}/{cap}: read error {e}")

print("--- attestation records ---")
for ag, mcp in [(1, "lifi"), (2, "1inch"), (3, "odos"), (4, "jupiter"), (5, "kyberswap")]:
    try:
        r = c.functions.records(ag).call()
        print(f"agent {ag} {mcp}: attestationId={r[4][:28] or '(none)'} transcriptHash={r[5].hex()[:24]}")
    except Exception as e:
        print(f"agent {ag} {mcp}: {e}")
