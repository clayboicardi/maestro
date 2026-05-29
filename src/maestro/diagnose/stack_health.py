"""Stack health probe -- pings each configured addon's manifest endpoint.

Best-effort, like Stremio addon protocol queries: a slow or unreachable
addon should fail fast (caught as ``status=error`` per-addon) rather
than block the entire health response.

URL normalization piggybacks on
:func:`maestro.stremio.normalize_addon_base_url` -- both the Stremio
client and this probe handle bare-base vs. manifest-suffixed inputs
identically, so a base URL that streams correctly also probes correctly.
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

    Failure taxonomy (what becomes ``status="error"`` vs. what escapes):

    - **Caught -> ``status="error"``**: ``httpx.HTTPError`` (connect,
      read, timeout, protocol) and ``ValueError`` -- the latter covers
      ``json.JSONDecodeError`` raised by ``response.json()`` on a
      non-JSON body. ``error`` is populated with a short string and
      latency is still recorded, so the response surfaces "how long did
      this addon take to fail".
    - **NOT caught -> propagates**: a 200 response whose body is valid
      JSON but not an object (e.g. a top-level list or string) makes
      ``response.json().get("id")`` raise ``AttributeError``, which is
      outside the ``(httpx.HTTPError, ValueError)`` catch. It propagates
      out of this coroutine and fails the whole :func:`probe_all` gather
      rather than degrading to a single per-addon error. The Stremio
      client guards this with an explicit "response root is not a dict"
      check; this probe does not (yet), so a single malformed-shape
      manifest can sink the entire stack-health response.
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
    """Probe every addon concurrently; key results by the input URL string.

    Duplicate URLs collapse in the returned dict (last-probe-wins) even
    though each occurrence is still probed -- caller pays for N probes but
    sees fewer than N keys. Pass a de-duplicated list if per-URL accounting
    matters. Keys are the RAW input strings (pre-normalization), so callers
    can correlate results back to the exact configured value.
    """
    results = await asyncio.gather(*(probe_addon(u, timeout_s=timeout_s) for u in addon_urls))
    return dict(zip(addon_urls, results, strict=True))
