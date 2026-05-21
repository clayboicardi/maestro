"""Maestro runtime configuration sourced from environment.

All env vars use the MAESTRO_* prefix. Required vars raise pydantic
ValidationError at load time. Secrets use SecretStr so they never leak
into logs or repr output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MaestroSettings(BaseSettings):
    """Server-wide settings, loaded once at startup."""

    model_config = SettingsConfigDict(
        env_prefix="MAESTRO_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    rd_token: SecretStr
    aiostreams_base_url: HttpUrl
    aiostreams_uuid: str
    aiostreams_password: SecretStr

    torrentio_base_url: HttpUrl = HttpUrl("https://torrentio.strem.fun")

    http_timeout_s: float = 15.0
    retry_attempts: int = 3
    compose_budget_s: float = 60.0
    compose_candidate_timeout_s: float = 10.0

    log_format: Literal["json", "console"] = "json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    filter_gate_state_path: str = "~/.config/maestro/filter_gate_state.json"
