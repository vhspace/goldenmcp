"""Test helpers for Walrus client (used by integration tests only)."""

from __future__ import annotations

from goldenmcp_walrus.client import WalrusClient, WalrusError


class InMemoryWalrusClient(WalrusClient):
    """In-RAM Walrus client for unit tests (no HTTP)."""

    def __init__(self) -> None:
        super().__init__(publisher_url="http://memory", aggregator_url="http://memory")
        self.blobs: dict[str, bytes] = {}

    def upload(self, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        blob_id = f"mem-{len(self.blobs)}"
        self.blobs[blob_id] = data
        return blob_id

    def download(self, blob_id: str) -> bytes:
        try:
            return self.blobs[blob_id]
        except KeyError as exc:
            raise WalrusError(f"missing blob {blob_id}") from exc
