"""find_best_stream composer.

Chains:
    1. Cinemeta resolve title -> imdb_id
    2. Stremio query AIOStreams' /stream/ endpoint
    3. RD cache check (batch)
    4. Filter-gate overlay
    5. Sort candidates (cached & low-risk > cached & risk > uncached)
    6. Resolve top candidate via RD unrestrict
    7. On failure, pop next and retry; record attempts

Returns StreamResolution (success or structured failure with `attempts`).

This module is parameterized to accept callables for sub-domain
operations -- keeps it test-friendly and avoids tight coupling.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from maestro.compose.types import Attempt, StreamMetadata, StreamResolution
from maestro.errors import MaestroException
from maestro.realdebrid.filter_gate import FilterGateLearner, RiskLevel

log = structlog.get_logger("maestro.compose.find_best_stream")

CinemetaSearch = Callable[[str, str], Awaitable[str | None]]
StremioQuery = Callable[..., Awaitable[list[dict[str, Any]]]]
RDCheckCache = Callable[[list[str]], Awaitable[dict[str, dict[str, Any]]]]
RDUnrestrict = Callable[[str], Awaitable[dict[str, Any]]]

# Language-tag tokens commonly seen in release names. Used so we can
# distinguish "stream tags a language we don't want" (reject) from
# "stream tags no language at all" (accept -- usually English by default).
_LANG_TOKENS: tuple[str, ...] = (
    "english",
    "french",
    "spanish",
    "german",
    "italian",
    "portuguese",
    "russian",
    "japanese",
    "korean",
    "chinese",
    "hindi",
    "dubbed",
    "multi",
    "dual",
    "fre",
    "spa",
    "ger",
    "ita",
    "por",
    "rus",
    "jpn",
    "kor",
    "chi",
    "hin",
)

_NO_CACHED_SUGGESTION = (
    "No cached candidates after filtering. Try fallback_to_uncached=True "
    "or check that RD is still serving cached results for this title."
)

_ALL_FAILED_SUGGESTION = (
    "All candidates failed. Inspect `attempts` for per-candidate diagnostics. "
    "Common causes: RD filter-gate (May 2026), expired RD token, addon outage."
)


def _filter_streams(
    raw_streams: list[dict[str, Any]],
    preferred_languages: list[str],
    exclude_quality: list[str],
) -> list[dict[str, Any]]:
    """Apply language + quality filters; keep streams with no language tag."""
    out: list[dict[str, Any]] = []
    for s in raw_streams:
        title_blob_lower = ((s.get("title") or "") + " " + (s.get("name") or "")).lower()
        if preferred_languages:
            has_preferred = any(lang.lower() in title_blob_lower for lang in preferred_languages)
            has_any_lang_tag = any(tok in title_blob_lower for tok in _LANG_TOKENS)
            if not has_preferred and has_any_lang_tag:
                continue
        if exclude_quality and any(q.lower() in title_blob_lower for q in exclude_quality):
            continue
        out.append(s)
    return out


def _overlay_cache_and_risk(
    candidates: list[dict[str, Any]],
    cache_map: dict[str, dict[str, Any]],
    learner: FilterGateLearner,
) -> None:
    """Mutate each candidate dict with `_cached`, `_filter_gate_risk`, `_filename`."""
    for c in candidates:
        h = c.get("infoHash") or ""
        c["_cached"] = bool(cache_map.get(h, {}).get("cached", False))
        filename = _extract_filename(c)
        c["_filter_gate_risk"] = learner.predict_risk(filename).value
        c["_filename"] = filename


def _handle_unrestrict_exception(
    exc: MaestroException,
    *,
    candidate: dict[str, Any],
    learner: FilterGateLearner,
) -> Attempt:
    """Build an Attempt from a MaestroException raised by rd_unrestrict.

    Side effect: on infringing_file, persists a filter-gate strike via the
    CF10 wrapper (atomic record + save).
    """
    err_str = str(exc).lower()
    filename = candidate.get("_filename")
    title_blob = candidate.get("title") or candidate.get("name") or ""
    hash_ = candidate.get("infoHash")
    if "infringing_file" in err_str:
        learner.record_strike_and_persist(filename or "", "infringing_file")
        return Attempt(
            hash=hash_,
            title=title_blob,
            filename=filename,
            status="unrestrict_403_infringing",
            error=str(exc)[:200],
        )
    return Attempt(
        hash=hash_,
        title=title_blob,
        filename=filename,
        status="unrestrict_4xx",
        error=str(exc)[:200],
    )


async def find_best_stream(
    *,
    title: str,
    content_type: str,
    season: int | None,
    episode: int | None,
    preferred_languages: list[str],
    exclude_quality: list[str],
    require_cached: bool,
    fallback_to_uncached: bool,
    aiostreams_addon_url: str,
    learner: FilterGateLearner,
    cinemeta_search: CinemetaSearch,
    stremio_query: StremioQuery,
    rd_check_cache: RDCheckCache,
    rd_unrestrict: RDUnrestrict,
    budget_s: float,
) -> StreamResolution:
    """The composer. Returns one playable URL or a structured failure."""

    start = time.monotonic()
    attempts: list[Attempt] = []

    log.info("compose_start", title=title, content_type=content_type)

    imdb_id = await cinemeta_search(title, content_type)
    if imdb_id is None:
        return StreamResolution(
            url=None,
            metadata=None,
            source="aiostreams",
            attempts=[],
            elapsed_ms=_elapsed(start),
            suggestion="Cinemeta returned no matches; pass imdb_id directly if you have it",
        )

    raw_streams = await stremio_query(
        addon_url=aiostreams_addon_url,
        content_type=content_type,
        imdb_id=imdb_id,
        season=season,
        episode=episode,
    )

    candidates = _filter_streams(raw_streams, preferred_languages, exclude_quality)
    if not candidates:
        return StreamResolution(
            url=None,
            source="aiostreams",
            attempts=[],
            elapsed_ms=_elapsed(start),
            suggestion="AIOStreams returned 0 streams matching language/quality filters",
        )

    hashes: list[str] = [str(c["infoHash"]) for c in candidates if c.get("infoHash")]
    cache_map = await rd_check_cache(hashes) if hashes else {}
    _overlay_cache_and_risk(candidates, cache_map, learner)

    candidates.sort(
        key=lambda x: (
            0 if x["_cached"] else 1,
            0 if x["_filter_gate_risk"] != RiskLevel.HIGH.value else 1,
        )
    )

    if require_cached and not fallback_to_uncached:
        candidates = [c for c in candidates if c["_cached"]]
        if not candidates:
            return StreamResolution(
                url=None,
                source="aiostreams",
                attempts=[],
                elapsed_ms=_elapsed(start),
                suggestion=_NO_CACHED_SUGGESTION,
            )

    for c in candidates:
        if time.monotonic() - start >= budget_s:
            attempts.append(Attempt(status="timeout", error=f"budget {budget_s}s exhausted"))
            break

        attempt_or_resolution = await _try_candidate(
            c,
            attempts=attempts,
            start=start,
            learner=learner,
            rd_unrestrict=rd_unrestrict,
            fallback_to_uncached=fallback_to_uncached,
        )
        if attempt_or_resolution is not None:
            return attempt_or_resolution

    return StreamResolution(
        url=None,
        source="aiostreams",
        attempts=attempts,
        elapsed_ms=_elapsed(start),
        suggestion=_ALL_FAILED_SUGGESTION,
    )


async def _try_candidate(
    candidate: dict[str, Any],
    *,
    attempts: list[Attempt],
    start: float,
    learner: FilterGateLearner,
    rd_unrestrict: RDUnrestrict,
    fallback_to_uncached: bool,
) -> StreamResolution | None:
    """Process one candidate: append an Attempt; return success resolution or None."""
    hash_ = candidate.get("infoHash")
    filename = candidate.get("_filename")
    title_blob = candidate.get("title") or candidate.get("name") or ""
    risk = candidate.get("_filter_gate_risk")

    if risk == RiskLevel.HIGH.value and not fallback_to_uncached:
        attempts.append(
            Attempt(
                hash=hash_,
                title=title_blob,
                filename=filename,
                status="filter_gate_block",
            )
        )
        return None

    restricted_url = candidate.get("url")
    if not restricted_url:
        attempts.append(
            Attempt(
                hash=hash_,
                title=title_blob,
                status="no_url",
                error="stream had no url field",
            )
        )
        return None

    try:
        unrestrict_result = await rd_unrestrict(restricted_url)
    except MaestroException as e:
        attempts.append(_handle_unrestrict_exception(e, candidate=candidate, learner=learner))
        return None

    download = unrestrict_result.get("download")
    if not download:
        attempts.append(
            Attempt(
                hash=hash_,
                title=title_blob,
                status="no_url",
                error="unrestrict returned no download URL",
            )
        )
        return None

    attempts.append(
        Attempt(
            hash=hash_,
            title=title_blob,
            filename=filename,
            status="success",
        )
    )
    return StreamResolution(
        url=download,
        metadata=_build_metadata(candidate),
        source="aiostreams",
        attempts=attempts,
        elapsed_ms=_elapsed(start),
    )


def _extract_filename(stream: dict[str, Any]) -> str | None:
    """Pull a likely filename out of a stream dict."""
    if "filename" in stream:
        return stream["filename"]
    title = stream.get("title") or ""
    if "\n" in title:
        return title.splitlines()[0]
    return title or None


def _build_metadata(stream: dict[str, Any]) -> StreamMetadata:
    title_blob = ((stream.get("title") or "") + " " + (stream.get("name") or "")).lower()
    resolution = next((r for r in ("4k", "1080p", "720p", "480p") if r in title_blob), None)
    codec = next((c for c in ("x265", "x264", "av1", "hevc") if c in title_blob), None)
    return StreamMetadata(
        resolution=resolution,
        codec=codec,
        language="English" if "english" in title_blob else None,
        size_gb=None,
        source_addon="aiostreams",
    )


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
