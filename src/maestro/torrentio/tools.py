"""Torrentio MCP tool definitions.

All 5 tools are pure compute -- no network. They wrap encoder.py +
enums.py for Claude's consumption.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import pure_compute, read_only
from maestro.torrentio.encoder import (
    TorrentioConfig,
    build_url,
    parse_url,
    validate_config,
)
from maestro.torrentio.enums import PROVIDERS, QUALITY_FILTERS


def torrentio_parse_url(url: str) -> dict[str, Any]:
    """Decode a Torrentio install URL into its config object.

    Returns a dict with keys: providers, sort, quality_filter, languages,
    limit, size_filter, debrid_provider, debrid_key, extra.

    Reference: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/configuration.js
    """
    return parse_url(url).model_dump()


def torrentio_build_url(
    config: dict[str, Any],
    *,
    base_url: str = "https://torrentio.strem.fun",
) -> str:
    """Build a Torrentio install URL from a config dict."""
    cfg = TorrentioConfig.model_validate(config)
    return build_url(cfg, base_url=base_url)


def torrentio_validate_config(config: dict[str, Any]) -> list[str]:
    """Validate a Torrentio config against known enums. Empty list = valid.

    Known asymmetry (Task 4.2 follow-up, tracked, not part of 4.3 scope):
    providers/quality_filter inputs are lowercased before comparison, but
    sort/debrid_provider are not -- so `{"sort": "Qualitysize"}` errors
    while `{"providers": ["YTS"]}` does not.
    """
    cfg = TorrentioConfig.model_validate(config)
    return validate_config(cfg)


def torrentio_list_providers() -> list[str]:
    """Return all known torrent providers (lowercase strings)."""
    return list(PROVIDERS)


def torrentio_list_quality_filters() -> list[str]:
    """Return all valid quality-filter tags for exclusion config."""
    return list(QUALITY_FILTERS)


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
