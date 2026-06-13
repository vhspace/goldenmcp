"""Load golden benchmarks from YAML files."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from goldenmcp_inspect.schemas import GoldenBenchmark

logger = logging.getLogger(__name__)


def golden_path() -> Path:
    env_root = Path(__file__).resolve().parents[4]
    candidate = env_root / "benchmarks" / "golden"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"benchmarks/golden not found at {candidate}")


def load_benchmark(mcp: str, capability: str) -> GoldenBenchmark:
    root = golden_path()
    path = root / mcp / f"{capability}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"golden benchmark not found: {path}")

    with path.open() as f:
        data = yaml.safe_load(f)

    logger.info("loaded benchmark %s/%s from %s", mcp, capability, path)
    return GoldenBenchmark(mcp=mcp, capability=capability, **data)


def list_benchmarks() -> list[tuple[str, str]]:
    root = golden_path()
    results: list[tuple[str, str]] = []
    for mcp_dir in sorted(root.iterdir()):
        if not mcp_dir.is_dir():
            continue
        for yaml_file in sorted(mcp_dir.glob("*.yaml")):
            results.append((mcp_dir.name, yaml_file.stem))
    return results
