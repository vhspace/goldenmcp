"""Inspect-ai eval invocation. Used both as a library call and as the per-eval
subprocess entry point (`python -m goldenmcp_eval_runner.inspect_runner`) that the
eval-runner spawns so Inspect's process-global async/display state never collides
across consecutive runs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from goldenmcp_eval_runner.inspect_logs import find_inspect_log_for_benchmark, read_inspect_log_file

logger = logging.getLogger(__name__)


def inspect_task_spec(mcp: str, capability: str) -> str:
    """Return Inspect registry task name (matches @task-decorated function in goldenmcp_inspect.tasks)."""
    return f"{mcp.replace('-', '_')}_{capability.replace('-', '_')}"


def run_inspect_eval(
    *,
    mcp: str,
    capability: str,
    model: str,
    repo_root: Path,
    log_dir: Path | None = None,
    time_limit: int | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    """Run Inspect eval (one process); return (log_path, log_data, raw_bytes).

    time_limit caps per-sample wall clock so a slow/unreachable MCP (e.g. LI.FI
    SSE stalling) surfaces as a finished-but-low-scoring run instead of hanging
    until the much larger subprocess timeout.
    """
    from inspect_ai import eval

    root = repo_root.resolve()
    logs_dir = (log_dir or root / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    task_spec = inspect_task_spec(mcp, capability)

    logger.info(
        "inspect eval task=%s model=%s log_dir=%s repo_root=%s time_limit=%s",
        task_spec,
        model,
        logs_dir,
        root,
        time_limit,
    )

    eval_kwargs: dict[str, Any] = dict(
        tasks=task_spec,
        model=model,
        log_dir=str(logs_dir),
        display="none",
        log_level="warning",
    )
    if time_limit is not None and time_limit > 0:
        eval_kwargs["time_limit"] = time_limit
    eval_logs = eval(**eval_kwargs)

    if not eval_logs:
        raise RuntimeError("inspect eval returned no logs")

    eval_log = eval_logs[0]
    if eval_log.status != "success":
        if eval_log.status == "error":
            err = eval_log.error
            message = getattr(err, "message", None) or str(err) if err else "unknown error"
            raise RuntimeError(f"inspect eval failed: {message}")
        raise RuntimeError(f"inspect eval did not succeed: status={eval_log.status!r}")

    log_path = (eval_log.location or "").strip()

    if log_path and Path(log_path).is_file():
        log_data, raw = read_inspect_log_file(log_path)
        return log_path, log_data, raw

    log_data = eval_log.model_dump(mode="json")
    fallback_path, _, raw = find_inspect_log_for_benchmark(mcp, capability, repo_root=root)
    return fallback_path, log_data, raw


def main(argv: list[str] | None = None) -> int:
    """CLI entry: run one eval in this (fresh) process, print the log path as JSON.

    The eval-runner invokes this as a subprocess (one per eval) so Inspect's
    process-global anyio/display state never collides across runs — the in-process
    path hangs on the second consecutive `inspect_ai.eval()` in a long-lived server.
    The child prints only the log path; the parent reads the .eval file itself.
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(prog="goldenmcp-inspect-runner")
    parser.add_argument("--mcp", required=True)
    parser.add_argument("--capability", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--time-limit", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    try:
        log_path, _, _ = run_inspect_eval(
            mcp=args.mcp,
            capability=args.capability,
            model=args.model,
            repo_root=Path(args.repo_root),
            log_dir=Path(args.log_dir) if args.log_dir else None,
            time_limit=args.time_limit,
        )
    except Exception as exc:  # noqa: BLE001 — surface as stderr + non-zero exit
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps({"log_path": log_path}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
