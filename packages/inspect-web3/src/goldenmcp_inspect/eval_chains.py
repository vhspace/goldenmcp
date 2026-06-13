"""Chain defaults, solver system prompt, and per-task prompts for live MCP evals.

Quote evals use Base mainnet (8453) across EVM vendors for comparability.
Jupiter runs on Solana (a separate, non-comparable track).
"""

from __future__ import annotations

BASE_CHAIN_ID = 8453
BASE_CHAIN_NAME = "base"

FRAXTAL_CHAIN_ID = 252
FRAXTAL_CHAIN_NAME = "fraxtal"

# Small amounts to limit mainnet spend during evals.
EVAL_ETH_AMOUNT = "0.001"

# Solver system prompt — sets the read-only stage and the answer contract once,
# for every task. Because each eval attaches exactly one MCP, the per-task prompts
# below do NOT name the MCP (redundant and biasing) and do NOT name the tools to
# call (the model plans the trajectory from tool descriptions, so PathScore
# measures planning rather than transcription).
SYSTEM_PROMPT = (
    "You answer questions using ONLY the attached MCP tools. Read the tool descriptions and "
    "input schemas carefully and call the most specific tool for the task with correctly typed "
    "arguments. This is strictly read-only/quote-only: never execute, sign, build, or submit a "
    "transaction or swap. When you have the answer, submit a concise final response containing "
    "the numeric answer as a plain decimal number (or an explicit statement that the answer "
    "could not be determined). Do not guess or invent values."
)

# K=3 model ensemble. Each task runs on all three; the Chainlink CRE judge
# validates the aggregated final score inside the TEE.
# NOTE: confirm the exact Together slug for MiniMax before a live run.
EVAL_MODELS = [
    "anthropic/claude-haiku-4-5-20251001",
    "together/meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "together/MiniMaxAI/MiniMax-M2.7",
]

# --- EVM quote prompts (Base) ---
LIFI_QUOTE_PROMPT = (
    f"How much USDC is received when swapping {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain ID {BASE_CHAIN_ID})?"
)

LIFI_ROUTE_PROMPT = (
    f"Using the best available route, how much USDC is received when swapping "
    f"{EVAL_ETH_AMOUNT} ETH to USDC on Base (chain ID {BASE_CHAIN_ID})?"
)

ODOS_QUOTE_PROMPT = (
    f"How much USDC is received when swapping {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain name {BASE_CHAIN_NAME!r}, chain ID {BASE_CHAIN_ID})?"
)

UNISWAP_QUOTE_PROMPT = (
    f"How much USDC is received when swapping {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain ID {BASE_CHAIN_ID})?"
)

ONEINCH_QUOTE_PROMPT = (
    f"How much USDC is received when swapping {EVAL_ETH_AMOUNT} ETH to USDC on "
    f"Base (chain ID {BASE_CHAIN_ID})?"
)

KYBERSWAP_QUOTE_PROMPT = (
    f"Using the best available route, how much USDC is received when swapping "
    f"{EVAL_ETH_AMOUNT} ETH to USDC on Base (chain ID {BASE_CHAIN_ID})?"
)

# --- Build/execute prompts (PENDING read-only-scope decision) ---
# These conflict with the strictly read-only SYSTEM_PROMPT above and are kept only
# so the task imports stay valid until the lineup decision is made.
ODOS_SWAP_PROMPT = (
    f"Quote and execute a tiny {EVAL_ETH_AMOUNT} ETH to USDC swap on "
    f"Fraxtal (chain name {FRAXTAL_CHAIN_NAME!r}, chain ID {FRAXTAL_CHAIN_ID})."
)

UNISWAP_SWAP_PROMPT = (
    f"Quote and execute a tiny {EVAL_ETH_AMOUNT} ETH to USDC swap on "
    f"Base (chain ID {BASE_CHAIN_ID})."
)

ONEINCH_SWAP_PROMPT = (
    f"Build (do not broadcast) a tiny {EVAL_ETH_AMOUNT} ETH to USDC swap transaction "
    f"on Base (chain ID {BASE_CHAIN_ID}) for the caller to sign."
)

KYBERSWAP_ROUTE_PROMPT = (
    f"Find and build the best route (calldata only, do not broadcast) for swapping "
    f"{EVAL_ETH_AMOUNT} ETH to USDC on Base (chain ID {BASE_CHAIN_ID})."
)

# --- Solana track (Jupiter) — read-only price/portfolio ---
SOLANA_CHAIN_NAME = "solana"
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_SOL_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# Sample Solana wallet for read-only portfolio queries (Jupiter project treasury).
SAMPLE_SOLANA_WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

JUPITER_QUOTE_PROMPT = (
    f"What is the current price of SOL (mint {SOL_MINT}) in USDC "
    f"(mint {USDC_SOL_MINT}) on Solana?"
)

JUPITER_POSITIONS_PROMPT = (
    f"How many distinct token positions does Solana wallet {SAMPLE_SOLANA_WALLET} "
    "currently hold?"
)
