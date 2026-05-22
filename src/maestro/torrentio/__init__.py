"""Torrentio domain -- pure-compute URL builder + enum lookups."""

from __future__ import annotations

from fastmcp import FastMCP

from maestro.annotations import pure_compute, read_only
from maestro.torrentio.tools import (
    torrentio_build_url,
    torrentio_list_providers,
    torrentio_list_quality_filters,
    torrentio_parse_url,
    torrentio_validate_config,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all 5 Torrentio tools."""
    mcp.tool(
        name="torrentio_parse_url",
        annotations=read_only(title="Parse Torrentio URL").model_dump(),
    )(torrentio_parse_url)
    mcp.tool(
        name="torrentio_build_url",
        annotations=pure_compute(title="Build Torrentio URL").model_dump(),
    )(torrentio_build_url)
    mcp.tool(
        name="torrentio_validate_config",
        annotations=pure_compute(title="Validate Torrentio Config").model_dump(),
    )(torrentio_validate_config)
    mcp.tool(
        name="torrentio_list_providers",
        annotations=pure_compute(title="List Torrentio Providers").model_dump(),
    )(torrentio_list_providers)
    mcp.tool(
        name="torrentio_list_quality_filters",
        annotations=pure_compute(title="List Torrentio Quality Filters").model_dump(),
    )(torrentio_list_quality_filters)
