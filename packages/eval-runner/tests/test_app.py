"""Eval-runner HTTP tests."""

from __future__ import annotations

import base64
import importlib
import time

import pytest
from fastapi.testclient import TestClient

from goldenmcp_eval_runner.app import app
from goldenmcp_eval_runner.jobs import eval_jobs
from goldenmcp_eval_runner.pending_runs import benchmark_cursor, cai_callbacks, inference_index
from goldenmcp_eval_runner.settings import get_settings


def _app_module():
    return importlib.import_module("goldenmcp_eval_runner.app")


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _patch_inspect_subprocess(monkeypatch, *, raw: bytes = b'{"eval": "raw-log-bytes"}') -> None:
    """Stub the per-eval subprocess + log read (the app spawns inspect_runner)."""
    import json as _json

    app_module = _app_module()
    monkeypatch.setattr(
        app_module.subprocess,
        "run",
        lambda *a, **k: _FakeProc(0, stdout=_json.dumps({"log_path": "/tmp/goldenmcp_lifi_quote.eval"})),
    )
    monkeypatch.setattr(
        app_module,
        "read_inspect_log_file",
        lambda path: ({"status": "success"}, raw),
    )
    monkeypatch.setattr(
        app_module,
        "transcript_from_inspect_log",
        lambda log_data, mcp, capability: __import__(
            "goldenmcp_inspect.schemas", fromlist=["EvalTranscript"]
        ).EvalTranscript(mcp=mcp, capability=capability),
    )


@pytest.fixture(autouse=True)
def clear_stores():
    eval_jobs._jobs.clear()
    cai_callbacks._by_run_id.clear()
    inference_index._by_inference_id.clear()
    benchmark_cursor._index = 0
    yield
    eval_jobs._jobs.clear()
    cai_callbacks._by_run_id.clear()
    inference_index._by_inference_id.clear()


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


