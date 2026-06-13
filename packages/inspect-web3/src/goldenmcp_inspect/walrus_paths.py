"""Walrus logical paths compatible with Inspect log listing."""

from __future__ import annotations

from datetime import datetime, timezone


def inspect_eval_log_path(
    mcp: str,
    capability: str,
    *,
    run_id: str,
    created_at: datetime | None = None,
) -> str:
    """Return a walrus:// path Inspect can list under --log-dir walrus://evals/goldenmcp."""
    ts = (created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"{ts}_goldenmcp_{mcp}_{capability}_{run_id}.eval"
    return f"walrus://evals/goldenmcp/{filename}"
