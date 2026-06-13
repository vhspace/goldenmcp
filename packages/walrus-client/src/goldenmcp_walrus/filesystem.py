"""walrus:// fsspec filesystem for Inspect eval logs."""

from __future__ import annotations

import logging
from io import BytesIO
from urllib.parse import urlparse

import fsspec
from fsspec.spec import AbstractBufferedFile, AbstractFileSystem

from goldenmcp_walrus.client import WalrusClient

logger = logging.getLogger(__name__)


class WalrusFileSystem(AbstractFileSystem):
    protocol = "walrus"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client: WalrusClient | None = None

    @property
    def client(self) -> WalrusClient:
        if self._client is None:
            self._client = WalrusClient()
        return self._client

    def _strip_protocol(self, path: str) -> str:
        if path.startswith("walrus://"):
            return path[len("walrus://") :]
        return path.lstrip("/")

    def ls(self, path: str, detail: bool = True, **kwargs):
        raise NotImplementedError(
            "Walrus does not support directory listing. Use known blob IDs from score manifests."
        )

    def exists(self, path: str, **kwargs) -> bool:
        blob_id = self._strip_protocol(path)
        try:
            self.client.download(blob_id)
            return True
        except Exception as exc:
            logger.error("walrus exists check failed for %s: %s", blob_id, exc)
            return False

    def cat_file(self, path: str, start=None, end=None, **kwargs) -> bytes:
        blob_id = self._strip_protocol(path)
        data = self.client.download(blob_id)
        if start is not None or end is not None:
            return data[start:end]
        return data

    def pipe_file(self, path: str, value, **kwargs):
        blob_id = self._strip_protocol(path)
        if isinstance(value, str):
            value = value.encode()
        uploaded = self.client.upload(value)
        logger.info("pipe_file logical_path=%s uploaded_blob_id=%s", blob_id, uploaded)
        return uploaded

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
        self._blob_id = self.fs.client.upload(data)
        logger.info("committed walrus file path=%s blob_id=%s", self.path, self._blob_id)


# Register with fsspec
fsspec.register_implementation("walrus", WalrusFileSystem)
