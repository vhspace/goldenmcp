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
    # Per-sample wall cap passed to Inspect (time_limit); bounds a slow/unreachable
    # MCP so the run finishes-and-scores instead of stalling until the subprocess
    # kill at eval_inspect_timeout. Keep < eval_inspect_timeout and < CRE poll budget.
    eval_inspect_time_limit: int = 150
    eval_inspect_model: str = "together/google/gemma-4-31B-it"


@lru_cache
def get_settings() -> RunnerSettings:
    return RunnerSettings()
