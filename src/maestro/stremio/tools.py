"""Stremio addon protocol MCP tools -- the six tools listed below.

IO tools (three, ``read_only`` annotation) wrap
:class:`maestro.stremio.client.StremioAddonClient` to expose the
Stremio addon protocol over MCP:

- ``stremio_query_addon`` -- single addon's ``/stream/`` endpoint.
- ``stremio_query_addons_parallel`` -- fan-out across multiple addons
  via ``asyncio.gather``. Per-addon failures are ISOLATED: a single
  addon raising :class:`MaestroException` (timeout or malformed JSON)
  is caught and logged at warning level; that addon's slot in the
  result map gets an empty stream list and the remaining addons'
  results are still returned. Note: the v1 ``find_best_stream``
  composer wires the single-addon ``query_addon`` (one AIOStreams
  endpoint per call), NOT this parallel variant. The "empty slot
  diagnostics" semantics are intended for a future multi-addon
  composer; today's surface uses this tool as a standalone Claude-
  facing utility for ad-hoc fan-out queries.
- ``stremio_get_manifest`` -- single addon's ``/manifest.json``.

Pure-compute tools (three, ``pure_compute`` annotation) operate on
already-fetched stream lists -- no network, no I/O, no mutation:

- ``stremio_dedupe_streams`` -- collapse duplicates across addons.
- ``stremio_filter_streams`` -- post-fetch language + quality filter.
- ``stremio_rank_streams`` -- sort by a configurable key hierarchy.

These three are the post-fetch toolkit Claude uses to whittle a
200-stream union down to a small handful of playable candidates
before calling RD cache check / unrestrict.

Annotation mapping is enumerated explicitly per-tool in
:func:`register_tools` to avoid integer-tally drift (each tool name
appears next to its annotation; adding a tool means adding both the
``mcp.tool`` call and a line here in the module docstring).
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


def _title_text(s: dict[str, Any]) -> str:
    """Concatenate stream ``title`` + ``name`` for substring matching.

    Coalesces missing-OR-``None`` fields to ``""`` -- real Stremio addons
    send sparse JSON where a field can be explicitly null, and
    ``s.get("title", "") + s.get("name", "")`` would crash on ``None + str``.
    """
    return ((s.get("title") or "") + (s.get("name") or "")).lower()


def stremio_dedupe_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe streams by infoHash, falling back to title then ``repr``.

    Dedup key per stream (first non-empty wins):

    1. ``infoHash`` -- the canonical Stremio identifier.
    2. ``title`` -- coalesce path for streams missing ``infoHash``.
    3. ``repr(s)`` -- last-resort identity check for streams missing
       both. Note: ``repr`` of a dict is order-sensitive, so two
       semantically-identical dicts with different key insertion
       orders would be treated as distinct here. Acceptable because
       the cases that lack BOTH ``infoHash`` and ``title`` are
       malformed in practice.

    First-occurrence-wins ordering: the input list's order determines
    which duplicate survives. Useful after ``query_addons_parallel``
    to collapse duplicates across multiple addons indexing the same
    upstream source (the first addon queried takes precedence).

    Pure function: takes a list, returns a new list with the same
    dict references. Does not mutate the input LIST or the per-stream
    DICTS, but downstream mutation of a kept dict will also mutate
    the input (shallow reference, not deep copy). Use ``copy.deepcopy``
    at the call site if you need true isolation.
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
    """Post-fetch language + quality filtering for streams.

    ``preferred_languages``: case-insensitive substring match against
    the stream's ``title`` + ``name`` text blob. Streams matching NONE
    of the requested languages are DROPPED. This is a stricter rule than
    the composer's internal :func:`maestro.compose.find_best_stream._filter_streams`,
    which also keeps streams with NO language tag at all -- here the
    untagged streams ARE dropped if ``preferred_languages`` is set.
    Consumers wanting the composer's looser semantics should call the
    composer directly rather than this filter.

    ``exclude_quality_tags``: case-insensitive substring exclusion
    against the same blob. Streams matching ANY tag are DROPPED.
    Useful for stripping ``cam`` / ``ts`` / ``hdcam`` rips when the
    upstream addon doesn't filter them. Substring matching is
    non-tokenized; ``"CAM"`` would also match ``"webcam"`` if such
    a release tag existed.

    Both filters short-circuit when their argument is ``None`` or
    empty -- pass empty to skip a stage entirely.

    Pure function: takes a list, returns a new list with the same
    dict references. Does not mutate the input LIST or the per-stream
    DICTS, but downstream mutation of a kept dict will also mutate
    the input (shallow reference, not deep copy). Use ``copy.deepcopy``
    at the call site if you need true isolation.
    """
    out = list(streams)
    if preferred_languages:
        out = [
            s for s in out if any(lang.lower() in _title_text(s) for lang in preferred_languages)
        ]
    if exclude_quality_tags:
        out = [
            s for s in out if not any(tag.lower() in _title_text(s) for tag in exclude_quality_tags)
        ]
    return out


def stremio_rank_streams(
    streams: list[dict[str, Any]],
    *,
    sort_strategy: list[str],
) -> list[dict[str, Any]]:
    """Sort streams by a hierarchy of keys; stable for ties.

    ``sort_strategy``: ordered list of keys. The sort tuple uses these
    keys in order, so the first key dominates and later keys break
    ties. Supported keys:

    - ``cached``: streams with truthy ``cached`` field sort first
      (rank 0); others rank 1. The ``cached`` field is NOT part of
      the Stremio addon protocol -- the composer synthesizes it after
      a Real-Debrid cache check, so streams returned directly from
      an addon will all rank as uncached unless the composer has
      already pre-overlaid the field.
    - ``resolution``: ``4k`` > ``1080p`` > ``720p`` > ``480p``,
      string-matched in the ``title`` + ``name`` blob (case-insensitive).
      Streams with no recognized resolution token sort LAST within
      their cached-group (rank 99).
    - ``size``: larger first (descending). Streams without a ``size``
      field rank as size 0 (i.e., last).
    - ``seeders``: more seeders first (descending). Streams without
      a ``seeders`` field rank as 0.

    Unknown keys are TOLERATED as no-op tiebreakers (rank 0 for all
    streams). Mixing supported + unknown keys is safe; the unknown
    key contributes nothing to the ordering. No error is raised on
    unknown keys -- consumers can ship a forward-compatible strategy
    list and older deployments will ignore the unrecognized keys.

    Stable sort: streams with equal sort tuples preserve their input
    order (Python's :func:`sorted` is stable).

    Pure function: takes a list, returns a new list with the same
    dict references. Does not mutate the input LIST or the per-stream
    DICTS, but downstream mutation of a kept dict will also mutate
    the input (shallow reference, not deep copy). Use ``copy.deepcopy``
    at the call site if you need true isolation.
    """

    def key_for(s: dict[str, Any]) -> tuple[int, ...]:
        parts: list[int] = []
        for k in sort_strategy:
            if k == "cached":
                parts.append(0 if s.get("cached") else 1)
            elif k == "resolution":
                title = _title_text(s)
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
    """Holds the shared addon client + exposes per-method tool implementations.

    The toolset wraps a single :class:`StremioAddonClient` so tool
    invocations share the timeout configuration without re-instantiating
    the client per call. Stateless beyond the timeout -- no auth, no
    persistent connection pool (the underlying client opens a fresh
    ``httpx.AsyncClient`` per request), no retries (best-effort per
    protocol).

    Single-instance-per-server-lifetime by design -- FastMCP serializes
    tool invocations within a session, so no thread-safety or coroutine-
    safety is asserted. The composer reaches into ``self._client`` via
    private-attribute access to share the same client instance for
    Cinemeta + Stremio queries; documented in the compose package.
    """

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._client = StremioAddonClient(timeout_s=timeout_s)

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
        """Parallel fan-out via ``asyncio.gather``; returns ``{url: streams}``.

        Failure isolation contract: when one addon raises
        :class:`MaestroException` (timeout or malformed JSON), the
        failure is logged at warning level under ``addon_query_failed``
        and that addon's slot in the result map gets an empty stream
        list. The remaining addons' results are STILL RETURNED in the
        same dict. The composer downstream inspects empty slots for
        diagnostics.

        Non-:class:`MaestroException` errors (programmer bugs,
        :class:`KeyError`, etc.) PROPAGATE out of
        :func:`asyncio.gather` and abort the entire fan-out. This is
        deliberate -- silently swallowing unexpected errors would mask
        bugs in the fan-out code itself. If you want bulletproof
        isolation, wrap each ``addon_url`` query in its own
        :func:`asyncio.shield` and catch at the call site.

        Wall-clock: bounded by ``self._client._timeout_s`` per addon
        (parallel), so the total time is approximately the slowest
        addon's response time rather than the sum.
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
    """Register the Stremio MCP tools on the FastMCP app; return the toolset.

    Annotation strategy (per-tool, immune to count drift):
    ``stremio_query_addon``, ``stremio_query_addons_parallel``, and
    ``stremio_get_manifest`` are ``read_only`` (idempotent reads, no
    side effects beyond logging); ``stremio_dedupe_streams``,
    ``stremio_filter_streams``, and ``stremio_rank_streams`` are
    ``pure_compute`` (no network, no mutation, deterministic for the
    same input).

    The :class:`StremioToolset` is RETURNED so the cross-domain
    composer can share the same client instance (and its already-
    configured timeout) rather than instantiating a parallel client.
    The composer reaches into ``toolset._client`` directly to call
    :meth:`StremioAddonClient.cinemeta_search`, which is not exposed
    as an MCP tool but is a public method on the underlying client.

    Signature matches the RD ``register_tools`` -- takes the full
    settings and extracts ``http_timeout_s`` internally for symmetry
    across domains.
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
