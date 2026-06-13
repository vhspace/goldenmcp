"""Walrus eval-storage bootstrap expectations."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
SETUP_SCRIPT = REPO_ROOT / "scripts" / "setup_eval_env.sh"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_walrus.sh"

WALRUS_PUBLISHER = "https://publisher.walrus-testnet.walrus.space"
WALRUS_AGGREGATOR = "https://aggregator.walrus-testnet.walrus.space"


def test_env_example_has_walrus_testnet_endpoints():
    text = ENV_EXAMPLE.read_text()
    assert f"WALRUS_PUBLISHER_URL={WALRUS_PUBLISHER}" in text
    assert f"WALRUS_AGGREGATOR_URL={WALRUS_AGGREGATOR}" in text
    assert "WALRUS_EPOCHS=" in text
    assert f"NEXT_PUBLIC_WALRUS_AGGREGATOR_URL={WALRUS_AGGREGATOR}" in text


def test_setup_eval_env_bootstraps_walrus_defaults():
    text = SETUP_SCRIPT.read_text()
    assert "ensure_walrus_defaults" in text
    assert "WALRUS_PUBLISHER_URL" in text
    assert "WALRUS_AGGREGATOR_URL" in text
    assert "WALRUS_EPOCHS" in text
    assert "NEXT_PUBLIC_WALRUS_AGGREGATOR_URL" in text


def test_verify_walrus_script_exists():
    assert VERIFY_SCRIPT.is_file()
    text = VERIFY_SCRIPT.read_text()
    assert "packages/walrus-client/tests" in text
