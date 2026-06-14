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


pending_runs = PendingRunStore()
cai_callbacks = CaiCallbackStore()
inference_index = InferenceIndex()
