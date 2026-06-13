"""Walrus fsspec filesystem index integration (in-memory client, no network)."""

from __future__ import annotations

import pytest

from goldenmcp_walrus.client import WalrusClient
from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


class InMemoryWalrusClient(WalrusClient):
    """Test double storing blobs in RAM; no HTTP."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.publisher_url = "http://memory"
        self.aggregator_url = "http://memory"
        self.epochs = 1
        self.timeout = 1.0

    def upload(self, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        blob_id = f"mem-{len(self.blobs)}"
        self.blobs[blob_id] = data
        return blob_id

    def download(self, blob_id: str) -> bytes:
        try:
            return self.blobs[blob_id]
        except KeyError as exc:
            from goldenmcp_walrus.client import WalrusError

            raise WalrusError(f"missing blob {blob_id}") from exc


@pytest.fixture
def walrus_fs() -> WalrusFileSystem:
    client = InMemoryWalrusClient()
    index = WalrusIndex()
    return WalrusFileSystem(client=client, index=index)


def test_strip_protocol_is_classmethod():
    assert WalrusFileSystem._strip_protocol("walrus://evals/foo.eval") == "evals/foo.eval"


def test_write_then_read_roundtrip(walrus_fs: WalrusFileSystem):
    path = "walrus://evals/goldenmcp/test.eval"
    payload = b"inspect-eval-bytes"
    walrus_fs.pipe_file(path, payload)
    assert walrus_fs.cat_file(path) == payload


def test_ls_lists_registered_eval_under_prefix(walrus_fs: WalrusFileSystem):
    walrus_fs.pipe_file("walrus://evals/goldenmcp/a.eval", b"a")
    walrus_fs.pipe_file("walrus://evals/goldenmcp/b.eval", b"bb")
    listing = walrus_fs.ls("walrus://evals/goldenmcp", detail=True)
    names = sorted(entry["name"] for entry in listing)
    assert names == [
        "walrus://evals/goldenmcp/a.eval",
        "walrus://evals/goldenmcp/b.eval",
    ]


def test_info_returns_size_and_mtime(walrus_fs: WalrusFileSystem):
    path = "walrus://evals/goldenmcp/sized.eval"
    walrus_fs.pipe_file(path, b"12345")
    info = walrus_fs.info(path)
    assert info["type"] == "file"
    assert info["size"] == 5
    assert info["mtime"] is not None
