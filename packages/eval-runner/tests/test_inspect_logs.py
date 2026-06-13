"""Tests for deterministic Inspect log discovery."""

from __future__ import annotations

import pytest

from goldenmcp_eval_runner.inspect_logs import (
    find_inspect_log_for_benchmark,
    find_inspect_log_for_task,
    inspect_log_slugs,
)


def test_inspect_log_slugs_includes_dash_form():
    assert "lifi-quote" in inspect_log_slugs("lifi", "quote")


def test_find_inspect_log_resolves_relative_log_path(monkeypatch, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_b = logs_dir / "2026-06-13T20-30-32-00-00_lifi-quote_abc.json"
    log_b.write_bytes(b'{"status":"ok"}')

    class LogInfo:
        def __init__(self, name: str):
            self.name = name

    monkeypatch.setattr(
        "inspect_ai.log.list_eval_logs",
        lambda: [LogInfo("logs/2026-06-13T20-30-32-00-00_lifi-quote_abc.json")],
    )

    path, _, raw = find_inspect_log_for_benchmark("lifi", "quote", repo_root=tmp_path)
    assert path == str(log_b)
    assert raw == b'{"status":"ok"}'


def test_find_inspect_log_matches_lifi_quote_dash_filename(monkeypatch, tmp_path):
    log_a = tmp_path / "other_task.eval"
    log_a.write_bytes(b"{}")
    log_b = tmp_path / "2026-06-13T20-05-46-00-00_lifi-quote_abc.json"
    log_b.write_bytes(b'{"status":"ok"}')

    class LogInfo:
        def __init__(self, name: str):
            self.name = name

    monkeypatch.setattr(
        "inspect_ai.log.list_eval_logs",
        lambda: [LogInfo(str(log_a)), LogInfo(str(log_b))],
    )

    path, _data, raw = find_inspect_log_for_benchmark("lifi", "quote")
    assert path == str(log_b)
    assert raw == b'{"status":"ok"}'


def test_find_inspect_log_legacy_goldenmcp_slug(monkeypatch, tmp_path):
    log_b = tmp_path / "goldenmcp_lifi_quote.json"
    log_b.write_bytes(b'{"status":"ok"}')

    class LogInfo:
        def __init__(self, name: str):
            self.name = name

    monkeypatch.setattr("inspect_ai.log.list_eval_logs", lambda: [LogInfo(str(log_b))])

    path, _, raw = find_inspect_log_for_task("goldenmcp/lifi_quote")
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
        find_inspect_log_for_benchmark("lifi", "quote", repo_root=tmp_path)
