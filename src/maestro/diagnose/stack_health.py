"""Stack health probe -- pings each configured addon's manifest endpoint.

Best-effort, like Stremio addon protocol queries: a slow, unreachable, or
malformed-response addon should fail fast (caught as ``status=error``
per-addon) rather than block or sink the entire health response.

URL handling reuses the Stremio client's helpers so the probe hits the
SAME endpoint the streaming path would:
:func:`maestro.stremio.normalize_addon_base_url` strips the
``/manifest.json`` suffix + trailing slashes (preserving any query string),
and :func:`maestro.stremio.client._compose_addon_url` re-joins the
``/manifest.json`` path via ``urlparse`` so a query-auth base like
``https://x?token=S`` composes to ``https://x/manifest.json?token=S`` rather
than the malformed ``https://x?token=S/manifest.json`` an f-string produces.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from maestro.stremio import normalize_addon_base_url
from maestro.stremio.client import _compose_addon_url, _sanitize_url_for_message

# HTTP status threshold for "addon manifest probe failed". 4xx/5xx are
# both classified as ``error`` because either prevents the addon from
# serving a usable manifest.
_HTTP_ERROR_THRESHOLD: int = 400


async def probe_addon(addon_url: str, *, timeout_s: float) -> dict[str, Any]:
    """Single addon probe. Returns ``{status, latency_ms, ...}``.

    On success: ``status="ok"``, ``manifest_id`` populated from the addon's
    ``id`` field. A reachable addon whose manifest object omits ``id`` still
    reports ``status="ok"`` with ``manifest_id=None`` -- the probe confirms
    reachability, not manifest-schema completeness.

    Every failure mode degrades to ``status="error"`` for THIS addon only
    (latency still recorded); none escape to sink :func:`probe_all`:

    - ``httpx.HTTPError`` (connect, read, timeout, protocol) and
      ``ValueError`` (incl. ``json.JSONDecodeError`` on a non-JSON body)
      are caught.
    - A 200 body that is valid JSON but not an object (top-level list,
      ``null``, number, bool, string) is guarded by an ``isinstance``
      check and reported as ``error="manifest root is not a JSON object"``
      -- ``.get("id")`` is only called once the body is known to be a dict.
    - ``>= 400`` status -> ``error="HTTP <code>"``.
    """
    base = normalize_addon_base_url(addon_url)
    url = _compose_addon_url(base, "/manifest.json")
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(url, follow_redirects=True)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if response.status_code >= _HTTP_ERROR_THRESHOLD:
                return {
                    "status": "error",
                    "latency_ms": elapsed_ms,
                    "error": f"HTTP {response.status_code}",
                }
            payload = response.json()
            if not isinstance(payload, dict):
                return {
                    "status": "error",
                    "latency_ms": elapsed_ms,
                    "error": "manifest root is not a JSON object",
                }
            return {
                "status": "ok",
                "latency_ms": elapsed_ms,
                "manifest_id": payload.get("id"),
            }
    except (httpx.HTTPError, ValueError) as e:
        return {
            "status": "error",
            "latency_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }


async def probe_all(addon_urls: list[str], *, timeout_s: float) -> dict[str, dict[str, Any]]:
    """Probe every addon concurrently; key results by a sanitized addon URL.

    Keys run through :func:`_sanitize_url_for_message` (drops query string +
    userinfo + fragment) so a query-auth addon like ``https://x?token=S``
    does NOT surface ``token=S`` as a dict key in the health response. Two
    URLs that differ only in stripped components therefore collapse to one
    key (last-probe-wins) even though each is still probed; pass distinct
    host/path URLs if per-URL accounting matters. Each ``probe_addon``
    resolves to a per-addon result dict, so one malformed addon never sinks
    the gather.
    """
    results = await asyncio.gather(*(probe_addon(u, timeout_s=timeout_s) for u in addon_urls))
    return {_sanitize_url_for_message(u): r for u, r in zip(addon_urls, results, strict=True)}
