"""Walrus fsspec filesystem index integration (in-memory client, no network)."""

from __future__ import annotations

import fsspec.core
import pytest

from goldenmcp_walrus.testing import InMemoryWalrusClient
from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


@pytest.fixture
def walrus_fs() -> WalrusFileSystem:
    client = InMemoryWalrusClient()
    index = WalrusIndex()
    return WalrusFileSystem(client=client, index=index)


def test_strip_protocol_is_classmethod():
    assert WalrusFileSystem._strip_protocol("walrus://evals/foo.eval") == "evals/foo.eval"


def test_fsspec_url_to_fs_walrus_log_dir():
    """Inspect View calls fsspec.core.url_to_fs(log_dir) before listing logs."""
    fs, path = fsspec.core.url_to_fs("walrus://evals/goldenmcp")
    assert isinstance(fs, WalrusFileSystem)
    assert path == "evals/goldenmcp"


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
