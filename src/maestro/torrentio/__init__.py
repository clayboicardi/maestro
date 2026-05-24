"""Torrentio domain -- pure-compute install-URL codec + enum lookups.

Five MCP tools, all annotated either ``read_only`` (decode) or
``pure_compute`` (encode / validate / enumerate). No network calls and
no in-memory state -- this domain is entirely deterministic functions
over the Torrentio config grammar (see :mod:`.encoder` for the wire
format details).

Layered as:

- :mod:`.enums` -- frozen constants extracted from the upstream
  Torrentio addon's ``filter.js`` (providers, quality filters,
  resolutions, debrid providers, languages, sort options). Refresh
  manually when upstream evolves; there is no automated drift check
  in v1 (worth surfacing as a polish item).
- :mod:`.encoder` -- ``TorrentioConfig`` Pydantic model + ``parse_url``
  / ``build_url`` / ``validate_config`` round-trip operations on the
  pipe-delimited config segment of the install URL.
- :mod:`.tools` -- MCP-facing wrappers that take/return plain dicts so
  Claude can manipulate configs without round-tripping Pydantic models.

Annotation mapping (enumerated per-tool in :func:`register_tools` to
avoid integer-tally drift): ``torrentio_parse_url`` is ``read_only``;
``torrentio_build_url`` / ``torrentio_validate_config`` /
``torrentio_list_providers`` / ``torrentio_list_quality_filters`` are
``pure_compute``.
"""

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
    """Register the Torrentio MCP tools on the FastMCP app.

    Per-tool annotation mapping (drift-resistant enumeration):

    - ``torrentio_parse_url`` -- ``read_only`` (decode-only; the input
      URL is the data source, no derived state).
    - ``torrentio_build_url`` -- ``pure_compute`` (deterministic
      encode of a config dict to a URL string).
    - ``torrentio_validate_config`` -- ``pure_compute`` (deterministic
      schema check; returns a list of error strings).
    - ``torrentio_list_providers`` -- ``pure_compute`` (snapshot of the
      module-level :data:`.enums.PROVIDERS` constant).
    - ``torrentio_list_quality_filters`` -- ``pure_compute`` (snapshot
      of :data:`.enums.QUALITY_FILTERS`).
    """
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
