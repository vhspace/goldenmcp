"""Async inspect/publish job API tests."""

from __future__ import annotations

import importlib
import time

import pytest
from fastapi.testclient import TestClient

from goldenmcp_eval_runner.app import app
from goldenmcp_eval_runner.jobs import eval_jobs, JobStatus
from goldenmcp_eval_runner.pending_runs import cai_callbacks
from goldenmcp_eval_runner.settings import get_settings


def _app_module():
    return importlib.import_module("goldenmcp_eval_runner.app")


@pytest.fixture(autouse=True)
def clear_stores():
    eval_jobs._jobs.clear()
    cai_callbacks._by_run_id.clear()
    yield
    eval_jobs._jobs.clear()
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


def test_get_eval_runs_404_for_unknown_id(client):
    response = client.get("/eval/runs/unknown-run-id", headers=_auth_headers())
    assert response.status_code == 404


def test_async_inspect_returns_202_then_poll_until_scored(client, monkeypatch):
    app_module = _app_module()

    fake_log = b'{"eval": "raw-log-bytes"}'

    def fake_run_inspect(**kwargs):
        return "/tmp/goldenmcp_lifi_quote.eval", {"status": "success"}, fake_log

    monkeypatch.setattr(app_module, "run_inspect_eval", fake_run_inspect)
    monkeypatch.setattr(
        app_module,
        "transcript_from_inspect_log",
        lambda log_data, mcp, capability: __import__(
            "goldenmcp_inspect.schemas", fromlist=["EvalTranscript"]
        ).EvalTranscript(mcp=mcp, capability=capability),
    )

    response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote"},
        headers=_auth_headers(),
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    run_id = body["run_id"]

    final = _poll_until(client, run_id, "scored")
    assert final["status"] == "scored"
    assert final["manifest"]["mcp"] == "lifi"
    assert final["manifest"]["capability"] == "quote"


def test_failed_inspect_sets_status_failed_with_error(client, monkeypatch):
    app_module = _app_module()

    def fake_run_inspect(**kwargs):
        raise RuntimeError("inspect eval failed: boom")

    monkeypatch.setattr(app_module, "run_inspect_eval", fake_run_inspect)

    response = client.post(
        "/eval/inspect",
        json={"mcp": "lifi", "capability": "quote"},
        headers=_auth_headers(),
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]

    final = _poll_until(client, run_id, "failed")
    assert final["status"] == "failed"
    assert final["error"]


def test_async_publish_returns_202_then_poll_until_published(client, monkeypatch):
    app_module = _app_module()

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["inspect_log_bytes"] = kwargs.get("inspect_log_bytes")
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="manifest-blob",
            walrus_eval_blob_id="eval-blob",
            walrus_index_blob_id="index-blob",
        )

    monkeypatch.setattr(app_module, "publish_manifest_to_walrus", fake_publish)

    score_response = client.post(
        "/eval/score",
        json={"mcp": "lifi", "capability": "quote", "transcript": _sample_transcript_payload()},
        headers=_auth_headers(),
    )
    run_id = score_response.json()["run_id"]

    publish_response = client.post(
        "/eval/publish",
        json={"run_id": run_id, "attestation": {"inference_id": "att-1", "model": "gemma4"}},
        headers=_auth_headers(),
    )
    assert publish_response.status_code == 202
    assert publish_response.json()["status"] == "publishing"

    final = _poll_until(client, run_id, "published")
    assert final["status"] == "published"
    assert final["walrus_manifest_blob_id"] == "manifest-blob"
    assert final["walrus_eval_blob_id"] == "eval-blob"
    assert final["manifest"]["attestation_id"] == "att-1"


def test_async_publish_from_inspect_preserves_log_bytes(client, monkeypatch):
    app_module = _app_module()
    fake_log = b'{"eval": "raw-log-bytes"}'

    def fake_run_inspect(**kwargs):
        return "/tmp/goldenmcp_lifi_quote.eval", {"status": "success"}, fake_log

    captured: dict = {}

    def fake_publish(manifest, **kwargs):
        captured["inspect_log_bytes"] = kwargs.get("inspect_log_bytes")
        captured["inspect_log_path"] = kwargs.get("inspect_log_path")
        from goldenmcp_inspect.pipeline import WalrusUploadResult

        return WalrusUploadResult(
            manifest=manifest,
            walrus_manifest_blob_id="m",
            walrus_eval_blob_id="e",
        )

    monkeypatch.setattr(app_module, "run_inspect_eval", fake_run_inspect)
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
    run_id = inspect_response.json()["run_id"]
    _poll_until(client, run_id, "scored")

    client.post(
        "/eval/publish",
        json={"run_id": run_id},
        headers=_auth_headers(),
    )
    _poll_until(client, run_id, "published")
    assert captured["inspect_log_bytes"] == fake_log
    assert captured["inspect_log_path"] == "/tmp/goldenmcp_lifi_quote.eval"
