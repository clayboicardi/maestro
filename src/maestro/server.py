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
from maestro.config import MaestroSettings
from maestro.logging import configure_logging
from maestro.torrentio.tools import register_tools as register_torrentio


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
    )

    mcp = FastMCP(name="maestro")
    register_aiostreams(mcp, settings)
    register_torrentio(mcp)
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
