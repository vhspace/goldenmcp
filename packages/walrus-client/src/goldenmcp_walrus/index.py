"""Logical path index for Walrus blob storage (S3-style keys over content-addressed blobs)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WalrusIndexEntry:
    path: str
    blob_id: str
    size: int
    mtime: float


class WalrusIndex:
    """Maps walrus logical paths to blob IDs for listing and reads."""

    def __init__(self, *, index_blob_id: str | None = None) -> None:
        self.index_blob_id = index_blob_id
        self._files: dict[str, WalrusIndexEntry] = {}

    @staticmethod
    def normalize_path(path: str) -> str:
        if path.startswith("walrus://"):
            path = path[len("walrus://") :]
        return path.strip("/")

    def register(
        self,
        path: str,
        *,
        blob_id: str,
        size: int,
        mtime: float | None = None,
    ) -> WalrusIndexEntry:
        key = self.normalize_path(path)
        entry = WalrusIndexEntry(
            path=key,
            blob_id=blob_id,
            size=size,
            mtime=mtime if mtime is not None else time.time(),
        )
        self._files[key] = entry
        return entry

    def resolve(self, path: str) -> WalrusIndexEntry | None:
        return self._files.get(self.normalize_path(path))

    def list_prefix(self, prefix: str) -> list[WalrusIndexEntry]:
        key = self.normalize_path(prefix)
        if key and not key.endswith("/"):
            key = f"{key}/"
        if not key:
            entries = list(self._files.values())
        else:
            entries = [entry for entry in self._files.values() if entry.path.startswith(key)]
        return sorted(entries, key=lambda e: e.path)

    def to_json(self) -> dict[str, Any]:
        return {
            "files": {
                path: {
                    "blob_id": entry.blob_id,
                    "size": entry.size,
                    "mtime": entry.mtime,
                }
                for path, entry in sorted(self._files.items())
            },
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> WalrusIndex:
        index = cls(index_blob_id=payload.get("index_blob_id"))
        files = payload.get("files", {})
        if isinstance(files, dict):
            for path, meta in files.items():
                if not isinstance(meta, dict):
                    continue
                blob_id = meta.get("blob_id")
                if not blob_id:
                    continue
                index.register(
                    str(path),
                    blob_id=str(blob_id),
                    size=int(meta.get("size", 0)),
                    mtime=float(meta.get("mtime", 0.0)),
                )
        return index

    def to_bytes(self) -> bytes:
        return json.dumps(self.to_json(), indent=2).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> WalrusIndex:
        return cls.from_json(json.loads(data.decode()))
