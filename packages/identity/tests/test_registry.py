"""Identity layer tests."""

from goldenmcp_identity.registry import _format_bytes32, score_to_bps


def test_score_to_bps_clamps():
    assert score_to_bps(0.0) == 0
    assert score_to_bps(1.0) == 10000
    assert score_to_bps(0.85) == 8500
    assert score_to_bps(-0.5) == 0
    assert score_to_bps(1.5) == 10000


def test_format_bytes32():
    # Unset (all-zero) transcript hash -> empty string, not a bogus 0x000…0.
    assert _format_bytes32(bytes(32)) == ""
    assert _format_bytes32("0x" + "00" * 32) == ""
    # Real digest -> 0x-prefixed lowercase hex, from bytes or str input.
    assert _format_bytes32(bytes.fromhex("0a" * 32)) == "0x" + "0a" * 32
    assert _format_bytes32("0x" + "0a" * 32) == "0x" + "0a" * 32
