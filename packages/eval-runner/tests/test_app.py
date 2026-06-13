"""Eval-runner HTTP tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from goldenmcp_eval_runner.app import app
from goldenmcp_eval_runner.settings import get_settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("EVAL_RUNNER_API_KEY", "test-runner-key")
    monkeypatch.setenv("CAI_WEBHOOK_SECRET", "test-cai-secret")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-runner-key"}


def _sample_transcript_payload() -> dict:
    return {
        "events": [
            {"kind": "tool", "tool_name": "get-chains", "content": "{}"},
            {"kind": "tool", "tool_name": "get-tokens", "content": "{}"},
            {"kind": "tool", "tool_name": "get-quote", "content": '{"amount": 1}'},
        ],
        "final_output": {"amount": 1, "token": "USDC"},
        "total_tokens": 2000,
    }


def test_health_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_benchmarks_no_auth(client):
    response = client.get("/benchmarks")
    assert response.status_code == 200
    assert "benchmarks" in response.json()


def test_eval_score_rejects_when_api_key_unset(monkeypatch):
    monkeypatch.delenv("EVAL_RUNNER_API_KEY", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        response = test_client.post(
            "/eval/score",
            json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        )
        assert response.status_code == 401
        assert "EVAL_RUNNER_API_KEY" in response.json()["detail"]
    get_settings.cache_clear()


def test_eval_score_rejects_missing_bearer(client):
    response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
    )
    assert response.status_code == 401


def test_eval_score_rejects_invalid_bearer(client):
    response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert response.status_code == 401


def test_eval_score_returns_manifest_without_walrus(client):
    response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    manifest = body["manifest"]
    assert manifest["mcp"] == "lifi"
    assert manifest["capability"] == "quote"
    assert manifest.get("walrus_manifest_blob_id") is None
    assert manifest.get("walrus_blob_id") is None


def test_eval_publish_rejects_missing_bearer(client):
    response = client.post(
        "/eval/publish",
        json={
            "manifest": {
                "mcp": "lifi",
                "capability": "quote",
                "run_id": "publish-auth",
                "composite": 0.5,
            }
        },
    )
    assert response.status_code == 401


def test_webhooks_cai_rejects_invalid_secret(client):
    response = client.post(
        "/webhooks/cai",
        json={"input": {"attestation_id": "abc"}},
        headers={"X-CAI-Webhook-Secret": "wrong"},
    )
    assert response.status_code == 401


def test_webhooks_cai_accepts_valid_secret(client):
    response = client.post(
        "/webhooks/cai",
        json={"input": {"attestation_id": "abc", "run_id": "run-1"}},
        headers={"X-CAI-Webhook-Secret": "test-cai-secret"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(
    not __import__("os").environ.get("OPENAI_API_KEY") and not __import__("os").environ.get("TOGETHER_API_KEY"),
    reason="LLM API key required for live inspect eval",
)
def test_eval_inspect_returns_manifest_without_walrus(client):
    response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote", "model": "openai/gpt-4o-mini"},
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    manifest = body["manifest"]
    assert manifest.get("walrus_manifest_blob_id") is None
    assert manifest.get("walrus_blob_id") is None


@pytest.mark.skipif(
    not __import__("os").environ.get("WALRUS_PUBLISHER_URL") or not __import__("os").environ.get("WALRUS_AGGREGATOR_URL"),
    reason="WALRUS_PUBLISHER_URL and WALRUS_AGGREGATOR_URL required for live upload",
)
def test_eval_publish_integration(client):
    score_response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    manifest = score_response.json()["manifest"]

    publish_response = client.post(
        "/eval/publish",
        json={
            "manifest": manifest,
            "attestation_id": "attest-test",
            "attestation_tx_hash": "0xdead",
        },
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 200
    body = publish_response.json()
    assert body["walrus_manifest_blob_id"]
    assert body["walrus_eval_blob_id"]
    assert body["manifest"]["attestation_id"] == "attest-test"
    assert body["manifest"]["attestation_tx_hash"] == "0xdead"
