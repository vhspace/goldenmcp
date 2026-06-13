"""Walrus directory prefix info for Inspect log-dir."""

from goldenmcp_walrus.filesystem import WalrusFileSystem
from goldenmcp_walrus.index import WalrusIndex


def test_info_on_prefix_returns_directory():
    fs = WalrusFileSystem(index=WalrusIndex())
    fs.index.register("evals/goldenmcp/a.eval", blob_id="1", size=1, mtime=1.0)
    info = fs.info("walrus://evals/goldenmcp")
    assert info["type"] == "directory"
