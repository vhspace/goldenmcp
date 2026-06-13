"""Identity layer tests."""

from goldenmcp_identity.registry import score_to_bps


def test_score_to_bps_clamps():
    assert score_to_bps(0.0) == 0
    assert score_to_bps(1.0) == 10000
    assert score_to_bps(0.85) == 8500
    assert score_to_bps(-0.5) == 0
    assert score_to_bps(1.5) == 10000
