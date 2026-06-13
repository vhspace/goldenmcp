"""Eval-runner configuration from environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RunnerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    eval_runner_host: str = "0.0.0.0"
    eval_runner_port: int = 8090
    eval_runner_api_key: str | None = None
    cai_webhook_secret: str | None = None
    eval_inspect_timeout: int = 600


@lru_cache
def get_settings() -> RunnerSettings:
    return RunnerSettings()
