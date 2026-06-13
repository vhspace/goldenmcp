"""Bearer auth and CAI webhook secret validation for eval-runner."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from goldenmcp_eval_runner.settings import RunnerSettings, get_settings

_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: RunnerSettings = Depends(get_settings),
) -> None:
    """Reject mutating requests when API key is unset or bearer token is wrong."""
    expected = settings.eval_runner_api_key
    if not expected:
        raise HTTPException(
            status_code=401,
            detail="EVAL_RUNNER_API_KEY is not configured — refusing unauthenticated mutating requests",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization Bearer token required")
    if credentials.credentials != expected:
        raise HTTPException(status_code=401, detail="Invalid Authorization Bearer token")


def require_cai_webhook_secret(
    request: Request,
    settings: RunnerSettings = Depends(get_settings),
) -> None:
    """Validate CAI cre_callback webhook shared secret."""
    expected = settings.cai_webhook_secret
    if not expected:
        raise HTTPException(
            status_code=401,
            detail="CAI_WEBHOOK_SECRET is not configured — refusing CAI webhook requests",
        )

    header_secret = request.headers.get("X-CAI-Webhook-Secret")
    auth_header = request.headers.get("Authorization")
    bearer_secret = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_secret = auth_header[7:].strip()

    if header_secret == expected or bearer_secret == expected:
        return

    raise HTTPException(status_code=401, detail="Invalid CAI webhook secret")
