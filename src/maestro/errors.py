"""Error taxonomy for Maestro.

All tool errors are structured Pydantic models. Tools never raise to Claude;
they return either OK[T] or these Error[E] variants. Claude needs structured
info to decide next steps — stack traces are useless.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Domain = Literal["aiostreams", "torrentio", "realdebrid", "stremio", "compose", "diagnose"]


class MaestroError(BaseModel):
    """Base error shape returned by every tool."""

    code: str
    message: str = ""
    domain: str
    suggestion: str | None = None
    retry_after_s: float | None = None
    is_transient: bool = False


class AuthError(MaestroError):
    code: str = "auth_error"
    message: str = "Authentication failed"
    is_transient: bool = False


class InstanceError(MaestroError):
    code: str = "instance_error"
    message: str = "Instance not found or unreachable"
    is_transient: bool = False


class RateLimitError(MaestroError):
    code: str = "rate_limit"
    message: str = "Upstream rate limit hit"
    is_transient: bool = True


class SchemaError(MaestroError):
    code: str = "schema_error"
    message: str = "Schema mismatch — upstream may have changed"
    suggestion: str | None = "Run scripts/regen_aiostreams_schemas.sh and review the diff"
    is_transient: bool = False


class UpstreamError(MaestroError):
    code: str = "upstream_error"
    message: str = "Upstream returned a server error"
    is_transient: bool = True


class AddonTimeout(MaestroError):
    code: str = "addon_timeout"
    domain: str = "stremio"
    is_transient: bool = True


class AddonMalformed(MaestroError):
    code: str = "addon_malformed"
    domain: str = "stremio"
    is_transient: bool = False


class FilterGateStrike(MaestroError):
    code: str = "filter_gate_strike"
    domain: str = "realdebrid"
    message: str = "RD blocked file under May 2026 filter-gate"
    is_transient: bool = False

    filename: str
    rd_error_code: str
    learned_keywords: list[str] = Field(default_factory=list)


class NoStreamsAvailable(MaestroError):
    code: str = "no_streams_available"
    domain: str = "compose"


class TitleUnresolved(MaestroError):
    code: str = "title_unresolved"
    domain: str = "compose"
    suggestion: str | None = "Pass imdb_id directly if you have it"


class CompositionFailure(MaestroError):
    code: str = "composition_failure"
    domain: str = "compose"
    attempts: list[dict[str, Any]] = Field(default_factory=list)
