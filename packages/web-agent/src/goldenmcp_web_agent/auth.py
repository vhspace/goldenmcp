"""Bearer auth for web-agent mutating endpoints."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from goldenmcp_web_agent.settings import WebAgentSettings, get_settings

_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: WebAgentSettings = Depends(get_settings),
) -> None:
    expected = settings.web_agent_api_key
    if not expected:
        return
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    if not secrets.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid Authorization Bearer token")
