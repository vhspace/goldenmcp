"""In-memory stores for score/inspect runs and CAI callbacks (bounded, single-process)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from goldenmcp_inspect.schemas import EvalTranscript, ScoreManifest

MAX_PENDING_RUNS = 100
MAX_CAI_CALLBACKS = 100
MAX_INFERENCE_INDEX = 100


@dataclass
class PendingRun:
    manifest: ScoreManifest
    transcript: EvalTranscript | None = None
    inspect_log_bytes: bytes | None = None
    inspect_log_path: str | None = None


class PendingRunStore:
    def __init__(self, max_size: int = MAX_PENDING_RUNS) -> None:
        self._runs: OrderedDict[str, PendingRun] = OrderedDict()
        self._max_size = max_size

    def put(self, run_id: str, run: PendingRun) -> None:
        if run_id in self._runs:
            del self._runs[run_id]
        while len(self._runs) >= self._max_size:
            self._runs.popitem(last=False)
        self._runs[run_id] = run

    def pop(self, run_id: str) -> PendingRun | None:
        return self._runs.pop(run_id, None)

    def __len__(self) -> int:
        return len(self._runs)


class CaiCallbackStore:
    def __init__(self, max_size: int = MAX_CAI_CALLBACKS) -> None:
        self._by_run_id: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size

    def put(self, input_data: dict[str, Any]) -> str | None:
        run_id = input_data.get("run_id")
        if not run_id or not isinstance(run_id, str):
            return None
        if run_id in self._by_run_id:
            del self._by_run_id[run_id]
        while len(self._by_run_id) >= self._max_size:
            self._by_run_id.popitem(last=False)
        self._by_run_id[run_id] = input_data
        return run_id

    def pop(self, run_id: str) -> dict[str, Any] | None:
        return self._by_run_id.pop(run_id, None)

    def __len__(self) -> int:
        return len(self._by_run_id)


class InferenceIndex:
    """Maps a CAI inference id -> the eval run_id that submitted it.

    The CRE HTTP-trigger payload carries only the CAI status (no run_id), so the
    inference id in that status is the only handle back to the run. Handler A
    registers the mapping right after submitting to CAI.
    """

    def __init__(self, max_size: int = MAX_INFERENCE_INDEX) -> None:
        self._by_inference_id: OrderedDict[str, str] = OrderedDict()
        self._max_size = max_size

    def put(self, inference_id: str, run_id: str) -> None:
        if inference_id in self._by_inference_id:
            del self._by_inference_id[inference_id]
        while len(self._by_inference_id) >= self._max_size:
            self._by_inference_id.popitem(last=False)
        self._by_inference_id[inference_id] = run_id

    def get(self, inference_id: str) -> str | None:
        return self._by_inference_id.get(inference_id)

    def __len__(self) -> int:
        return len(self._by_inference_id)


# Open-weight model ensemble run against every benchmark. Each (benchmark, model)
# pair is its own CRE fire (one live Inspect eval ~ the per-execution HTTP cap),
# so two models can't share a fire. Pairs are emitted ADJACENTLY per benchmark
# (model[0] then model[1]) so the eval-runner can pair the two manifests and
# submit both to one CAI judge that sums across models.
ENSEMBLE_MODELS = (
    "together/Qwen/Qwen3.5-9B",
    "together/google/gemma-4-31B-it",
)


class BenchmarkCursor:
    """Round-robin cursor over (benchmark × model) pairs.

    For `n` benchmarks and `m` models it cycles n*m steps, emitting each
    benchmark's models back-to-back: (b0,m0),(b0,m1),(b1,m0),(b1,m1),...
    In-memory — resets on eval-runner restart, which is fine for the demo.
    """

    def __init__(self, models: tuple[str, ...] = ENSEMBLE_MODELS) -> None:
        self._index = 0
        self._models = models

    def next_pair(self, benchmarks: list[tuple[str, str]]) -> dict[str, object]:
        n = len(benchmarks)
        m = len(self._models)
        if n <= 0 or m <= 0:
            raise ValueError("no benchmarks/models to rotate over")
        total = n * m
        i = self._index % total
        self._index = (self._index + 1) % total
        mcp, capability = benchmarks[i // m]
        model = self._models[i % m]
        return {
            "mcp": mcp,
            "capability": capability,
            "model": model,
            "model_index": i % m,
            "models_total": m,
            "index": i,
            "total": total,
        }

    def peek(self) -> int:
        return self._index


class ManifestPairStore:
    """Pair the two open-weight models' manifests for a benchmark.

    Each (benchmark, model) fire records its run here keyed by `mcp/capability`.
    The first model parks its run_id and waits; the second completes the pair and
    the workflow then submits BOTH manifests to one CAI judge that sums across
    models. In-memory, bounded; resets on restart (fine for the demo).
    """

    def __init__(self, max_size: int = 50) -> None:
        # key -> {model: run_id}
        self._pending: OrderedDict[str, dict[str, str]] = OrderedDict()
        self._max_size = max_size

    @staticmethod
    def _key(mcp: str, capability: str) -> str:
        return f"{mcp}/{capability}"

    def record(self, mcp: str, capability: str, model: str, run_id: str) -> dict[str, str]:
        """Record a model's run for a benchmark; return the current {model: run_id} map."""
        key = self._key(mcp, capability)
        runs = self._pending.get(key)
        if runs is None:
            while len(self._pending) >= self._max_size:
                self._pending.popitem(last=False)
            runs = {}
            self._pending[key] = runs
        runs[model] = run_id
        return dict(runs)

    def complete_and_clear(self, mcp: str, capability: str, expected: int) -> dict[str, str] | None:
        """If the benchmark has `expected` model runs, pop + return them; else None."""
        key = self._key(mcp, capability)
        runs = self._pending.get(key)
        if runs is not None and len(runs) >= expected:
            del self._pending[key]
            return dict(runs)
        return None

    def __len__(self) -> int:
        return len(self._pending)


pending_runs = PendingRunStore()
cai_callbacks = CaiCallbackStore()
inference_index = InferenceIndex()
benchmark_cursor = BenchmarkCursor()
manifest_pairs = ManifestPairStore()
