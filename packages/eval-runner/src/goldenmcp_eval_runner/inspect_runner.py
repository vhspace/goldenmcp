"""In-process Inspect-ai eval invocation (no subprocess)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from goldenmcp_eval_runner.inspect_logs import find_inspect_log_for_benchmark, read_inspect_log_file

logger = logging.getLogger(__name__)


def inspect_task_spec(mcp: str, capability: str) -> str:
    slug = f"{mcp.replace('-', '_')}_{capability.replace('-', '_')}"
    return f"packages/inspect-web3/src/goldenmcp_inspect/tasks.py@{slug}"


def run_inspect_eval(
    *,
    mcp: str,
    capability: str,
    model: str,
    repo_root: Path,
    log_dir: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    """Run Inspect eval in-process; return (log_path, log_data, raw_bytes)."""
    from inspect_ai import eval

    root = repo_root.resolve()
    logs_dir = (log_dir or root / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    task_spec = inspect_task_spec(mcp, capability)

    logger.info(
        "in-process inspect eval task=%s model=%s log_dir=%s repo_root=%s",
        task_spec,
        model,
        logs_dir,
        root,
    )

    prev_cwd = Path.cwd()
    try:
        os.chdir(root)
        eval_logs = eval(
            tasks=task_spec,
            model=model,
            log_dir=str(logs_dir),
            display="none",
            log_level="warning",
        )
    finally:
        os.chdir(prev_cwd)

    if not eval_logs:
        raise RuntimeError("inspect eval returned no logs")

    eval_log = eval_logs[0]
    if eval_log.status == "error":
        err = eval_log.error
        message = getattr(err, "message", None) or str(err) if err else "unknown error"
        raise RuntimeError(f"inspect eval failed: {message}")

    log_path = (eval_log.location or "").strip()
    if log_path and Path(log_path).is_file():
        log_data, raw = read_inspect_log_file(log_path)
        return log_path, log_data, raw

    return find_inspect_log_for_benchmark(mcp, capability, repo_root=root)
