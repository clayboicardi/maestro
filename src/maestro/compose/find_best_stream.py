"""find_best_stream composer -- chains AIOStreams + RD + filter-gate.

The composer is the project's killer feature: it takes a human title
(``"Foundation"``) and returns one playable Real-Debrid URL OR a
structured failure that diagnoses why no candidate worked. It chains
seven steps:

    1. Cinemeta resolves the title to an IMDB id (best-effort; returns
       :attr:`StreamResolution.suggestion` if Cinemeta has no match).
    2. The Stremio addon protocol queries AIOStreams' ``/stream/``
       endpoint for that IMDB id (and season/episode for series).
    3. Local language + quality filters drop non-preferred streams.
    4. Real-Debrid batch ``check_cache`` overlays per-candidate cache
       status onto each candidate dict (in-place mutation).
    5. The runtime filter-gate heuristic overlays per-candidate risk
       (``LOW`` / ``HIGH``) based on the extracted filename.
    6. Candidates sort: cached + low-risk first, then cached + HIGH,
       then uncached. Within each group the upstream AIOStreams order
       is preserved (Python sort is stable).
    7. The top candidate is resolved via RD ``unrestrict_link``. On
       failure, the loop pops the next candidate and retries; each
       attempt is recorded in :attr:`StreamResolution.attempts`. The
       loop terminates on success, ``budget_s`` exhaustion, or empty
       candidate list.

Side effects: when an attempt fails with ``infringing_file`` (RD's
filter-gate 403), the learner's :meth:`record_strike_and_persist` is
called so future calls can predict the same failure pre-network.

Contract notes (surface area future callers should know):

- **Parameterization over callables**: the composer accepts
  ``cinemeta_search`` / ``stremio_query`` / ``rd_check_cache`` /
  ``rd_unrestrict`` as callables, not as toolset references. Keeps
  the composer unit-testable with mock implementations and avoids
  coupling to specific toolset internals.
- **No tenacity / no per-attempt timeout**: retry logic is the
  candidate-iteration loop, not a backoff schedule. The only time
  bound is ``budget_s``, checked BEFORE each candidate attempt --
  a single slow ``rd_unrestrict`` call can blow past ``budget_s``
  during its own execution. Callers needing strict bounds should
  set a short per-call timeout on ``rd_unrestrict`` itself.
- **``fallback_to_uncached`` does double duty**: the flag controls
  BOTH "include uncached candidates in the candidate list" AND
  "attempt HIGH-filter-gate-risk candidates anyway." Callers wanting
  uncached fallback without filter-gate bypass cannot express that
  in v1 -- a future split into ``allow_uncached`` +
  ``bypass_filter_gate`` would separate the concerns.
- **Empty filename on infringing strike**: if
  :func:`_extract_filename` returns ``None`` for the failing candidate,
  ``record_strike_and_persist`` receives ``""`` and learns nothing
  (the regex matches no tokens). Acceptable degradation, not a bug.
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

# Media-file extensions used to identify the real-filename line inside a
# multi-line `title` field. AIOStreams + many other Stremio addons format
# titles like "Episode Label\n[folder] Show.S01E03.WEB-DL.mkv\n[size] 8.2 GB"
# where the release-tag-bearing filename is NOT line 0.
_MEDIA_EXTENSIONS: tuple[str, ...] = (".mkv", ".mp4", ".avi", ".webm", ".mov", ".m4v")

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
    """Apply language + quality filters; keep streams with no language tag.

    Language heuristic (three branches per stream):

    1. Stream's ``title`` + ``name`` contains at least one preferred
       language token (case-insensitive substring) -> keep.
    2. Stream's blob contains any token from :data:`_LANG_TOKENS` but
       NOT a preferred one -> drop (foreign release explicitly tagged).
    3. Stream's blob contains no language tag at all -> keep
       (untagged releases are usually English by default; better to
       attempt than to silently drop).

    Quality heuristic: case-insensitive substring exclusion against
    the same blob. Streams matching ANY token in ``exclude_quality``
    are dropped. No substitution / regex; ``"CAM"`` would also match
    ``"webcam"`` if such a release tag existed.

    Pure function: takes a list, returns a new list. Does not mutate.
    """
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
    """Mutate each candidate dict IN-PLACE with three derived fields.

    Side effect: returns ``None`` and mutates ``candidates`` directly.
    Fields added to each dict (underscore-prefixed to mark them as
    composer-internal vs addon-supplied):

    - ``_cached`` (bool): from ``cache_map[infoHash]["cached"]``.
      Streams whose ``infoHash`` is absent from ``cache_map`` (e.g.,
      the addon didn't ship an ``infoHash`` field, or RD's cache check
      returned nothing for it) get ``False`` -- sorted as uncached.
    - ``_filter_gate_risk`` (str): the ``.value`` of the
      :class:`RiskLevel` returned by
      :meth:`FilterGateLearner.predict_risk` for the extracted
      filename. The risk is computed once here, then RE-CHECKED at
      attempt time in :func:`_try_candidate` -- consistent under
      FastMCP's per-session serialization but theoretically vulnerable
      to learner-state changes between the two reads if that contract
      ever loosens.
    - ``_filename`` (str | None): extracted via
      :func:`_extract_filename`. ``None`` if no filename could be
      determined; downstream :meth:`record_strike_and_persist` receives
      ``""`` in that case and learns nothing.
    """
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
    """Build an :class:`Attempt` row from a failed ``rd_unrestrict`` call.

    Two branches based on whether the error body contains
    ``infringing_file``:

    - **Infringing**: returns ``Attempt(status="unrestrict_403_infringing")``
      AND triggers a side effect:
      :meth:`FilterGateLearner.record_strike_and_persist` learns the
      filename's tokens for future risk prediction. If the candidate
      has no extractable filename (``_filename is None``), the strike
      records as ``""`` (no tokens learned, but the call still completes
      cleanly -- no exception escapes).
    - **Other 4xx**: returns ``Attempt(status="unrestrict_4xx")`` with
      no side effect; the failure was a non-filter-gate condition (auth,
      rate limit, malformed response) and the learner has nothing to
      learn from it.

    The ``error`` field is the first 200 chars of ``str(exc)`` -- enough
    for diagnostics without bloating the response payload.
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
    """Resolve a title to one playable RD URL or a structured failure.

    See module docstring for the 7-step chain overview. This function
    is the orchestrator; helpers do the per-step work.

    Parameter contract:

    - ``title`` + ``content_type``: passed to ``cinemeta_search`` for
      title -> IMDB id resolution. ``content_type`` is ``"movie"`` or
      ``"series"``; the addon protocol uses it in the request path.
    - ``season`` / ``episode``: required for ``"series"``, ignored for
      ``"movie"``. Both must be set together or neither (the addon
      query handler treats either-but-not-both as "movie" mode).
    - ``preferred_languages``: list of language tokens; see
      :func:`_filter_streams` for the three-branch heuristic.
    - ``exclude_quality``: list of release-tag tokens; case-insensitive
      substring excluded from candidates.
    - ``require_cached``: when ``True`` AND ``fallback_to_uncached`` is
      ``False``, uncached candidates are filtered out before the
      candidate loop. When ``False``, all candidates remain (cached
      first per sort).
    - ``fallback_to_uncached``: **does double duty**. When ``True``:
      (a) the ``require_cached`` filter is BYPASSED so uncached
      candidates stay in the list; AND (b) HIGH-filter-gate-risk
      candidates are ATTEMPTED rather than pre-skipped (see
      :func:`_try_candidate`). Callers cannot currently express
      "uncached OK, but skip HIGH risk" in v1.
    - ``aiostreams_addon_url``: passed verbatim to ``stremio_query``;
      the composer doesn't normalize or validate it (the Stremio
      client does that at the boundary).
    - ``learner``: shared :class:`FilterGateLearner` instance; mutated
      by :meth:`record_strike_and_persist` calls on infringing-file
      failures (the persistence target lives on the learner).
    - ``cinemeta_search``: best-effort; returns ``None`` for both "no
      matches" and "Cinemeta is down." The composer can't distinguish
      these two cases and treats both as "no matches" (returning a
      structured failure with suggestion = "Cinemeta returned no
      matches; pass imdb_id directly if you have it").
    - ``stremio_query``: ``MaestroException`` from this call is NOT
      caught -- it propagates out of the composer. Justified because
      a failed AIOStreams query means we have no candidates to work
      with, and the caller's middleware will translate the exception
      to an MCP error response.
    - ``rd_check_cache``: only called if at least one candidate has
      a non-empty ``infoHash``. Streams without ``infoHash`` are still
      attempted but sort as uncached.
    - ``rd_unrestrict``: called once per candidate during the retry
      loop. Exceptions are caught and converted to ``Attempt`` rows;
      see :func:`_handle_unrestrict_exception`.
    - ``budget_s``: wall-clock budget in seconds, checked BEFORE each
      candidate (NOT during ``rd_unrestrict`` execution). A single
      slow upstream call can exceed ``budget_s``.

    Sort stability: within (cached, risk) groups the upstream
    AIOStreams ordering is preserved (Python's sort is stable). The
    addon's quality ranking flows through unchanged.

    Return shape (see :class:`StreamResolution`): success envelope
    with ``url`` set OR structured failure with ``url=None``,
    ``attempts`` populated, and ``suggestion`` naming the next action.
    """

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
    """Evaluate one candidate; append an :class:`Attempt`; return success or ``None``.

    Side effect: always appends exactly ONE :class:`Attempt` to
    ``attempts`` (regardless of return). Returning ``StreamResolution``
    triggers an early-exit from the candidate loop; returning ``None``
    signals "try the next candidate."

    Branch logic (in order):

    1. **HIGH filter-gate risk + no fallback**: when
       ``candidate["_filter_gate_risk"] == "high"`` AND
       ``fallback_to_uncached`` is ``False``, the candidate is
       pre-skipped with ``status="filter_gate_block"``. NOTE:
       ``fallback_to_uncached`` here gates filter-gate bypass, not
       just uncached fallback -- the flag does double duty (see
       :func:`find_best_stream` docstring).
    2. **No URL**: ``candidate["url"]`` missing/falsy -> ``status="no_url"``.
    3. **``rd_unrestrict`` raised**: caught + converted to an
       ``Attempt`` row via :func:`_handle_unrestrict_exception`
       (which may also trigger a filter-gate strike learn).
    4. **``rd_unrestrict`` returned but no ``download`` field**:
       ``status="no_url"`` with error explaining the source. Distinct
       from branch 2 because the URL existed in the addon response but
       RD returned no playable form.
    5. **Success**: ``status="success"`` appended AND a populated
       :class:`StreamResolution` returned. The success ``Attempt``
       is always the last row in ``attempts``.
    """
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
    """Pull a likely filename out of a stream dict.

    AIOStreams + many other Stremio addons format the `title` field as
    multi-line text where line 0 is the human episode label and a later
    line contains the actual filename (often prefixed with a folder icon).
    Scan every line for one containing a known media extension -- that's
    the line carrying the release tags filter-gate cares about. Without
    this, filter-gate-aware sort silently breaks because predict_risk is
    fed "S01E03 - Episode Name" instead of the real release name.
    """
    explicit = stream.get("filename")
    if explicit:
        # Trust an explicit, non-empty filename field if present.
        return explicit
    title = stream.get("title") or ""
    if not title:
        return None
    lines = title.splitlines()
    # Prefer the line containing a media extension (real filename).
    for line in lines:
        line_lower = line.lower()
        if any(ext in line_lower for ext in _MEDIA_EXTENSIONS):
            return line.strip()
    # Fallback: first non-empty line.
    for line in lines:
        if line.strip():
            return line.strip()
    return title.strip() or None


def _build_metadata(stream: dict[str, Any]) -> StreamMetadata:
    """Build a :class:`StreamMetadata` from heuristic title-blob inspection.

    Three substring checks against the lower-cased ``title`` + ``name``:

    - **Resolution**: first match of ``4k`` / ``1080p`` / ``720p`` /
      ``480p``. ``None`` if no match.
    - **Codec**: first match of ``x265`` / ``x264`` / ``av1`` / ``hevc``.
      ``None`` if no match.
    - **Language**: ``"English"`` iff ``"english"`` substring present;
      ``None`` otherwise. NOT a real language detector -- foreign
      releases that tag e.g. ``"French"`` will report ``language=None``
      here even though the stream is clearly French.

    ``size_gb`` and ``group`` are always ``None`` in v1 (not yet
    extracted). ``source_addon`` is hardcoded ``"aiostreams"`` since
    that's the only upstream the composer consults.

    Pure function; called once on the winning candidate.
    """
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
