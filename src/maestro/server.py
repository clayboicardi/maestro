"""Maestro MCP server entry point.

Boots a FastMCP stdio server. Tools land here via domain-module
register_* functions in later phases.
"""

from __future__ import annotations

import sys

import structlog
from fastmcp import FastMCP

from maestro.config import MaestroSettings
from maestro.logging import configure_logging


def create_server() -> FastMCP:
    """Construct and return the configured FastMCP app.

    Reads settings from env, configures logging, returns the bare app
    without tools. Domain register_* functions wire tools.
    """
    settings = MaestroSettings()  # pyright: ignore[reportCallIssue] - pydantic-settings sources required fields from env
    configure_logging(format=settings.log_format, level=settings.log_level)

    log = structlog.get_logger("maestro.server")
    log.info(
        "server_starting",
        aiostreams_base_url=str(settings.aiostreams_base_url),
        torrentio_base_url=str(settings.torrentio_base_url),
        http_timeout_s=settings.http_timeout_s,
    )

    mcp = FastMCP(name="maestro")
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