def _poll_until(client, run_id: str, target_status: str, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        response = client.get(f"/eval/runs/{run_id}", headers=_auth_headers())
        if response.status_code == 200 and response.json().get("status") == target_status:
            return response.json()
        if response.status_code == 200 and response.json().get("status") == "failed":
            return response.json()
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not reach {target_status} within {timeout_s}s")


def test_health_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_benchmarks_no_auth(client):
    response = client.get("/benchmarks")
    assert response.status_code == 200
    assert "benchmarks" in response.json()


def test_benchmarks_next_round_robins(client):
    total = len(client.get("/benchmarks").json()["benchmarks"])
    assert total > 0
    seen = []
    for i in range(total):
        body = client.get("/benchmarks/next").json()
        assert body["index"] == i
        assert body["total"] == total
        seen.append((body["mcp"], body["capability"]))
    # One full cycle covers every benchmark exactly once, then wraps to index 0.
    assert len(set(seen)) == total
    assert client.get("/benchmarks/next").json()["index"] == 0


def test_eval_score_rejects_when_api_key_unset(monkeypatch):
    monkeypatch.setenv("EVAL_RUNNER_API_KEY", "")
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
        json={"input": {"id": "inf-1", "status": "completed", "run_id": "run-1"}},
        headers={"X-CAI-Webhook-Secret": "test-cai-secret"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["run_id"] == "run-1"


def test_webhooks_cai_injects_run_id_from_query(client):
    """Real CAI status objects have no run_id; the workflow carries it in the URL query."""
    response = client.post(
        "/webhooks/cai?run_id=run-q",
        json={"input": {"id": "inf-2", "status": "completed", "output": "PASS"}},
        headers={"X-CAI-Webhook-Secret": "test-cai-secret"},
    )
    assert response.status_code == 200
    assert response.json()["run_id"] == "run-q"


def test_eval_inspect_query_params_backward_compat(client, monkeypatch):
    """Legacy query-param API still accepted alongside JSON body."""
    _patch_inspect_subprocess(monkeypatch)

    response = client.post(
        "/eval/inspect?mcp=lifi&capability=quote&model=openai/gpt-4o-mini",
        headers=_auth_headers(),
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    _poll_until(client, run_id, "scored")


def test_eval_inspect_stores_log_bytes_for_publish(client, monkeypatch):
    app_module = _app_module()
    fake_log = b'{"eval": "raw-log-bytes"}'
    _patch_inspect_subprocess(monkeypatch, raw=fake_log)

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

    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    inspect_response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote"},
        headers=_auth_headers(),
    )
    assert inspect_response.status_code == 202
    run_id = inspect_response.json()["run_id"]
    _poll_until(client, run_id, "scored")

    publish_response = client.post(
        "/eval/publish",
        json={"run_id": run_id, "attestation": {"inference_id": "att-1", "model": "gemma4"}},
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 202
    _poll_until(client, run_id, "published")
    assert captured["inspect_log_bytes"] == fake_log
    assert captured["inspect_log_path"] == "/tmp/goldenmcp_lifi_quote.eval"


def test_eval_publish_merges_cai_webhook_attestation(client, monkeypatch):
    app_module = _app_module()

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["attestation_id"] = manifest.attestation_id
        captured["attestation"] = manifest.attestation
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

    # Real CAI cre_callback: status object (id/output/usage), run_id carried in query string.
    client.post(
        f"/webhooks/cai?run_id={run_id}",
        json={
            "input": {
                "id": "inf-from-cai",
                "status": "completed",
                "model": "gemma4",
                "output": "PASS",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "resources": [
                    {
                        "response_digest": "0a0124911560a2236e432d30c3e2a90b0666f4c84b40bf10ba01960595c6ecea"
                    }
                ],
            }
        },
        headers={"X-CAI-Webhook-Secret": "test-cai-secret"},
    )

    publish_response = client.post(
        "/eval/publish",
        json={"run_id": run_id},
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 202
    _poll_until(client, run_id, "published")
    assert captured["attestation_id"] == "inf-from-cai"
    assert captured["attestation"].inference_id == "inf-from-cai"
    assert captured["attestation"].verdict == "PASS"
    assert (
        captured["attestation"].transcript_hash
        == "0x0a0124911560a2236e432d30c3e2a90b0666f4c84b40bf10ba01960595c6ecea"
    )


@pytest.mark.skipif(
    not __import__("os").environ.get("OPENAI_API_KEY") and not __import__("os").environ.get("TOGETHER_API_KEY"),
    reason="LLM API key required for live inspect eval",
)
@pytest.mark.skipif(
    not __import__("os").environ.get("LIFI_MCP_URL"),
    reason="LIFI_MCP_URL required for live LiFi HTTP MCP eval",
)
def test_eval_inspect_returns_manifest_without_walrus(client):
    response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote"},
        headers=_auth_headers(),
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    final = _poll_until(client, run_id, "scored", timeout_s=300.0)
    manifest = final["manifest"]
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
            "attestation": {"inference_id": "attest-test", "model": "gemma4", "verdict": "PASS"},
        },
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 202
    body = _poll_until(client, run_id, "published", timeout_s=120.0)
    assert body["walrus_manifest_blob_id"]
    assert body["walrus_eval_blob_id"]
    assert body["manifest"]["attestation_id"] == "attest-test"
    assert body["manifest"]["attestation"]["inference_id"] == "attest-test"


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
    eval_jobs._jobs.pop(run_id, None)

    publish_response = client.post(
        "/eval/publish",
        json={
            "run_id": run_id,
            "manifest": score_response.json()["manifest"],
            "inspect_log_bytes_b64": base64.b64encode(raw).decode(),
        },
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 202
    _poll_until(client, run_id, "published")
    assert captured["inspect_log_bytes"] == raw


def test_cai_submitted_maps_inference_id(client):
    resp = client.post(
        "/eval/cai-submitted",
        json={"inference_id": "inf-xyz", "run_id": "run-xyz"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run-xyz"
    assert inference_index.get("inf-xyz") == "run-xyz"


def test_cai_submitted_requires_auth(client):
    resp = client.post("/eval/cai-submitted", json={"inference_id": "i", "run_id": "r"})
    assert resp.status_code == 401


def test_publish_by_inference_id_resolves_run(client, monkeypatch):
    """Handler B path: publish identified by CAI inference_id, not run_id."""
    app_module = _app_module()

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["attestation"] = manifest.attestation
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="m-blob",
            walrus_eval_blob_id="e-blob",
        )

    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    score = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    run_id = score.json()["run_id"]

    # Handler A registers the mapping after submitting to CAI.
    client.post(
        "/eval/cai-submitted",
        json={"inference_id": "inf-b", "run_id": run_id},
        headers=_auth_headers(),
    )

    # Handler B publishes using only the inference_id from the CAI status.
    publish = client.post(
        "/eval/publish",
        json={
            "inference_id": "inf-b",
            "attestation": {"inference_id": "inf-b", "model": "gemma4", "verdict": "PASS"},
        },
        headers=_auth_headers(),
    )
    assert publish.status_code == 202
    final = _poll_until(client, run_id, "published")
    assert final["mcp"] == "lifi"
    assert final["capability"] == "quote"
    assert captured["attestation"].inference_id == "inf-b"


def test_publish_unknown_inference_id_404(client):
    resp = client.post(
        "/eval/publish",
        json={"inference_id": "nope"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404
