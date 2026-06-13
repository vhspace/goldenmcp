"""walrus:// fsspec filesystem for Inspect eval logs."""

from __future__ import annotations

import logging
import os
import time
from io import BytesIO
from typing import Any

import fsspec
from fsspec.spec import AbstractBufferedFile, AbstractFileSystem

from goldenmcp_walrus.client import WalrusClient
from goldenmcp_walrus.index import WalrusIndex

logger = logging.getLogger(__name__)

INDEX_ENV_VAR = "WALRUS_INDEX_BLOB_ID"


def _looks_like_blob_id(path: str) -> bool:
    """Heuristic: Walrus blob IDs are single path segments without slashes."""
    return "/" not in path and len(path) >= 8


class WalrusFileSystem(AbstractFileSystem):
    protocol = "walrus"

    def __init__(
        self,
        *,
        client: WalrusClient | None = None,
        index: WalrusIndex | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._client = client
        self._index = index

    @property
    def client(self) -> WalrusClient:
        if self._client is None:
            self._client = WalrusClient()
        return self._client

    @property
    def index(self) -> WalrusIndex:
        if self._index is None:
            self._index = self._load_index()
        return self._index

    def _load_index(self) -> WalrusIndex:
        blob_id = os.environ.get(INDEX_ENV_VAR)
        if not blob_id:
            return WalrusIndex()
        try:
            index = WalrusIndex.from_bytes(self.client.download(blob_id))
            index.index_blob_id = blob_id
            return index
        except Exception as exc:
            logger.error("failed loading Walrus index blob_id=%s: %s", blob_id, exc)
            raise

    def _persist_index(self) -> None:
        blob_id = self.client.upload(self.index.to_bytes(), content_type="application/json")
        self.index.index_blob_id = blob_id
        logger.info("persisted walrus index blob_id=%s files=%d", blob_id, len(self.index._files))

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        if isinstance(path, list):
            return [cls._strip_protocol(p) for p in path]
        if path.startswith("walrus://"):
            return path[len("walrus://") :]
        return path.lstrip("/")

    def unstrip_protocol(self, name: str) -> str:
        if name.startswith("walrus://"):
            return name
        return f"walrus://{name}"

    def invalidate_cache(self, path: str | None = None) -> None:
        return None

    def _resolve_blob_id(self, path: str) -> str:
        normalized = WalrusIndex.normalize_path(path)
        entry = self.index.resolve(normalized)
        if entry is not None:
            return entry.blob_id
        if _looks_like_blob_id(normalized):
            return normalized
        raise FileNotFoundError(f"No Walrus index entry for path: {path}")

    def ls(self, path: str, detail: bool = True, **kwargs):
        prefix = WalrusIndex.normalize_path(path)
        entries = self.index.list_prefix(prefix)
        if not detail:
            return [self.unstrip_protocol(entry.path) for entry in entries]
        return [
            {
                "name": self.unstrip_protocol(entry.path),
                "type": "file",
                "size": entry.size,
                "mtime": entry.mtime,
            }
            for entry in entries
        ]

    def walk(self, path, maxdepth=None, detail=False, **kwargs):
        prefix = WalrusIndex.normalize_path(path)
        entries = self.index.list_prefix(prefix)
        files = {
            self.unstrip_protocol(entry.path): {
                "name": self.unstrip_protocol(entry.path),
                "type": "file",
                "size": entry.size,
                "mtime": entry.mtime,
            }
            for entry in entries
        }
        dirs: dict[str, Any] = {}
        yield self.unstrip_protocol(prefix) if prefix else "walrus://", dirs, files

    def info(self, path: str, **kwargs) -> dict[str, Any]:
        normalized = WalrusIndex.normalize_path(path)
        entry = self.index.resolve(normalized)
        if entry is None and _looks_like_blob_id(normalized):
            data = self.client.download(normalized)
            return {
                "name": self.unstrip_protocol(normalized),
                "type": "file",
                "size": len(data),
                "mtime": time.time(),
            }
        if entry is None:
            raise FileNotFoundError(path)
        return {
            "name": self.unstrip_protocol(entry.path),
            "type": "file",
            "size": entry.size,
            "mtime": entry.mtime,
        }

    def exists(self, path: str, **kwargs) -> bool:
        normalized = WalrusIndex.normalize_path(path)
        if self.index.resolve(normalized) is not None:
            return True
        if self.index.list_prefix(normalized):
            return True
        if _looks_like_blob_id(normalized):
            try:
                self.client.download(normalized)
                return True
            except Exception:
                return False
        return False

    def cat_file(self, path: str, start=None, end=None, **kwargs) -> bytes:
        blob_id = self._resolve_blob_id(path)
        data = self.client.download(blob_id)
        if start is not None or end is not None:
            return data[start:end]
        return data

    def pipe_file(self, path: str, value, **kwargs):
        if isinstance(value, str):
            value = value.encode()
        blob_id = self.client.upload(value)
        entry = self.index.register(path, blob_id=blob_id, size=len(value))
        self._persist_index()
        logger.info(
            "pipe_file logical_path=%s blob_id=%s size=%d",
            entry.path,
            blob_id,
            entry.size,
        )
        return blob_id

    def open(self, path, mode="rb", block_size=None, autocommit=True, **kwargs):
        return WalrusFile(self, path, mode=mode, block_size=block_size, autocommit=autocommit)


class WalrusFile(AbstractBufferedFile):
    def __init__(self, fs: WalrusFileSystem, path: str, mode="rb", **kwargs):
        super().__init__(fs, path, mode=mode, **kwargs)
        self._buffer = BytesIO()
        self._blob_id: str | None = None
        if "r" in mode:
            data = fs.cat_file(path)
            self._buffer = BytesIO(data)

    def _fetch_range(self, start, end):
        return self.fs.cat_file(self.path, start=start, end=end)

    def _upload(self):
        data = self._buffer.getvalue()
        self._blob_id = self.fs.pipe_file(self.path, data)
        logger.info("committed walrus file path=%s blob_id=%s", self.path, self._blob_id)


fsspec.register_implementation("walrus", WalrusFileSystem)
