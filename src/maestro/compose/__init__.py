"""Compose domain -- the ``find_best_stream`` killer feature surface.

Wires the parameterized
:func:`maestro.compose.find_best_stream.find_best_stream` composer to
the FastMCP server with sub-domain callables threaded in from the RD
and Stremio toolsets. The composer itself is sub-domain agnostic (takes
callables) so it stays unit-testable without an MCP server or live
upstream endpoints.

This module is one of two cross-domain wiring sites that reach into
RD + Stremio toolset internals (``rd_toolset._client``,
``rd_toolset._learner``, ``stremio_toolset._client``). The other is
:func:`maestro.diagnose.register_tools`, which reaches into
``rd_toolset._client.get_user_info`` and ``rd_toolset._learner`` for
the diagnostics tool surface. Both are server-boot-time wiring (see
``server.py``); neither is steady-state code. The per-domain toolsets
don't expose public accessors because the only consumers needing those
refs are the cross-domain registrars themselves. Promoting the private
refs to public attributes would force per-domain file changes for two
downstream consumers; keeping the private access LOCALIZED at the
server-boot wiring is the smaller-blast-radius option, and the
violation is documented + intentional rather than incidental.

Surfaces a single MCP tool: ``find_best_stream``, annotated as
``destructive`` because it can burn Real-Debrid daily-cap quota and
trigger filter-gate strike learning as a side effect.
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

    The composer is parameterized over callables; this function binds
    each callable to the relevant toolset method so the registered tool
    captures the SHARED state across calls:

    1. ``stremio_toolset._client.cinemeta_search`` -- title -> IMDB id.
    2. ``stremio_toolset.query_addon`` -- AIOStreams stream query.
    3. ``rd_toolset._client.check_cache`` -- the SHARED RD client with
       its already-bound bearer token and reused httpx connection pool.
    4. ``rd_toolset._client.unrestrict_link`` -- same shared client.
    5. ``learner`` -- the SHARED :class:`FilterGateLearner`; in-memory
       keyword evidence persists across composer calls AND is the same
       instance the RD ``filter_gate_check`` tool reads from. Sharing
       it here ensures strikes the composer records via
       :meth:`record_strike_and_persist` are immediately visible to
       the standalone risk-check tool.

    Private-attribute access at the toolset boundary
    (``rd_toolset._client``, ``stremio_toolset._client``) is deliberate
    and load-bearing -- see the package-level docstring for rationale.
    Promoting those refs to public attributes would force changes in
    the per-domain modules for this single cross-domain consumer.

    The ``compose_budget_s`` argument becomes the composer's wall-clock
    budget; tunable per deployment via the same name on settings.
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

        Chains the user-configured AIOStreams addon + Real-Debrid cache
        check + the May 2026 filter-gate runtime heuristic + retry-on-
        fail. See :func:`maestro.compose.find_best_stream.find_best_stream`
        for the full 7-step chain documentation and parameter contract
        (including the ``fallback_to_uncached`` double-duty behavior).

        Defaulting policy applied here (before delegating to the
        composer):

        - ``preferred_languages`` defaults to ``["English"]`` -- the
          consumer can pass an explicit list to override.
        - ``exclude_quality`` defaults to ``["CAM", "TS", "SCR", "R5",
          "R6"]`` -- common low-quality release types most consumers
          want filtered.

        Returns the dict-serialized :class:`StreamResolution`. Inspect
        ``url`` (truthy iff success) and ``attempts`` (per-candidate
        diagnostics on failure).
        """
        # Cross-domain composition needs the underlying client/learner refs;
        # the per-domain toolsets don't expose public accessors. Documented
        # and isolated to this single call site -- see package docstring.
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
