"""Issue #10 acceptance: every golden task run produces a manifest with 3 dimension scores.

For each golden benchmark we synthesise a passing transcript (tool calls matching the
golden path, output satisfying expected_data) and assert that `build_manifest` yields a
manifest carrying all three dimension scores. Runs fully offline — no MCP, no model key.
"""

from __future__ import annotations

from typing import Any

import pytest

from goldenmcp_inspect.benchmarks import list_benchmarks, load_benchmark
from goldenmcp_inspect.manifest import build_manifest
from goldenmcp_inspect.schemas import EvalTranscript, GoldenBenchmark, TranscriptEvent

BENCHMARKS = list_benchmarks()


def test_at_least_nine_task_runs():
    # 6 MCPs x ~2 capabilities -> 12 golden task runs (>= 9 per the rounded-out acceptance).
    assert len(BENCHMARKS) >= 9


def _value_for_spec(spec: Any) -> Any:
    if isinstance(spec, dict):
        if "min" in spec:
            return spec["min"]
        if "max" in spec:
            return spec["max"]
        if "equals" in spec:
            return spec["equals"]
        if "contains" in spec:
            return f"golden-{spec['contains']}-value"
    return spec


def _set_nested(target: dict[str, Any], keys: list[str], value: Any) -> None:
    cur = target
    for key in keys[:-1]:
        cur = cur.setdefault(key, {})
    cur[keys[-1]] = value


def _passing_output(benchmark: GoldenBenchmark) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, spec in benchmark.expected_data.items():
        if key == "policy":
            continue
        _set_nested(out, key.split("."), _value_for_spec(spec))
    return out


def _passing_transcript(benchmark: GoldenBenchmark) -> EvalTranscript:
    return EvalTranscript(
        mcp=benchmark.mcp,
        capability=benchmark.capability,
        events=[
            TranscriptEvent(kind="tool", tool_name=tool)
            for tool in benchmark.expected_path
        ],
        final_output=_passing_output(benchmark),
        total_tokens=max(1, benchmark.baseline_tokens // 2),
    )


@pytest.mark.parametrize("mcp,capability", BENCHMARKS, ids=[f"{m}/{c}" for m, c in BENCHMARKS])
def test_benchmark_produces_manifest_with_three_dimension_scores(mcp: str, capability: str):
    benchmark = load_benchmark(mcp, capability)
    transcript = _passing_transcript(benchmark)
    manifest = build_manifest(transcript, benchmark, run_id=f"coverage-{mcp}-{capability}")

    assert manifest.mcp == mcp
    assert manifest.capability == capability
    assert not manifest.failed, manifest.fail_reason
    # All three dimensions present...
    for dimension in ("data_score", "path_score", "token_efficiency"):
        score = getattr(manifest, dimension)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
    # ...and a real composite from a clean (non-security-failed) run.
    assert manifest.composite > 0.0
