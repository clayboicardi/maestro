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
    """Server-wide settings, loaded once at startup.

    All vars use the ``MAESTRO_`` prefix and are case-insensitive
    (``MAESTRO_RD_TOKEN`` and ``maestro_rd_token`` both bind).

    Required (no default; raises ``ValidationError`` if missing):

    - ``MAESTRO_RD_TOKEN`` — Real-Debrid API token (``SecretStr``)
    - ``MAESTRO_AIOSTREAMS_BASE_URL`` — AIOStreams instance URL
    - ``MAESTRO_AIOSTREAMS_UUID`` — per-user UUID
    - ``MAESTRO_AIOSTREAMS_PASSWORD`` — basic-auth password (``SecretStr``)

    Optional (sensible defaults):

    - ``MAESTRO_TORRENTIO_BASE_URL`` — defaults to public Torrentio
    - ``MAESTRO_HTTP_TIMEOUT_S`` — per-request timeout, default 15s
    - ``MAESTRO_RETRY_ATTEMPTS`` — per-domain retry budget, default 3
    - ``MAESTRO_COMPOSE_BUDGET_S`` — total composer budget, default 60s
    - ``MAESTRO_COMPOSE_CANDIDATE_TIMEOUT_S`` — per-candidate within composer, default 10s
    - ``MAESTRO_LOG_FORMAT`` — ``json`` (default) or ``console``
    - ``MAESTRO_LOG_LEVEL`` — standard stdlib level, default ``INFO``
    - ``MAESTRO_FILTER_GATE_STATE_PATH`` — persistent filter-gate state, default ``~/.config/maestro/filter_gate_state.json``

    Secrets use ``SecretStr`` so they never appear in repr output or
    structured-log dumps. Compare with ``.get_secret_value()``; Pydantic
    v2's ``SecretStr.__eq__`` does NOT compare to plain strings.
    """

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
