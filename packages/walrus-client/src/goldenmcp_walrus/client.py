"""Walrus HTTP client for publisher and aggregator APIs."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WalrusError(Exception):
    """Walrus API error with verbose context."""


def parse_upload_blob_id(result: dict[str, Any]) -> str | None:
    """Extract blob ID from Walrus publisher PUT /v1/blobs JSON response."""
    for key in ("blobId", "blob_id", "id"):
        value = result.get(key)
        if value:
            return str(value)

    newly_created = result.get("newlyCreated")
    if isinstance(newly_created, dict):
        blob_object = newly_created.get("blobObject")
        if isinstance(blob_object, dict):
            blob_id = blob_object.get("blobId") or blob_object.get("blob_id")
            if blob_id:
                return str(blob_id)

    already_certified = result.get("alreadyCertified")
    if isinstance(already_certified, dict):
        blob_id = already_certified.get("blobId") or already_certified.get("blob_id")
        if blob_id:
            return str(blob_id)

    return None


class WalrusClient:
    def __init__(
        self,
        *,
        publisher_url: str | None = None,
        aggregator_url: str | None = None,
        epochs: int | None = None,
        timeout: float = 120.0,
    ):
        if publisher_url and aggregator_url:
            self.publisher_url = publisher_url.rstrip("/")
            self.aggregator_url = aggregator_url.rstrip("/")
        else:
            self.publisher_url = os.environ["WALRUS_PUBLISHER_URL"].rstrip("/")
            self.aggregator_url = os.environ["WALRUS_AGGREGATOR_URL"].rstrip("/")
        self.epochs = epochs or int(os.environ.get("WALRUS_EPOCHS", "1"))
        self.timeout = timeout
        logger.info(
            "WalrusClient publisher=%s aggregator=%s epochs=%s",
            self.publisher_url,
            self.aggregator_url,
            self.epochs,
        )

    def upload(self, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Upload blob via publisher; returns blob ID."""
        url = f"{self.publisher_url}/v1/blobs"
        params = {"epochs": self.epochs}
        headers = {"Content-Type": content_type}
        logger.info("uploading %d bytes to Walrus publisher", len(data))
        with httpx.Client(timeout=self.timeout) as client:
            response = client.put(url, params=params, content=data, headers=headers)
            if response.status_code >= 400:
                raise WalrusError(
                    f"Walrus upload failed: status={response.status_code} body={response.text}"
                )
            result = response.json()
            blob_id = parse_upload_blob_id(result)
            if not blob_id:
                raise WalrusError(f"Walrus upload response missing blob ID: {result}")
            logger.info("uploaded blob_id=%s", blob_id)
            return str(blob_id)

    def download(self, blob_id: str) -> bytes:
        """Download blob via aggregator."""
        url = f"{self.aggregator_url}/v1/blobs/{blob_id}"
        logger.info("downloading blob_id=%s from Walrus aggregator", blob_id)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url)
            if response.status_code >= 400:
                raise WalrusError(
                    f"Walrus download failed: blob_id={blob_id} "
                    f"status={response.status_code} body={response.text}"
                )
            return response.content

    def upload_json(self, payload: dict[str, Any]) -> str:
        import json

        return self.upload(json.dumps(payload, indent=2).encode(), content_type="application/json")

    def download_json(self, blob_id: str) -> dict[str, Any]:
        import json

        return json.loads(self.download(blob_id).decode())
