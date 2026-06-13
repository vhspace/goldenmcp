"""Walrus logical-path index tests (no network)."""

from __future__ import annotations

from goldenmcp_walrus.index import WalrusIndex, WalrusIndexEntry


def test_register_and_resolve_path():
    index = WalrusIndex()
    index.register(
        "evals/goldenmcp/2026-06-13T12-00-00_goldenmcp_lifi_quote_run.eval",
        blob_id="blob-abc",
        size=100,
        mtime=1710000000.0,
    )
    entry = index.resolve("evals/goldenmcp/2026-06-13T12-00-00_goldenmcp_lifi_quote_run.eval")
    assert entry is not None
    assert entry.blob_id == "blob-abc"
    assert entry.size == 100


def test_list_prefix_returns_matching_files():
    index = WalrusIndex()
    index.register("evals/goldenmcp/a.eval", blob_id="1", size=1, mtime=1.0)
    index.register("evals/goldenmcp/b.eval", blob_id="2", size=2, mtime=2.0)
    index.register("evals/other/c.eval", blob_id="3", size=3, mtime=3.0)

    names = [e.path for e in index.list_prefix("evals/goldenmcp")]
    assert names == [
        "evals/goldenmcp/a.eval",
        "evals/goldenmcp/b.eval",
    ]


def test_list_prefix_trailing_slash():
    index = WalrusIndex()
    index.register("evals/goldenmcp/a.eval", blob_id="1", size=1, mtime=1.0)
    assert len(index.list_prefix("evals/goldenmcp/")) == 1


def test_to_json_roundtrip():
    index = WalrusIndex()
    index.register("evals/x.eval", blob_id="blob-x", size=9, mtime=42.0)
    restored = WalrusIndex.from_json(index.to_json())
    entry = restored.resolve("evals/x.eval")
    assert entry == WalrusIndexEntry(path="evals/x.eval", blob_id="blob-x", size=9, mtime=42.0)


def test_normalize_path_strips_walrus_protocol():
    index = WalrusIndex()
    index.register("evals/a.eval", blob_id="id", size=1, mtime=1.0)
    assert index.resolve("walrus://evals/a.eval") is not None
