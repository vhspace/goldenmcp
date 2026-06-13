"""Tests for eval chain prompt defaults."""

from goldenmcp_inspect.eval_chains import (
    BASE_CHAIN_ID,
    FRAXTAL_CHAIN_ID,
    LIFI_QUOTE_PROMPT,
    ODOS_QUOTE_PROMPT,
    ODOS_SWAP_PROMPT,
)


def test_quote_prompts_target_base():
    assert str(BASE_CHAIN_ID) in LIFI_QUOTE_PROMPT
    assert str(BASE_CHAIN_ID) in ODOS_QUOTE_PROMPT
    assert "8453" in LIFI_QUOTE_PROMPT


def test_odos_swap_targets_fraxtal():
    assert str(FRAXTAL_CHAIN_ID) in ODOS_SWAP_PROMPT
    assert "fraxtal" in ODOS_SWAP_PROMPT
