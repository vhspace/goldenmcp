"""Walrus prefix existence for Inspect log-dir listing."""

from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


def test_exists_returns_true_for_prefix_with_entries():
    fs = WalrusFileSystem(index=WalrusIndex())
    fs.index.register("evals/goldenmcp/a.eval", blob_id="1", size=1, mtime=1.0)
    assert fs.exists("walrus://evals/goldenmcp")
