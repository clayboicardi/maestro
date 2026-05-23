"""Generic Stremio addon protocol client + Cinemeta search helper.

Speaks the public Stremio addon protocol:

    GET /manifest.json
    GET /stream/{type}/{imdb_id}.json                      (movies)
    GET /stream/{type}/{imdb_id}:{season}:{episode}.json   (series)

Also wraps Cinemeta (``v3-cinemeta.strem.io``) for title -> IMDB id
resolution. Cinemeta is its own Stremio addon under the hood but
exposes a catalog-search endpoint we use directly rather than via
the generic addon-query path.

URL normalization policy:

  Both bare base URLs (``https://addon.example``) and manifest-suffixed
  URLs (``https://addon.example/manifest.json``) are accepted on input
  and normalized to the bare base form at the boundary via
  :func:`normalize_addon_base_url`. The bare base is used for path
  composition in ``query_stream``; ``get_manifest`` re-appends
  ``/manifest.json`` after normalization. Addon URLs are never stored
  with the ``/manifest.json`` suffix internally.

  ``normalize_addon_base_url`` is package-public: the diagnose domain's
  ``stack_health`` probe needs the same normalization, so the function
  is exposed rather than duplicated. The normalizer only handles the
  ``/manifest.json`` suffix and trailing slashes -- query strings on
  the input URL (e.g., ``...manifest.json?token=X``) are NOT recognized
  as separable suffixes and will leak into the bare base, then
  re-appear in derived paths. Callers shipping query-stringed manifest
  URLs should strip the query first.

Retry / timeout policy:

  Best-effort by protocol: no tenacity wrapping, no per-call retry.
  A slow addon should fail fast (``AddonTimeout``) rather than burn
  the composer's wall-clock budget on retries. Malformed JSON
  responses raise ``AddonMalformed``. Both errors are wrapped in
  ``MaestroException`` per the project convention; the MCP tool
  boundary translates them to structured ``McpError`` responses.

  Cinemeta's ``cinemeta_search`` is doubly best-effort: any HTTP or
  JSON error returns ``None`` rather than raising. The caller cannot
  distinguish "title doesn't exist" from "Cinemeta is unavailable"
  -- both surface as ``None``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import httpx
import structlog

from maestro.errors import AddonMalformed, AddonTimeout, MaestroException

log = structlog.get_logger("maestro.stremio.client")

CINEMETA_BASE = "https://v3-cinemeta.strem.io"


def normalize_addon_base_url(addon_url: str) -> str:
    """Return the addon base URL without trailing slash or ``/manifest.json`` suffix.

    Accepts either bare (``https://addon.example``) or manifest-suffixed
    (``https://addon.example/manifest.json``) input. Trailing slashes are
    stripped before AND after suffix removal so
    ``https://addon.example/manifest.json/`` normalizes to
    ``https://addon.example`` as well.

    Query strings are PRESERVED via ``urlunparse``. An input like
    ``https://addon.example/manifest.json?token=secret`` normalizes to
    ``https://addon.example?token=secret`` -- the auth token survives
    so callers using :func:`_compose_addon_url` for path joining will
    correctly produce ``https://addon.example/stream/...?token=secret``
    rather than the malformed ``https://addon.example?token=secret/stream/...``
    the prior literal-string approach produced.

    Public symbol (re-exported from the package) so the diagnose
    domain's stack_health probe uses the SAME normalization the
    Stremio client uses internally.
    """
    parsed = urlparse(addon_url)
    new_path = parsed.path.rstrip("/").removesuffix("/manifest.json").rstrip("/")
    return urlunparse(parsed._replace(path=new_path))


def _compose_addon_url(base: str, path: str) -> str:
    """Join ``base`` + ``path`` preserving the base's query string.

    Direct f-string concatenation (``f"{base}{path}"``) mangles URLs
    whose base carries a query string: ``"https://x?t=1" + "/stream/..."``
    becomes ``"https://x?t=1/stream/..."``, which addons reject. This
    helper round-trips through :func:`urlparse` / :func:`urlunparse`
    so the query stays attached to the netloc, not embedded in the
    path.
    """
    parsed = urlparse(base)
    full_path = parsed.path.rstrip("/") + path
    return urlunparse(parsed._replace(path=full_path))


class StremioAddonClient:
    """Reusable HTTP client for any Stremio addon URL.

    Stateless beyond the construction-bound timeout: no auth, no
    cookies, no connection pool reuse across calls. Each method
    instantiates an :class:`httpx.AsyncClient` inside an ``async with``
    so connections are closed deterministically per request. This
    matches the "best-effort, fail-fast" protocol stance -- there's
    no win from keeping a pool open across calls when retries are
    forbidden.

    No tenacity wrapping anywhere in this class: slow addons fail
    fast via ``httpx.TimeoutException``, wrapped in
    :class:`MaestroException` as :class:`AddonTimeout`. Callers that
    want bounded latency should set ``timeout_s`` to the latency
    budget they care about.
    """

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._timeout_s = timeout_s

    async def get_manifest(self, addon_url: str) -> dict[str, Any]:
        """GET ``<addon>/manifest.json`` and return the parsed JSON dict.

        Accepts either bare or manifest-suffixed ``addon_url``; both
        normalize to the same request URL via
        :func:`normalize_addon_base_url`.

        Three distinct failure modes (all wrapped in
        :class:`MaestroException`):

        - :class:`AddonTimeout` if the HTTP request exceeds ``timeout_s``.
        - :class:`AddonMalformed` for any other HTTP error (4xx, 5xx,
          connection refused, DNS failure) -- the original
          :class:`httpx.HTTPError` is chained via ``raise ... from``.
        - :class:`AddonMalformed` for invalid JSON in the response body.
        """
        base = normalize_addon_base_url(addon_url)
        url = _compose_addon_url(base, "/manifest.json")
        parsed = urlparse(url)
        # Use hostname (not netloc) so any user:pass@ userinfo is stripped before logging.
        log.info(
            "stremio_get_manifest_request", host=parsed.hostname, path=parsed.path
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            raise MaestroException(AddonTimeout(message=f"manifest timeout: {addon_url}")) from e
        except httpx.HTTPError as e:
            raise MaestroException(AddonMalformed(message=f"manifest HTTP error: {e}")) from e
        except ValueError as e:
            raise MaestroException(
                AddonMalformed(message=f"manifest malformed JSON from {url}")
            ) from e

    async def query_stream(
        self,
        addon_url: str,
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """GET ``<addon>/stream/<type>/<imdb_id>[:s:e].json`` -> streams list.

        Path composition: series queries (``content_type="series"``,
        both ``season`` and ``episode`` set) include ``:season:episode``;
        movie queries omit them. The function does NOT validate that
        ``season`` / ``episode`` are both-set-or-neither -- it triggers
        the series path iff BOTH are non-None, treating either-but-not-
        both as the movie path. Callers should keep the invariant.

        Three failure modes (all wrapped in :class:`MaestroException`,
        same shape as :meth:`get_manifest`):

        - :class:`AddonTimeout` on HTTP timeout.
        - :class:`AddonMalformed` on HTTP error OR malformed JSON OR
          when the response body's ``streams`` key is not a list.

        Returns the parsed ``streams`` list (may be empty if the addon
        had no candidates).
        """
        base = normalize_addon_base_url(addon_url)
        if season is not None and episode is not None:
            path = f"/stream/{content_type}/{imdb_id}:{season}:{episode}.json"
        else:
            path = f"/stream/{content_type}/{imdb_id}.json"
        url = _compose_addon_url(base, path)
        parsed = urlparse(url)
        # Use hostname (not netloc) so any user:pass@ userinfo is stripped before logging.
        log.info(
            "stremio_query_stream_request",
            host=parsed.hostname,
            path=parsed.path,
            content_type=content_type,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
        )

        # httpx.TimeoutException is a subclass of httpx.HTTPError — order matters:
        # TimeoutException must be caught first to preserve the timeout-vs-malformed
        # distinction the test suite asserts.
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as e:
            raise MaestroException(AddonTimeout(message=f"stream query timeout: {url}")) from e
        except httpx.HTTPError as e:
            raise MaestroException(AddonMalformed(message=f"stream HTTP error: {e}")) from e
        except ValueError as e:
            raise MaestroException(
                AddonMalformed(message=f"stream malformed JSON from {url}")
            ) from e

        if not isinstance(payload, dict):
            raise MaestroException(
                AddonMalformed(message=f"stream response root is not a dict from {url}")
            )
        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            raise MaestroException(AddonMalformed(message=f"streams is not a list in {url}"))
        return streams

    async def cinemeta_search(
        self,
        title: str,
        content_type: str,
    ) -> str | None:
        """Resolve title -> IMDB id via Cinemeta's catalog search endpoint.

        URL-encodes ``title`` for the path; ``content_type`` is
        ``"movie"`` or ``"series"`` (Cinemeta uses it as the catalog
        type segment).

        Returns ``None`` in two distinct conditions the caller cannot
        distinguish:

        - Cinemeta responded successfully but returned no matches
          (or the first match was missing the ``id`` field).
        - Cinemeta failed: HTTP error, JSON decode error, timeout, or
          the response root was not a dict.

        Failed-call errors are logged at warning level under
        ``cinemeta_search_failed`` but never raised -- this method is
        best-effort by design. Callers wanting strict failure handling
        should query Cinemeta directly via
        :meth:`get_manifest` / :meth:`query_stream` (both of which raise
        on failure).

        The first match wins; no relevance tie-breaking is applied.
        If Cinemeta ranks an incorrect match first (e.g., a re-release
        with the same title), the composer will resolve to the wrong
        ``imdb_id``.
        """
        encoded = quote(title, safe="")
        url = f"{CINEMETA_BASE}/catalog/{content_type}/top/search={encoded}.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("cinemeta_search_failed", title=title)
            return None
        if not isinstance(payload, dict):
            log.warning("cinemeta_search_failed", title=title, reason="non_dict_root")
            return None
        metas = payload.get("metas") or []
        if not metas:
            return None
        first = metas[0]
        if not isinstance(first, dict):
            return None
        return first.get("id")
