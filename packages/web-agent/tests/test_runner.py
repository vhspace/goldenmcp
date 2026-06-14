"""FastAPI runner endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from goldenmcp_web_agent.runner import create_app


def test_health():
    client = TestClient(create_app())
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_chat_requires_message():
    client = TestClient(create_app())
    res = client.post("/chat", json={})
    assert res.status_code == 422


def test_chat_rejects_empty_message():
    client = TestClient(create_app())
    res = client.post("/chat", json={"message": "   "})
    assert res.status_code == 400
