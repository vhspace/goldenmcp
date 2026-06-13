"""Inspect log path helpers for Walrus-backed eval storage."""

from __future__ import annotations

from datetime import datetime, timezone

from goldenmcp_inspect.walrus_paths import inspect_eval_log_path


def test_inspect_eval_log_path_uses_timestamp_and_run_id():
    created = datetime(2026, 6, 13, 12, 30, 0, tzinfo=timezone.utc)
    path = inspect_eval_log_path("lifi", "quote", run_id="run-1", created_at=created)
    assert path == (
        "walrus://evals/goldenmcp/"
        "2026-06-13T12-30-00_goldenmcp_lifi_quote_run-1.eval"
    )
