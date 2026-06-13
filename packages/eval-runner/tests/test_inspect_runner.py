"""In-process Inspect eval runner tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import inspect_ai
import pytest

from goldenmcp_eval_runner import inspect_runner


def test_inspect_task_spec():
    assert inspect_runner.inspect_task_spec("lifi", "quote") == (
        "packages/inspect-web3/src/goldenmcp_inspect/tasks.py@lifi_quote"
    )


def test_run_inspect_eval_returns_log_from_eval_location(monkeypatch, tmp_path):
    log_file = tmp_path / "logs" / "2026-06-13T12-00-00_lifi-quote.json"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')

    captured: dict = {}

    def fake_eval(**kwargs):
        captured.update(kwargs)
        return [SimpleNamespace(status="success", location=str(log_file), error=None)]

    monkeypatch.setattr(inspect_ai, "eval", fake_eval)

    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    log_path, log_data, raw = inspect_runner.run_inspect_eval(
        mcp="lifi",
        capability="quote",
        model="together/google/gemma-4-31B-it",
        repo_root=repo_root,
    )

    assert captured["display"] == "none"
    assert captured["model"] == "together/google/gemma-4-31B-it"
    assert "lifi_quote" in captured["tasks"]
    assert log_path == str(log_file)
    assert log_data["status"] == "success"
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_falls_back_to_log_discovery(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    log_file = repo_root / "logs" / "2026-06-13T12-00-00_lifi-quote.eval"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [SimpleNamespace(status="success", location="", error=None)],
    )

    def fake_find(mcp, capability, *, repo_root):
        return str(log_file), {"status": "success"}, log_file.read_bytes()

    monkeypatch.setattr(inspect_runner, "find_inspect_log_for_benchmark", fake_find)

    log_path, log_data, raw = inspect_runner.run_inspect_eval(
        mcp="lifi",
        capability="quote",
        model="openai/gpt-4o-mini",
        repo_root=repo_root,
    )
    assert log_path == str(log_file)
    assert log_data["status"] == "success"
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_raises_on_error_status(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [
            SimpleNamespace(status="error", location="", error=SimpleNamespace(message="boom")),
        ],
    )

    with pytest.raises(RuntimeError, match="boom"):
        inspect_runner.run_inspect_eval(
            mcp="lifi",
            capability="quote",
            model="openai/gpt-4o-mini",
            repo_root=repo_root,
        )
