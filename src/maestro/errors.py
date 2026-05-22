"""Error taxonomy for Maestro.

All tool errors are structured Pydantic models (the *Error subclasses).
Tools return these in OK/Err envelopes — Claude needs structured info
to decide next steps; stack traces are useless to it.

Internal helpers (clients, validators) raise MaestroException carrying
a MaestroError payload. The MCP tool boundary catches and converts
back to a structured response, so the "no raise to Claude" rule still
holds end-to-end.
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


# --- Auth + connectivity (apply to any HTTP-backed domain) ---


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


# --- Schema + upstream contract drift ---


class SchemaError(MaestroError):
    code: str = "schema_error"
    message: str = "Schema mismatch — upstream may have changed"
    suggestion: str | None = "Run scripts/regen_aiostreams_schemas.sh and review the diff"
    is_transient: bool = False


class UpstreamError(MaestroError):
    code: str = "upstream_error"
    message: str = "Upstream returned a server error"
    is_transient: bool = True


# --- Stremio addon-protocol failures ---


class AddonTimeout(MaestroError):
    code: str = "addon_timeout"
    domain: str = "stremio"
    is_transient: bool = True


class AddonMalformed(MaestroError):
    code: str = "addon_malformed"
    domain: str = "stremio"
    is_transient: bool = False


# --- Real-Debrid filter-gate ---


class FilterGateStrike(MaestroError):
    """Recorded when RD's May 2026 filter-gate blocks a previously-cached file.

    Carries the offending filename, the RD error code, and any keywords
    the runtime learner extracted so the composer can avoid sibling
    candidates that share the same trigger pattern.
    """

    code: str = "filter_gate_strike"
    domain: str = "realdebrid"
    message: str = "RD blocked file under May 2026 filter-gate"
    is_transient: bool = False

    filename: str
    rd_error_code: str
    learned_keywords: list[str] = Field(default_factory=list)


# --- Composer (find_best_stream) ---


class NoStreamsAvailable(MaestroError):
    code: str = "no_streams_available"
    domain: str = "compose"


class TitleUnresolved(MaestroError):
    code: str = "title_unresolved"
    domain: str = "compose"
    suggestion: str | None = "Pass imdb_id directly if you have it"


class CompositionFailure(MaestroError):
    """Returned when the composer exhausted all candidates without resolving.

    ``attempts`` carries one dict per candidate tried, with whatever the
    composer recorded for debugging (rejection reason, RD response code,
    filter-gate strike payload, etc.).
    """

    code: str = "composition_failure"
    domain: str = "compose"
    attempts: list[dict[str, Any]] = Field(default_factory=list)


class MaestroException(Exception):
    """Control-flow wrapper carrying a structured MaestroError payload.

    Internal helpers (HTTP clients, validators) raise this to surface
    structured errors up to the MCP tool boundary, where the boundary
    catches it and returns `e.error.model_dump()` to Claude. The MCP
    boundary never sees a Python traceback — only the structured payload.

    Pattern:
        raise MaestroException(AuthError(domain="aiostreams", suggestion="..."))

    At the boundary:
        try:
            return await toolset.get_config()
        except MaestroException as e:
            return e.error.model_dump()
    """

    def __init__(self, error: MaestroError) -> None:
        self.error = error
        super().__init__(error.message)
