"""Compose domain -- `find_best_stream` killer feature.

Wires the parameterized :func:`maestro.compose.find_best_stream.find_best_stream`
composer to the FastMCP server with sub-domain callables threaded in from
Phase 5 (RD) and Phase 6 (Stremio) toolsets.

The composer itself is sub-domain agnostic (takes callables) so it stays
unit-testable without an MCP server. This module is the only place that
reaches into Phase 5/6 toolset internals -- the cross-domain wiring needs
the underlying ``_client`` / ``_learner`` references that the toolsets
encapsulate. Documented and isolated here so future maintainers don't
duplicate the private-attribute access elsewhere.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import destructive
from maestro.compose.find_best_stream import find_best_stream as _composer
from maestro.compose.types import StreamResolution
from maestro.realdebrid.filter_gate import FilterGateLearner
from maestro.realdebrid.tools import RDToolset
from maestro.stremio.tools import StremioToolset


def register_tools(
    mcp: FastMCP,
    *,
    stremio_toolset: StremioToolset,
    rd_toolset: RDToolset,
    learner: FilterGateLearner,
    aiostreams_addon_url: str,
    compose_budget_s: float,
) -> None:
    """Register ``find_best_stream`` wired to RD + Stremio sub-domains.

    The composer is parameterized over callables -- this function binds
    each callable to the relevant toolset method so the registered tool
    captures both:

    1. The shared :class:`RDClient` (reused connection pool) via
       ``rd_toolset._client``.
    2. The shared :class:`FilterGateLearner` (in-memory keyword evidence
       persists across calls) via ``rd_toolset._learner``.

    Private-attribute access at the toolset boundary is deliberate: the
    cross-domain wiring needs the underlying client/learner refs and the
    toolsets don't expose public accessors. Promoting these to public
    would force Phase 5/6 file changes for one consumer; keeping the
    private access localized here is the smaller-blast-radius option.
    """

    async def find_best_stream_tool(
        title: str,
        content_type: str,
        season: int | None = None,
        episode: int | None = None,
        preferred_languages: list[str] | None = None,
        exclude_quality: list[str] | None = None,
        require_cached: bool = True,
        fallback_to_uncached: bool = False,
    ) -> dict[str, Any]:
        """Resolve a title to a single playable Real-Debrid URL.

        Chains AIOStreams (already configured by user) + RD cache check +
        May 2026 filter-gate heuristic + retry-on-fail.

        Returns either a successful :class:`StreamResolution` with ``url``
        set, or a structured failure with ``attempts`` showing per-candidate
        diagnostics and ``suggestion`` recommending next action.
        """
        # Cross-domain composition needs the underlying client/learner; toolset has no
        # public accessor by design (Phase 5/6 didn't anticipate the Phase 7 consumer).
        # Documented and isolated to this single call site.
        result: StreamResolution = await _composer(
            title=title,
            content_type=content_type,
            season=season,
            episode=episode,
            preferred_languages=preferred_languages or ["English"],
            exclude_quality=exclude_quality or ["CAM", "TS", "SCR", "R5", "R6"],
            require_cached=require_cached,
            fallback_to_uncached=fallback_to_uncached,
            aiostreams_addon_url=aiostreams_addon_url,
            learner=learner,
            cinemeta_search=stremio_toolset._client.cinemeta_search,
            stremio_query=stremio_toolset.query_addon,
            rd_check_cache=rd_toolset._client.check_cache,
            rd_unrestrict=rd_toolset._client.unrestrict_link,
            budget_s=compose_budget_s,
        )
        return result.model_dump()

    mcp.tool(
        name="find_best_stream",
        annotations=destructive(
            title="Find Best Stream (chains AIOStreams + RD + filter-gate)"
        ).model_dump(),
    )(find_best_stream_tool)
