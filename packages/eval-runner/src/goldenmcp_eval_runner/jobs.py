"""In-memory eval job store for async inspect/publish (bounded, single-process)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from typing import Any

from goldenmcp_inspect.schemas import EvalTranscript, ScoreManifest

MAX_EVAL_JOBS = 100


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SCORED = "scored"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class EvalJob:
    run_id: str
    mcp: str
    capability: str
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None
    manifest: ScoreManifest | None = None
    transcript: EvalTranscript | None = None
    inspect_log_bytes: bytes | None = None
    inspect_log_path: str | None = None
    walrus_manifest_blob_id: str | None = None
    walrus_eval_blob_id: str | None = None
    walrus_index_blob_id: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "mcp": self.mcp,
            "capability": self.capability,
            "status": self.status,
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.manifest is not None:
            payload["manifest"] = self.manifest.to_public_dict()
        if self.walrus_manifest_blob_id is not None:
            payload["walrus_manifest_blob_id"] = self.walrus_manifest_blob_id
        if self.walrus_eval_blob_id is not None:
            payload["walrus_eval_blob_id"] = self.walrus_eval_blob_id
        if self.walrus_index_blob_id is not None:
            payload["walrus_index_blob_id"] = self.walrus_index_blob_id
        return payload


class EvalJobStore:
    def __init__(self, max_size: int = MAX_EVAL_JOBS) -> None:
        self._jobs: OrderedDict[str, EvalJob] = OrderedDict()
        self._max_size = max_size
        self._lock = Lock()

    def create(self, run_id: str, mcp: str, capability: str, status: JobStatus = JobStatus.QUEUED) -> EvalJob:
        with self._lock:
            if run_id in self._jobs:
                del self._jobs[run_id]
            while len(self._jobs) >= self._max_size:
                self._jobs.popitem(last=False)
            job = EvalJob(run_id=run_id, mcp=mcp, capability=capability, status=status)
            self._jobs[run_id] = job
            return job

    def get(self, run_id: str) -> EvalJob | None:
        with self._lock:
            return self._jobs.get(run_id)

    def update(self, run_id: str, **fields: Any) -> EvalJob | None:
        with self._lock:
            job = self._jobs.get(run_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            return job

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)


eval_jobs = EvalJobStore()
