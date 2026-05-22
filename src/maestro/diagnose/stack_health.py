"""Stack health probe -- pings each configured addon's manifest endpoint.

Best-effort, like Stremio addon protocol queries: a slow or unreachable
addon should fail fast (caught as ``status=error`` per-addon) rather
than block the entire health response.

URL normalization piggybacks on
:func:`maestro.stremio.normalize_addon_base_url` -- both the Stremio
client and this probe handle bare-base vs. manifest-suffixed inputs
identically (CF13 resolution).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from maestro.stremio import normalize_addon_base_url

# HTTP status threshold for "addon manifest probe failed". 4xx/5xx are
# both classified as ``error`` because either prevents the addon from
# serving a usable manifest.
_HTTP_ERROR_THRESHOLD: int = 400


async def probe_addon(addon_url: str, *, timeout_s: float) -> dict[str, Any]:
    """Single addon probe. Returns ``{status, latency_ms, ...}``.

    On success: ``status="ok"``, ``manifest_id`` populated from the
    addon's ``id`` field.
    On any HTTP/JSON failure: ``status="error"``, ``error`` populated
    with a short string. Latency is recorded even on failure so the
    response surfaces "how long did this addon take to fail".
    """
    base = normalize_addon_base_url(addon_url)
    url = f"{base}/manifest.json"
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
            return {
                "status": "ok",
                "latency_ms": elapsed_ms,
                "manifest_id": response.json().get("id"),
            }
    except (httpx.HTTPError, ValueError) as e:
        return {
            "status": "error",
            "latency_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }


async def probe_all(addon_urls: list[str], *, timeout_s: float) -> dict[str, dict[str, Any]]:
    """Probe every addon concurrently; key results by the input URL string."""
    results = await asyncio.gather(*(probe_addon(u, timeout_s=timeout_s) for u in addon_urls))
    return dict(zip(addon_urls, results, strict=True))
