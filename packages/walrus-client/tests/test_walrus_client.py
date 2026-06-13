"""Walrus storage integration tests — require WALRUS_* env vars."""

import os

import pytest

from goldenmcp_walrus import WalrusClient, WalrusError


def _walrus_configured() -> bool:
    return bool(os.environ.get("WALRUS_PUBLISHER_URL") and os.environ.get("WALRUS_AGGREGATOR_URL"))


@pytest.mark.skipif(not _walrus_configured(), reason="WALRUS_PUBLISHER_URL and WALRUS_AGGREGATOR_URL required")
def test_upload_and_download_roundtrip():
    client = WalrusClient()
    payload = b"goldenmcp walrus integration test"
    blob_id = client.upload(payload, content_type="text/plain")
    assert blob_id
    downloaded = client.download(blob_id)
    assert downloaded == payload


@pytest.mark.skipif(not _walrus_configured(), reason="WALRUS env required")
def test_upload_json():
    client = WalrusClient()
    blob_id = client.upload_json({"test": True, "project": "goldenmcp"})
    data = client.download_json(blob_id)
    assert data["project"] == "goldenmcp"


def test_missing_env_raises():
    if os.environ.get("WALRUS_PUBLISHER_URL"):
        pytest.skip("env is set")
    with pytest.raises(KeyError):
        WalrusClient()
