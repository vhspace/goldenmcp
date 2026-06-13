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


def find_inspect_log_for_task(task_name: str) -> tuple[str, dict[str, Any], bytes]:
    """Return newest log file whose name contains the task slug; fail if none match."""
    from inspect_ai.log import list_eval_logs

    logs = list_eval_logs()
    if not logs:
        raise FileNotFoundError("inspect eval produced no log files")

    task_slug = task_name.replace("/", "_")
    candidates: list[tuple[float, str]] = []
    for log in logs:
        path = Path(log.name)
        if task_slug not in log.name:
            continue
        if not path.is_file():
            logger.warning("inspect log listed but missing on disk path=%s", log.name)
            continue
        candidates.append((path.stat().st_mtime, log.name))

    if not candidates:
        raise FileNotFoundError(f"no inspect log matching task {task_name!r} (slug {task_slug!r})")

    candidates.sort(key=lambda item: item[0], reverse=True)
    log_path = candidates[0][1]
    logger.info("selected inspect log path=%s task=%s", log_path, task_name)
    log_data, raw = read_inspect_log_file(log_path)
    return log_path, log_data, raw
