"""FastAPI HTTP service for web concierge chat."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from goldenmcp_web_agent.auth import require_api_key
from goldenmcp_web_agent.concierge import stream_chat
from goldenmcp_web_agent.settings import WebAgentSettings, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] | None = None


def _format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app() -> FastAPI:
    app = FastAPI(title="GoldenMCP Web Agent")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "goldenmcp-web-agent"}

    @app.post("/chat")
    async def chat(
        body: ChatRequest,
        _: None = Depends(require_api_key),
        settings: WebAgentSettings = Depends(get_settings),
    ):
        message = body.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="message is required")

        history = (
            [{"role": m.role, "content": m.content} for m in body.history]
            if body.history
            else None
        )

        async def event_generator():
            try:
                async for item in stream_chat(message, history, settings=settings):
                    yield _format_sse(item["event"], item["data"])
            except Exception as exc:
                logger.exception("chat stream failed")
                yield _format_sse("error", {"message": str(exc)})
                yield _format_sse("done", {})

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "goldenmcp_web_agent.runner:app",
        host=settings.web_agent_host,
        port=settings.web_agent_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
