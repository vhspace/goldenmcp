"""Deterministic Inspect eval log discovery and parsing."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_inspect_log_file(log_path: str) -> tuple[dict[str, Any], bytes]:
    """Load Inspect log JSON and raw bytes (same logic as pipeline.post_eval_from_log_file)."""
    raw = Path(log_path).read_bytes()
    if log_path.endswith(".json"):
        log_data = json.loads(raw.decode())
    else:
        from inspect_ai.log import read_eval_log

        eval_log = read_eval_log(log_path)
        log_data = json.loads(json.dumps(eval_log.model_dump(mode="json")))
    return log_data, raw


def inspect_log_slugs(mcp: str, capability: str) -> list[str]:
    """Substrings that appear in Inspect eval log filenames for a benchmark."""
    dash = f"{mcp}-{capability}"
    under = f"{mcp}_{capability}".replace("-", "_")
    legacy = f"goldenmcp_{under}"
    return [dash, under, legacy]


def _resolve_log_path(log_name: str, repo_root: Path) -> Path | None:
    """Resolve inspect log path from list_eval_logs (often relative to repo root)."""
    candidates = [
        Path(log_name),
        repo_root / log_name,
        repo_root / "logs" / Path(log_name).name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def find_inspect_log_for_benchmark(
    mcp: str,
    capability: str,
    *,
    repo_root: Path | None = None,
) -> tuple[str, dict[str, Any], bytes]:
    """Return newest log file whose name contains a slug for mcp/capability."""
    from inspect_ai.log import list_eval_logs

    root = repo_root or Path.cwd()
    slugs = inspect_log_slugs(mcp, capability)
    logs = list_eval_logs()
    candidates: list[tuple[float, str]] = []

    for log in logs:
        resolved = _resolve_log_path(log.name, root)
        if resolved is None:
            logger.warning("inspect log listed but missing on disk path=%s", log.name)
            continue
        if not any(slug in resolved.name for slug in slugs):
            continue
        candidates.append((resolved.stat().st_mtime, str(resolved)))

    if not candidates and (root / "logs").is_dir():
        for slug in slugs:
            for path in (root / "logs").glob(f"*{slug}*"):
                if path.is_file():
                    candidates.append((path.stat().st_mtime, str(path)))

    if not candidates:
        raise FileNotFoundError(
            f"no inspect log matching mcp={mcp!r} capability={capability!r} (slugs {slugs!r})",
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    log_path = candidates[0][1]
    logger.info(
        "selected inspect log path=%s mcp=%s capability=%s",
        log_path,
        mcp,
        capability,
    )
    log_data, raw = read_inspect_log_file(log_path)
    return log_path, log_data, raw


def find_inspect_log_for_task(task_name: str) -> tuple[str, dict[str, Any], bytes]:
    """Legacy helper: parse goldenmcp/mcp_capability or mcp_capability task names."""
    if task_name.startswith("goldenmcp/"):
        slug = task_name.removeprefix("goldenmcp/")
    else:
        slug = task_name.replace("/", "_")
    if "_" not in slug:
        raise FileNotFoundError(f"cannot derive mcp/capability from task name {task_name!r}")
    mcp, capability = slug.split("_", 1)
    return find_inspect_log_for_benchmark(mcp, capability)
