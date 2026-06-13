"""Tests for deterministic Inspect log discovery."""

from __future__ import annotations

import pytest

from goldenmcp_eval_runner.inspect_logs import find_inspect_log_for_task


def test_find_inspect_log_requires_task_slug_match(monkeypatch, tmp_path):
    log_a = tmp_path / "other_task.json"
    log_a.write_bytes(b"{}")
    log_b = tmp_path / "goldenmcp_lifi_quote.json"
    log_b.write_bytes(b'{"status":"ok"}')

    class LogInfo:
        def __init__(self, name: str):
            self.name = name

    monkeypatch.setattr(
        "inspect_ai.log.list_eval_logs",
        lambda: [LogInfo(str(log_a)), LogInfo(str(log_b))],
    )

    path, data, raw = find_inspect_log_for_task("goldenmcp/lifi_quote")
    assert path == str(log_b)
    assert raw == b'{"status":"ok"}'


def test_find_inspect_log_fails_when_no_match(monkeypatch, tmp_path):
    log_a = tmp_path / "other.json"
    log_a.write_bytes(b"{}")

    class LogInfo:
        def __init__(self, name: str):
            self.name = name

    monkeypatch.setattr("inspect_ai.log.list_eval_logs", lambda: [LogInfo(str(log_a))])

    with pytest.raises(FileNotFoundError, match="no inspect log matching"):
        find_inspect_log_for_task("goldenmcp/lifi_quote")
