"""Eval-runner HTTP tests."""

from __future__ import annotations

import base64
import importlib

import pytest
from fastapi.testclient import TestClient

from goldenmcp_eval_runner.app import app
from goldenmcp_eval_runner.pending_runs import cai_callbacks, pending_runs
from goldenmcp_eval_runner.settings import get_settings


def _app_module():
    return importlib.import_module("goldenmcp_eval_runner.app")


@pytest.fixture(autouse=True)
def clear_stores():
    pending_runs._runs.clear()
    cai_callbacks._by_run_id.clear()
    yield
    pending_runs._runs.clear()
    cai_callbacks._by_run_id.clear()


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


def test_eval_publish_rejects_missing_pending_run(client):
    response = client.post(
        "/eval/publish",
        json={"run_id": "unknown-run-id"},
        headers=_auth_headers(),
    )
    assert response.status_code == 404


def test_eval_publish_rejects_missing_bearer(client):
    response = client.post(
        "/eval/publish",
        json={"run_id": "publish-auth"},
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
    assert response.json()["run_id"] == "run-1"


def test_eval_inspect_query_params_backward_compat(client, monkeypatch):
    """Legacy query-param API still accepted alongside JSON body."""
    app_module = _app_module()

    captured: dict = {}

    def fake_find(task_name: str):
        captured["task"] = task_name
        log_data = {"status": "success", "results": {"samples": []}}
        raw = b'{"status":"success","results":{"samples":[]}}'
        return "/tmp/fake.eval", log_data, raw

    def fake_run(*args, **kwargs):
        import subprocess

        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(app_module, "find_inspect_log_for_task", fake_find)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        app_module,
        "transcript_from_inspect_log",
        lambda log_data, mcp, capability: __import__(
            "goldenmcp_inspect.schemas", fromlist=["EvalTranscript"]
        ).EvalTranscript(mcp=mcp, capability=capability),
    )

    response = client.post(
        "/eval/inspect?mcp=lifi&capability=quote&model=openai/gpt-4o-mini",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    assert captured["task"] == "goldenmcp/lifi_quote"


def test_eval_inspect_stores_log_bytes_for_publish(client, monkeypatch):
    app_module = _app_module()

    fake_log = b'{"eval": "raw-log-bytes"}'

    def fake_find(task_name: str):
        return "/tmp/goldenmcp_lifi_quote.eval", {"status": "success"}, fake_log

    def fake_run(*args, **kwargs):
        import subprocess

        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["inspect_log_bytes"] = kwargs.get("inspect_log_bytes")
        captured["inspect_log_path"] = kwargs.get("inspect_log_path")
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="manifest-blob",
            walrus_eval_blob_id="eval-blob",
            walrus_index_blob_id="index-blob",
        )

    monkeypatch.setattr(app_module, "find_inspect_log_for_task", fake_find)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        app_module,
        "transcript_from_inspect_log",
        lambda log_data, mcp, capability: __import__(
            "goldenmcp_inspect.schemas", fromlist=["EvalTranscript"]
        ).EvalTranscript(mcp=mcp, capability=capability),
    )
    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    inspect_response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote"},
        headers=_auth_headers(),
    )
    assert inspect_response.status_code == 200
    run_id = inspect_response.json()["run_id"]

    publish_response = client.post(
        "/eval/publish",
        json={"run_id": run_id, "attestation_id": "att-1"},
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 200
    assert captured["inspect_log_bytes"] == fake_log
    assert captured["inspect_log_path"] == "/tmp/goldenmcp_lifi_quote.eval"


def test_eval_publish_merges_cai_webhook_attestation(client, monkeypatch):
    app_module = _app_module()

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["attestation_id"] = manifest.attestation_id
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="m",
            walrus_eval_blob_id="e",
        )

    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    score_response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    run_id = score_response.json()["run_id"]

    client.post(
        "/webhooks/cai",
        json={"input": {"run_id": run_id, "attestation_id": "from-cai", "attestation_tx_hash": "0xabc"}},
        headers={"X-CAI-Webhook-Secret": "test-cai-secret"},
    )

    publish_response = client.post(
        "/eval/publish",
        json={"run_id": run_id},
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 200
    assert captured["attestation_id"] == "from-cai"


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
    run_id = score_response.json()["run_id"]

    publish_response = client.post(
        "/eval/publish",
        json={
            "run_id": run_id,
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


def test_eval_publish_legacy_manifest_with_log_bytes(client, monkeypatch):
    app_module = _app_module()

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["inspect_log_bytes"] = kwargs.get("inspect_log_bytes")
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="m",
            walrus_eval_blob_id="e",
        )

    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    raw = b'{"legacy": true}'
    score_response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    run_id = score_response.json()["run_id"]
    pending_runs.pop(run_id)

    publish_response = client.post(
        "/eval/publish",
        json={
            "run_id": run_id,
            "manifest": score_response.json()["manifest"],
            "inspect_log_bytes_b64": base64.b64encode(raw).decode(),
        },
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 200
    assert captured["inspect_log_bytes"] == raw
