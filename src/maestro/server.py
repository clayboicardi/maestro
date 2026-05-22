"""Maestro MCP server entry point.

Boots a FastMCP stdio server. Tools land here via domain-module
register_* functions in later phases.
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit, urlunsplit

import structlog
from fastmcp import FastMCP

from maestro.aiostreams import register_tools as register_aiostreams
from maestro.compose import register_tools as register_compose
from maestro.config import MaestroSettings
from maestro.diagnose import register_tools as register_diagnose
from maestro.logging import configure_logging
from maestro.middleware import MaestroErrorMiddleware
from maestro.realdebrid import register_tools as register_realdebrid
from maestro.stremio import register_tools as register_stremio
from maestro.torrentio import register_tools as register_torrentio


def _strip_userinfo(url: str) -> str:
    """Drop user:password@ from a URL string before logging.

    Defense in depth: even though Maestro's AIOStreams/RD auth uses
    separate header credentials, never log raw URLs that might contain
    accidentally-embedded userinfo.
    """
    parts = urlsplit(url)
    if parts.username or parts.password:
        netloc = parts.hostname or ""
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return url


def create_server() -> FastMCP:
    """Construct and return the configured FastMCP app.

    Reads settings from env, configures logging, registers domain tools,
    returns the wired app.
    """
    settings = MaestroSettings()  # pyright: ignore[reportCallIssue] - pydantic-settings sources required fields from env
    configure_logging(format=settings.log_format, level=settings.log_level)

    log = structlog.get_logger("maestro.server")
    log.info(
        "server_starting",
        aiostreams_base_url=_strip_userinfo(str(settings.aiostreams_base_url)),
        torrentio_base_url=_strip_userinfo(str(settings.torrentio_base_url)),
        http_timeout_s=settings.http_timeout_s,
        rd_token_present=bool(settings.rd_token.get_secret_value()),
        stremio_active=True,
        compose_active=True,
        compose_budget_s=settings.compose_budget_s,
    )

    mcp = FastMCP(name="maestro")
    mcp.add_middleware(MaestroErrorMiddleware())
    register_aiostreams(mcp, settings)
    register_torrentio(mcp)
    rd_toolset = register_realdebrid(mcp, settings)
    stremio_toolset = register_stremio(mcp, settings)
    register_compose(
        mcp,
        stremio_toolset=stremio_toolset,
        rd_toolset=rd_toolset,
        learner=rd_toolset._learner,
        aiostreams_addon_url=str(settings.aiostreams_base_url),
        compose_budget_s=settings.compose_budget_s,
    )
    register_diagnose(
        mcp,
        addon_urls=[str(settings.aiostreams_base_url), str(settings.torrentio_base_url)],
        rd_get_user_info=rd_toolset._client.get_user_info,
        learner=rd_toolset._learner,
        timeout_s=settings.http_timeout_s,
    )
    return mcp


def main() -> None:
    """Console-script entry: run the server over stdio."""
    try:
        mcp = create_server()
        mcp.run()
    except Exception as e:
        print(f"Maestro failed to start: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
