"""Generic Stremio addon client.

Speaks the Stremio addon protocol:
  GET /manifest.json
  GET /stream/{type}/{imdb_id}.json                      (movies)
  GET /stream/{type}/{imdb_id}:{season}:{episode}.json   (series)

Also wraps Cinemeta search for title -> imdb_id resolution.

URL normalization policy (CF3 + CF13 uniform):
  Both bare base URLs (``https://addon.example``) and manifest-suffixed
  URLs (``https://addon.example/manifest.json``) are accepted on input
  and normalized to the bare base form at the boundary via
  :func:`normalize_addon_base_url`. The bare base form is used for path
  composition in ``query_stream``; ``get_manifest`` re-appends
  ``/manifest.json`` after normalization. Addon URLs are never stored
  with the ``/manifest.json`` suffix internally.

  ``normalize_addon_base_url`` is the package-level public normalizer
  (CF13 resolution, Phase 8): the diagnose domain's stack_health probe
  needs the same normalization. Promoting from the previous
  ``_normalize_addon_base_url`` private form consolidates the policy
  to a single import site.

Best-effort by protocol — no tenacity wrapping. A slow addon should
fail fast (``AddonTimeout``) rather than burn the timeout budget on
retries. Malformed responses raise ``AddonMalformed``. Both errors
are wrapped in ``MaestroException`` per the project convention; the
MCP tool boundary translates them to structured ``McpError`` responses.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from maestro.errors import AddonMalformed, AddonTimeout, MaestroException

log = structlog.get_logger("maestro.stremio.client")

CINEMETA_BASE = "https://v3-cinemeta.strem.io"


def normalize_addon_base_url(addon_url: str) -> str:
    """Return the addon base URL without trailing slash or ``/manifest.json`` suffix.

    Accepts either bare (``https://addon.example``) or manifest-suffixed
    (``https://addon.example/manifest.json``) input. Trailing slashes are
    stripped after suffix removal so ``https://addon.example/manifest.json/``
    normalizes to ``https://addon.example`` as well.

    Public per CF13 (Phase 8): the diagnose stack_health probe needs the
    same normalization the Stremio client uses, so the function is exposed
    rather than duplicated.
    """
    return addon_url.rstrip("/").removesuffix("/manifest.json").rstrip("/")


class StremioAddonClient:
    """Reusable client for any Stremio addon URL.

    No auth, no retries — Stremio addons are best-effort by protocol.
    Per-call timeout is bound at construction.
    """

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._timeout_s = timeout_s

    async def get_manifest(self, addon_url: str) -> dict[str, Any]:
        """GET ``<addon>/manifest.json``.

        Accepts either bare or manifest-suffixed input; both normalize
        to the same request URL.
        """
        base = normalize_addon_base_url(addon_url)
        url = f"{base}/manifest.json"
        log.info("stremio_get_manifest_request", url=url)
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

        Series queries include ``:season:episode``; movie queries omit them.
        """
        base = normalize_addon_base_url(addon_url)
        if season is not None and episode is not None:
            path = f"/stream/{content_type}/{imdb_id}:{season}:{episode}.json"
        else:
            path = f"/stream/{content_type}/{imdb_id}.json"
        url = f"{base}{path}"
        log.info(
            "stremio_query_stream_request",
            url=url,
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

        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            raise MaestroException(AddonMalformed(message=f"streams is not a list in {url}"))
        return streams

    async def cinemeta_search(
        self,
        title: str,
        content_type: str,
    ) -> str | None:
        """Resolve title -> IMDB id via Cinemeta search.

        Returns ``None`` on zero matches OR on any HTTP / JSON error;
        the caller (Phase 7 composer) decides whether ``None`` means
        ``TitleUnresolved`` or "try again later". Errors are logged at
        warning level but never raised — this method is best-effort.
        """
        encoded = quote(title)
        url = f"{CINEMETA_BASE}/catalog/{content_type}/top/search={encoded}.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("cinemeta_search_failed", title=title)
            return None
        metas = payload.get("metas") or []
        if not metas:
            return None
        first = metas[0]
        if not isinstance(first, dict):
            return None
        return first.get("id")
