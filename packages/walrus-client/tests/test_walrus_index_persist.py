"""Index persistence tests."""

from __future__ import annotations

from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex
from goldenmcp_walrus.testing import InMemoryWalrusClient


def test_persist_index_roundtrip_via_blob():
    client = InMemoryWalrusClient()
    fs = WalrusFileSystem(client=client, index=WalrusIndex())
    fs.pipe_file("walrus://evals/goldenmcp/a.eval", b"log-bytes")

    assert fs.index.index_blob_id is not None
    loaded = WalrusIndex.from_bytes(client.blobs[fs.index.index_blob_id])
    loaded.index_blob_id = fs.index.index_blob_id
    assert loaded.resolve("evals/goldenmcp/a.eval") is not None
