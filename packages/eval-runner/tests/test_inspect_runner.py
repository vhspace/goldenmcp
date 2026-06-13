"""In-process Inspect eval runner tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import inspect_ai
import pytest

from goldenmcp_eval_runner import inspect_runner


def test_inspect_task_spec():
    assert inspect_runner.inspect_task_spec("lifi", "quote") == "lifi_quote"


def _eval_log_namespace(
    *,
    status: str,
    location: str = "",
    error: object | None = None,
    log_data: dict | None = None,
) -> SimpleNamespace:
    data = log_data or {"status": status, "samples": []}

    def model_dump(*, mode: str = "json") -> dict:
        assert mode == "json"
        return data

    return SimpleNamespace(
        status=status,
        location=location,
        error=error,
        model_dump=model_dump,
    )


def test_run_inspect_eval_returns_log_from_eval_location(monkeypatch, tmp_path):
    log_file = tmp_path / "logs" / "2026-06-13T12-00-00_lifi-quote.json"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')
    expected_log_data = {"status": "success", "samples": [], "version": 2}

    captured: dict = {}

    def fake_eval(**kwargs):
        captured.update(kwargs)
        return [
            _eval_log_namespace(
                status="success",
                location=str(log_file),
                log_data=expected_log_data,
            ),
        ]

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
    assert captured["tasks"] == "lifi_quote"
    assert log_path == str(log_file)
    assert log_data == {"status": "success", "samples": []}
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_falls_back_for_raw_bytes_when_location_missing(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    log_file = repo_root / "logs" / "2026-06-13T12-00-00_lifi-quote.eval"
    log_file.parent.mkdir(parents=True)
    log_file.write_bytes(b'{"status":"success","samples":[]}')
    expected_log_data = {"status": "success", "samples": [{"id": "1"}]}

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [
            _eval_log_namespace(status="success", location="", log_data=expected_log_data),
        ],
    )

    def fake_find(mcp, capability, *, repo_root):
        return str(log_file), {"status": "from_disk"}, log_file.read_bytes()

    monkeypatch.setattr(inspect_runner, "find_inspect_log_for_benchmark", fake_find)

    log_path, log_data, raw = inspect_runner.run_inspect_eval(
        mcp="lifi",
        capability="quote",
        model="openai/gpt-4o-mini",
        repo_root=repo_root,
    )
    assert log_path == str(log_file)
    assert log_data == expected_log_data
    assert raw == log_file.read_bytes()


def test_run_inspect_eval_raises_on_error_status(monkeypatch, tmp_path):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [
            _eval_log_namespace(
                status="error",
                error=SimpleNamespace(message="boom"),
            ),
        ],
    )

    with pytest.raises(RuntimeError, match="boom"):
        inspect_runner.run_inspect_eval(
            mcp="lifi",
            capability="quote",
            model="openai/gpt-4o-mini",
            repo_root=repo_root,
        )


@pytest.mark.parametrize("status", ["cancelled", "started", "unknown"])
def test_run_inspect_eval_raises_on_non_success_status(monkeypatch, tmp_path, status):
    repo_root = tmp_path
    (repo_root / "packages").mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    monkeypatch.setattr(
        inspect_ai,
        "eval",
        lambda **kwargs: [_eval_log_namespace(status=status)],
    )

    with pytest.raises(RuntimeError, match=status):
        inspect_runner.run_inspect_eval(
            mcp="lifi",
            capability="quote",
            model="openai/gpt-4o-mini",
            repo_root=repo_root,
        )
