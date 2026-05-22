"""Stremio addon protocol MCP tools (6 tools = 3 IO + 3 pure-compute).

IO tools wrap :class:`maestro.stremio.client.StremioAddonClient`. The
parallel fan-out tool isolates per-addon failures so one bad apple
doesn't kill the rest -- ``MaestroException`` from any single addon
is caught and logged, and that addon's slot in the result map gets
an empty stream list. Phase 7's composer will fold this into
``find_best_stream`` and inspect the empty slots for diagnostics.

Pure-compute tools (dedupe/filter/rank) operate on already-fetched
stream lists -- no network. They're the post-fetch toolkit Claude
uses to whittle a 200-stream union down to a small handful of
playable candidates before calling RD cache check / unrestrict.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastmcp import FastMCP

from maestro.annotations import pure_compute, read_only
from maestro.config import MaestroSettings
from maestro.errors import MaestroException
from maestro.stremio.client import StremioAddonClient

log = structlog.get_logger("maestro.stremio.tools")


def stremio_dedupe_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe streams by infoHash, falling back to title then repr.

    First occurrence wins. Useful after ``query_addons_parallel`` to
    collapse duplicates across multiple addons indexing the same source.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in streams:
        key = s.get("infoHash") or s.get("title") or repr(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def stremio_filter_streams(
    streams: list[dict[str, Any]],
    *,
    preferred_languages: list[str] | None = None,
    exclude_quality_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Post-fetch filtering for streams.

    ``preferred_languages``: case-insensitive substring match against
    ``title`` + ``name``. Streams missing all of the requested languages
    are dropped.

    ``exclude_quality_tags``: case-insensitive substring exclusion against
    ``title`` + ``name``. Useful for stripping ``cam``/``ts``/``hdcam``
    rips when the upstream addon doesn't filter them.
    """
    out = list(streams)
    if preferred_languages:
        out = [
            s
            for s in out
            if any(
                lang.lower() in (s.get("title", "") + s.get("name", "")).lower()
                for lang in preferred_languages
            )
        ]
    if exclude_quality_tags:
        out = [
            s
            for s in out
            if not any(
                tag.lower() in (s.get("title", "") + s.get("name", "")).lower()
                for tag in exclude_quality_tags
            )
        ]
    return out


def stremio_rank_streams(
    streams: list[dict[str, Any]],
    *,
    sort_strategy: list[str],
) -> list[dict[str, Any]]:
    """Sort streams by a hierarchy of keys.

    ``sort_strategy``: ordered list of keys. Supported:

    - ``cached``: cached streams (RD ``cached: True``) sort first
    - ``resolution``: 4k > 1080p > 720p > 480p (string-matched in title)
    - ``size``: larger first (descending)
    - ``seeders``: more seeders first (descending)

    Unknown keys are tolerated (treated as no-op tiebreakers). The
    ``cached`` field is synthesized by Phase 7's composer after an
    RD cache check -- the Stremio addon protocol doesn't include it
    natively, so streams without the field rank as uncached.
    """

    def key_for(s: dict[str, Any]) -> tuple[Any, ...]:
        parts: list[Any] = []
        for k in sort_strategy:
            if k == "cached":
                parts.append(0 if s.get("cached") else 1)
            elif k == "resolution":
                title = (s.get("title", "") + s.get("name", "")).lower()
                for res, rank in [("4k", 0), ("1080p", 1), ("720p", 2), ("480p", 3)]:
                    if res in title:
                        parts.append(rank)
                        break
                else:
                    parts.append(99)
            elif k == "size":
                parts.append(-(s.get("size") or 0))
            elif k == "seeders":
                parts.append(-(s.get("seeders") or 0))
            else:
                parts.append(0)
        return tuple(parts)

    return sorted(streams, key=key_for)


class StremioToolset:
    """Holds the addon client + exposes per-method tool implementations.

    The toolset wraps a single :class:`StremioAddonClient` so tool
    invocations share the timeout configuration without re-instantiating
    the client per call. Stateless beyond the timeout -- no auth, no
    connection pool, no retries (best-effort per protocol).
    """

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._client = StremioAddonClient(timeout_s=timeout_s)
        self._timeout_s = timeout_s

    async def query_addon(
        self,
        addon_url: str,
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query a single Stremio addon's ``/stream/`` endpoint."""
        return await self._client.query_stream(
            addon_url=addon_url,
            content_type=content_type,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
        )

    async def query_addons_parallel(
        self,
        addon_urls: list[str],
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Parallel fan-out via ``asyncio.gather``. Returns ``{url: streams}``.

        Per-addon timeouts are isolated: when one addon raises
        :class:`MaestroException` (timeout or malformed JSON), the
        failure is logged at warning level and that slot returns an
        empty stream list. The remaining addons' results are still
        returned. Phase 7's composer will inspect empty slots for
        diagnostics.

        Non-:class:`MaestroException` errors (programmer bugs, etc.)
        propagate so they don't silently corrupt the fan-out.
        """

        async def one(url: str) -> tuple[str, list[dict[str, Any]]]:
            try:
                streams = await self._client.query_stream(
                    addon_url=url,
                    content_type=content_type,
                    imdb_id=imdb_id,
                    season=season,
                    episode=episode,
                )
            except MaestroException as e:
                log.warning(
                    "addon_query_failed",
                    addon_url=url,
                    error_code=e.error.code,
                    error_message=e.error.message,
                )
                return url, []
            return url, streams

        results = await asyncio.gather(*(one(u) for u in addon_urls))
        return dict(results)

    async def get_manifest(self, addon_url: str) -> dict[str, Any]:
        """Fetch ``/manifest.json`` from a Stremio addon."""
        return await self._client.get_manifest(addon_url)


def register_tools(mcp: FastMCP, settings: MaestroSettings) -> StremioToolset:
    """Register all 6 Stremio tools on the FastMCP app.

    Returns the toolset so a future composer (Phase 7's
    ``find_best_stream``) can share the same client instance without
    re-instantiating it. Matches the Phase 5 RD ``register_tools``
    signature -- takes the full settings and extracts the HTTP timeout
    internally for symmetry across domains.
    """
    toolset = StremioToolset(timeout_s=settings.http_timeout_s)

    mcp.tool(
        name="stremio_query_addon",
        annotations=read_only(title="Query Stremio Addon /stream/").model_dump(),
    )(toolset.query_addon)
    mcp.tool(
        name="stremio_query_addons_parallel",
        annotations=read_only(title="Parallel Fan-Out Across Addons").model_dump(),
    )(toolset.query_addons_parallel)
    mcp.tool(
        name="stremio_get_manifest",
        annotations=read_only(title="Get Addon Manifest").model_dump(),
    )(toolset.get_manifest)
    mcp.tool(
        name="stremio_dedupe_streams",
        annotations=pure_compute(title="Dedupe Streams by InfoHash").model_dump(),
    )(stremio_dedupe_streams)
    mcp.tool(
        name="stremio_filter_streams",
        annotations=pure_compute(title="Post-Filter Streams").model_dump(),
    )(stremio_filter_streams)
    mcp.tool(
        name="stremio_rank_streams",
        annotations=pure_compute(title="Rank Streams by Sort Strategy").model_dump(),
    )(stremio_rank_streams)
    return toolset
