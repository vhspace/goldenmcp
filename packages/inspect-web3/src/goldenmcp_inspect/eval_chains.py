"""Chain defaults for live MCP eval tasks.

Quote evals use Base mainnet (8453) across vendors for comparability.
Swap evals use the chain each MCP executes on (Fraxtal for Odos).
"""

from __future__ import annotations

BASE_CHAIN_ID = 8453
BASE_CHAIN_NAME = "base"

FRAXTAL_CHAIN_ID = 252
FRAXTAL_CHAIN_NAME = "fraxtal"

# Small amounts to limit mainnet spend during evals.
EVAL_ETH_AMOUNT = "0.001"

# Prompts are deliberately intent-level and do NOT name the tools to call: the
# model must choose the tool trajectory from the MCP's tool descriptions, so
# PathScore measures planning rather than instruction-copying.
LIFI_QUOTE_PROMPT = (
    f"Using the LI.FI MCP server, get a quote to swap {EVAL_ETH_AMOUNT} ETH for USDC "
    f"on Base (chain ID {BASE_CHAIN_ID}). Report the expected USDC output amount."
)

LIFI_ROUTE_PROMPT = (
    f"Using the LI.FI MCP server, find the best route to move {EVAL_ETH_AMOUNT} ETH "
    f"into USDC on Base (chain ID {BASE_CHAIN_ID}) and report the route steps."
)

ODOS_QUOTE_PROMPT = (
    f"Using the Odos MCP server, get a swap quote for {EVAL_ETH_AMOUNT} ETH to USDC "
    f"on Base (chain name {BASE_CHAIN_NAME!r}, chain ID {BASE_CHAIN_ID}). "
    "Report the expected output amount."
)

ODOS_SWAP_PROMPT = (
    f"Using the Odos MCP server, quote and execute a tiny {EVAL_ETH_AMOUNT} ETH to "
    f"USDC swap on Fraxtal (chain name {FRAXTAL_CHAIN_NAME!r}, chain ID {FRAXTAL_CHAIN_ID})."
)

UNISWAP_QUOTE_PROMPT = (
    f"Use the Uniswap MCP to quote {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain ID {BASE_CHAIN_ID})."
)

UNISWAP_SWAP_PROMPT = (
    f"Use the Uniswap MCP to quote and execute a tiny ETH to USDC swap on "
    f"Base (chain ID {BASE_CHAIN_ID})."
)

ONEINCH_QUOTE_PROMPT = (
    f"Use the 1inch MCP to get a swap quote for {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain ID {BASE_CHAIN_ID}). Return the quote details."
)

ONEINCH_SWAP_PROMPT = (
    f"Use the 1inch MCP to get a quote and build a tiny ETH to USDC swap on "
    f"Base (chain ID {BASE_CHAIN_ID}). 1inch is non-custodial — return the swap "
    "transaction for the caller to sign; do not broadcast."
)

KYBERSWAP_QUOTE_PROMPT = (
    f"Use the KyberSwap MCP to get a swap quote (route) for {EVAL_ETH_AMOUNT} ETH to "
    f"USDC on Base (chain ID {BASE_CHAIN_ID}). Return the quote details."
)

KYBERSWAP_ROUTE_PROMPT = (
    f"Use the KyberSwap MCP to find and build the best route for {EVAL_ETH_AMOUNT} ETH "
    f"to USDC on Base (chain ID {BASE_CHAIN_ID}). KyberSwap is read-only — return the "
    "route and built calldata; do not broadcast."
)

# --- Solana track (Jupiter) ---
# Solana has no EVM chain ID; tokens are identified by mint address. Jupiter quotes
# are NOT comparable to EVM Base quotes — scoring is per-benchmark, so this is a
# separate track rather than a reuse of the Base constants above.
SOLANA_CHAIN_NAME = "solana"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_SOL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# Sample Solana wallet for read-only portfolio queries (Jupiter project treasury).
SAMPLE_SOLANA_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

JUPITER_QUOTE_PROMPT = (
    "Use the Jupiter MCP to get the current price of SOL "
    f"(mint {SOL_MINT}) denominated in USDC (mint {USDC_SOL_MINT}) on Solana. "
    "Return the price."
)

JUPITER_POSITIONS_PROMPT = (
    "Use the Jupiter MCP to list the token positions held by Solana wallet "
    f"{SAMPLE_SOLANA_WALLET}. Return the positions."
)
