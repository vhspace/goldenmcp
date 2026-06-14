"""Web agent settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WebAgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    web_agent_host: str = "0.0.0.0"
    web_agent_port: int = 8092
    web_agent_api_key: str | None = None
    web_agent_model: str = "anthropic/claude-sonnet-4-20250514"
    marketplace_url: str = "http://localhost:8091"
    # Path to marketplace-mcp-ts for bun x402 deps (Circle Gateway client).
    marketplace_mcp_ts_root: str = ""


@lru_cache
def get_settings() -> WebAgentSettings:
    return WebAgentSettings()
