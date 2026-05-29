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
from urllib.parse import urlparse

import httpx

from maestro.stremio import normalize_addon_base_url
from maestro.stremio.client import _compose_addon_url

# HTTP status threshold for "addon manifest probe failed". 4xx/5xx are
# both classified as ``error`` because either prevents the addon from
# serving a usable manifest.
_HTTP_ERROR_THRESHOLD: int = 400


def _host_key(url: str) -> str:
    """Secret-free, collision-tolerant result key for an addon URL.

    Returns ``scheme://host`` only -- path, query, userinfo, and fragment
    are all dropped, so a token embedded ANYWHERE in the addon URL (query
    ``?token=`` OR path ``/realdebrid=.../`` as torrentio/RD configs use)
    never surfaces as a response key. Same-host addons map to the same base
    key by design; :func:`probe_all` disambiguates them with a counter
    suffix rather than silently overwriting.

    ``urlparse`` itself can raise ``ValueError`` on a malformed netloc
    (e.g. an unbalanced IPv6 bracket); the probe must stay resilient during
    key generation, so that falls back to the literal ``"addon"`` key.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        return f"{parsed.scheme or 'https'}://{host}" if host else "addon"
    except ValueError:
        return "addon"


async def probe_addon(addon_url: str, *, timeout_s: float) -> dict[str, Any]:
    """Single addon probe. Returns ``{status, latency_ms, ...}``.

    On success: ``status="ok"``, ``manifest_id`` populated from the addon's
    ``id`` field. A reachable addon whose manifest object omits ``id`` still
    reports ``status="ok"`` with ``manifest_id=None`` -- the probe confirms
    reachability, not manifest-schema completeness.

    Every failure mode degrades to ``status="error"`` for THIS addon only
    (latency still recorded); none escape to sink :func:`probe_all`. The
    try block wraps URL normalization/composition AND the HTTP call, so a
    ``urlparse`` ``ValueError`` from a malformed addon URL is caught too --
    not just transport/JSON errors:

    - ``ValueError`` from ``normalize_addon_base_url`` / ``_compose_addon_url``
      (malformed netloc, bad port, unbalanced IPv6 bracket) -> caught.
    - ``httpx.HTTPError`` (connect, read, timeout, protocol) -> caught.
    - ``ValueError`` incl. ``json.JSONDecodeError`` on a non-JSON body ->
      caught.
    - A 200 body that is valid JSON but not an object (top-level list,
      ``null``, number, bool, string) is guarded by an ``isinstance`` check
      and reported as ``error="manifest root is not a JSON object"``.
    - ``>= 400`` status -> ``error="HTTP <code>"``.
    """
    start = time.monotonic()
    try:
        base = normalize_addon_base_url(addon_url)
        url = _compose_addon_url(base, "/manifest.json")
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
    """Probe every addon concurrently; key results by a secret-free host key.

    Keys are ``scheme://host`` (via :func:`_host_key`) so no token embedded
    in an addon URL's query OR path can surface as a response key. Distinct
    addons that share a host (or the same addon configured twice) are
    disambiguated with a ``" (N)"`` suffix -- results are NEVER silently
    overwritten, so a failing addon cannot be hidden behind a healthy one
    with a colliding key. Each ``probe_addon`` resolves to a per-addon
    result dict, so one malformed addon never sinks the gather.
    """
    results = await asyncio.gather(*(probe_addon(u, timeout_s=timeout_s) for u in addon_urls))
    out: dict[str, dict[str, Any]] = {}
    for url, result in zip(addon_urls, results, strict=True):
        key = _host_key(url)
        if key in out:
            n = 2
            while f"{key} ({n})" in out:
                n += 1
            key = f"{key} ({n})"
        out[key] = result
    return out
