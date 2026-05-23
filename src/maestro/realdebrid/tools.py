"""Real-Debrid MCP tool definitions (7 tools).

Wraps :class:`maestro.realdebrid.client.RDClient` and
:class:`maestro.realdebrid.filter_gate.FilterGateLearner` for the MCP
surface. The cache-check tool overlays the filter-gate risk heuristic
on top of the RD response so Claude can avoid sending high-risk
candidates to ``unrestrict_link`` (which would burn a daily-cap call
and trigger an ``infringing_file`` 403).
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import destructive, pure_compute, read_only
from maestro.config import MaestroSettings
from maestro.realdebrid.client import RDClient
from maestro.realdebrid.filter_gate import FilterGateLearner


class RDToolset:
    """Encapsulates the RD client + filter-gate learner for the MCP tools.

    The toolset holds shared state (the client's connection pool and
    the learner's in-memory keyword evidence) so each tool method can
    be registered as a closure over a single instance. Single-instance-
    per-server-lifetime by design -- FastMCP serializes tool
    invocations within a session, so no thread-safety or coroutine-
    safety is asserted.

    Shared-state contract:

    - The :class:`RDClient` instance owns the bearer-token-bound httpx
      connection pool. All tool methods that hit RD go through this
      one client.
    - The :class:`.filter_gate.FilterGateLearner` instance owns the
      in-memory ``learned_keywords`` dict + the state-file path. The
      learner is read by :meth:`check_cache` (risk overlay) and
      :meth:`filter_gate_check` (pure-compute); writes happen via
      future composer integration (Phase 7 ``find_best_stream``) when
      :meth:`unrestrict_link` returns an ``infringing_file`` 403 --
      see :class:`.filter_gate.FilterGateLearner.record_strike_and_persist`.
    """

    def __init__(
        self,
        *,
        api_token: str,
        learner: FilterGateLearner,
        timeout_s: float = 15.0,
    ) -> None:
        self._client = RDClient(api_token=api_token, timeout_s=timeout_s)
        self._learner = learner

    async def get_user_info(self) -> dict[str, Any]:
        """Return RD user info -- premium status, expiration, etc."""
        return await self._client.get_user_info()

    async def check_cache(
        self,
        infohashes: list[str],
        filenames: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Batch RD cache probe with filter-gate risk overlay.

        For each hash, returns ``{hash, cached, filter_gate_risk,
        matched_keywords, rd_files}``. The risk overlay is pure-compute
        on top of the raw RD response -- callers should prefer ``low``
        risk hashes over ``high`` risk ones before calling
        :meth:`unrestrict_link` to avoid burning daily-cap quota on
        infringing-file 403s.

        ``filenames`` is an optional ``{hash: filename}`` map. When
        absent, ``filter_gate_risk`` is ``"unknown"`` for that entry.
        """
        raw = await self._client.check_cache(infohashes)
        results: list[dict[str, Any]] = []
        for h in infohashes:
            entry = raw.get(h, {"cached": False, "files": None})
            filename = (filenames or {}).get(h)
            risk = self._learner.predict_risk(filename)
            matched = self._learner.matched_keywords(filename) if filename else []
            results.append(
                {
                    "hash": h,
                    "cached": entry["cached"],
                    "filter_gate_risk": risk.value,
                    "matched_keywords": matched,
                    "rd_files": entry.get("files"),
                }
            )
        return results

    def filter_gate_check(self, filename: str) -> dict[str, Any]:
        """Pure-compute risk heuristic for a filename (no network).

        Returns ``{filename, risk, matched_keywords}``. Useful for
        pre-flighting a candidate against the May 2026 RD filter-gate
        without spending a cache-check round trip.
        """
        return {
            "filename": filename,
            "risk": self._learner.predict_risk(filename).value,
            "matched_keywords": self._learner.matched_keywords(filename),
        }

    async def add_torrent(self, magnet: str) -> dict[str, Any]:
        """Add a magnet link to RD. Returns ``{id, uri}`` for the new torrent."""
        return await self._client.add_magnet(magnet)

    async def get_torrent_status(self, torrent_id: str) -> dict[str, Any]:
        """Return torrent status + file list + progress for a given RD torrent id."""
        return await self._client.get_torrent_status(torrent_id)

    async def unrestrict_link(self, restricted_url: str) -> dict[str, Any]:
        """Convert an RD restricted URL to a playable CDN URL.

        Consumes RD daily-cap quota. The ``download`` field on the
        response is the playable URL. A 403 with ``infringing_file``
        in the body surfaces as :class:`maestro.errors.UpstreamError`
        via the middleware -- a future ``find_best_stream`` composer
        will catch that shape and feed it back to
        :meth:`FilterGateLearner.record_strike` to grow the learned
        keyword set (Phase 7).
        """
        return await self._client.unrestrict_link(restricted_url)

    async def get_library(self) -> list[dict[str, Any]]:
        """List torrents in the user's RD library."""
        return await self._client.get_library()


def register_tools(mcp: FastMCP, settings: MaestroSettings) -> RDToolset:
    """Register all 7 RD tools on the FastMCP app.

    Constructs a single :class:`FilterGateLearner` (loaded from the
    persisted state file at ``settings.filter_gate_state_path``) and a
    single :class:`RDToolset` (wrapping :class:`RDClient` + the
    learner) per server lifetime. The toolset is returned so a
    downstream composer (Phase 7 ``find_best_stream``) can wire to the
    SAME client + learner instances rather than re-instantiating --
    avoiding a duplicate connection pool and, more importantly,
    duplicate in-memory ``learned_keywords`` state that would diverge
    on subsequent strikes.

    Annotation strategy (per-tool, immune to count drift):
    ``get_user_info``, ``check_cache``, ``get_torrent_status``, and
    ``get_library`` are ``read_only`` (idempotent queries, no side
    effects beyond logging); ``filter_gate_check`` is ``pure_compute``
    (no network, no in-memory mutation, just a regex match against
    the learner's current keyword set); ``add_torrent`` and
    ``unrestrict_link`` are ``destructive`` (``add_torrent`` enqueues
    an RD operation; ``unrestrict_link`` burns daily-cap quota and
    may trigger filter-gate strike learning via the future composer
    wiring).

    Secret handling: ``settings.rd_token`` is unwrapped via
    ``.get_secret_value()`` exactly here, then passed to the client
    as a plain string for the lifetime of the process. Pydantic v2's
    ``SecretStr.__eq__`` does not compare against plain strings; the
    project tracks this as one of the hard invariants in CLAUDE.md.

    Filter-gate state lifecycle: ``learner.load_state()`` runs once at
    registration. Subsequent writes happen lazily on each
    ``record_strike_and_persist`` call from the composer. If
    ``filter_gate_state_path`` is ``None`` (test wiring), the learner
    operates in memory-only mode and persistence calls are silent
    no-ops.
    """
    learner = FilterGateLearner(state_path=settings.filter_gate_state_path)
    learner.load_state()

    toolset = RDToolset(
        api_token=settings.rd_token.get_secret_value(),
        learner=learner,
        timeout_s=settings.http_timeout_s,
    )

    mcp.tool(
        name="realdebrid_get_user_info",
        annotations=read_only(title="Get RD User Info").model_dump(),
    )(toolset.get_user_info)
    mcp.tool(
        name="realdebrid_check_cache",
        annotations=read_only(title="Batch RD Cache Check with Filter-Gate Overlay").model_dump(),
    )(toolset.check_cache)
    mcp.tool(
        name="realdebrid_filter_gate_check",
        annotations=pure_compute(title="Filter-Gate Risk Heuristic").model_dump(),
    )(toolset.filter_gate_check)
    mcp.tool(
        name="realdebrid_add_torrent",
        annotations=destructive(title="Add Torrent to RD").model_dump(),
    )(toolset.add_torrent)
    mcp.tool(
        name="realdebrid_get_torrent_status",
        annotations=read_only(title="Get RD Torrent Status").model_dump(),
    )(toolset.get_torrent_status)
    mcp.tool(
        name="realdebrid_unrestrict_link",
        annotations=destructive(title="Unrestrict RD Link to Playable URL").model_dump(),
    )(toolset.unrestrict_link)
    mcp.tool(
        name="realdebrid_get_library",
        annotations=read_only(title="List RD Library").model_dump(),
    )(toolset.get_library)
    return toolset
