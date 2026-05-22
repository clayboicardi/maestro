"""Template fetching + merging for AIOStreams community configs.

A "template" is a pre-built AIOStreams UserData JSON blob curated by
the community (currently Tam-Taro/SEL-Filtering-and-Sorting, which
auto-syncs Vidhin05/Releases-Regex into its regex pack). Templates
encode opinionated SEL setups: filter defaults, sort order, addon
selection, and regex packs tuned for Debrid/P2P/Both workflows.

Apply path: :func:`fetch_template` pulls the JSON from its GitHub raw
URL; :func:`merge_template_into_config` overlays it onto the user's
current config; the result is staged through
:class:`maestro.aiostreams.modify.ConfigStager` and flushed with a
single PUT.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import httpx
import structlog

log = structlog.get_logger("maestro.aiostreams.templates")

# Apply-time mode hint for the SEL setup. Today this is a documentation
# parameter on :func:`merge_template_into_config` -- it does not alter
# the merge result. Reserved for future mode-driven filtering when the
# template format gains explicit per-mode sections.
# - "Debrid": assume RD/AD/Premiumize available; bias toward cached streams.
# - "P2P"   : assume no debrid backend; bias toward seeded P2P streams.
# - "Both"  : permissive default; surface both buckets.
Mode = Literal["Debrid", "P2P", "Both"]

KNOWN_TEMPLATES: list[dict[str, str]] = [
    {
        "name": "Tamtaro Complete SEL Setup v2.6.1",
        "source_url": (
            "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
            "main/templates/complete-sel-setup-v2.6.1.json"
        ),
        "description": (
            "Tamtaro's all-in-one Debrid/Usenet/P2P template with English preference, "
            "Standard SEL (~20 results), auto-synced Vidhin's Regexes."
        ),
    },
]


def list_templates() -> list[dict[str, str]]:
    """Return the curated template catalog (no network)."""
    return list(KNOWN_TEMPLATES)


async def fetch_template(source_url: str, *, timeout_s: float = 10.0) -> dict[str, Any]:
    """Fetch a template JSON from its source URL.

    Issues a single GET with redirect following enabled. Raises:

    - ``httpx.HTTPStatusError`` on non-2xx response,
    - ``httpx.RequestError`` on network failure or timeout,
    - ``ValueError`` if the response parses as JSON but the top-level
      value is not an object (template contract requires a dict).

    No retry or backoff at this layer -- templates are pulled at apply
    time, and the user-visible error message benefits from being
    immediate. Default timeout is 10s; callers needing longer
    propagation should pass ``timeout_s`` explicitly.
    """
    log.info("aiostreams_fetch_template", url=source_url)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.get(source_url, follow_redirects=True)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected JSON object from template URL {source_url!r}, "
                f"got {type(result).__name__}"
            )
        return result


def merge_template_into_config(
    base: dict[str, Any],
    template: dict[str, Any],
    *,
    mode: Mode,
) -> dict[str, Any]:
    """Overlay template keys onto a base config (one-level deep merge).

    For each top-level key in template:
      - If both base[key] and template[key] are dicts: shallow-merge
        with template winning on key conflicts. Keys present in
        base[key] but not template[key] are preserved.
      - Otherwise (including template[key] is None or a list): replace
        base[key] wholesale. Note: setting a key to None sets the
        merged key TO None -- it does not remove the key. The base
        entry is overwritten, not deleted; downstream consumers
        iterating ``merged.keys()`` or testing ``key in merged`` will
        still see it. For the upstream UserDataSchema with
        ``extra="forbid"``, passing None on a required field would
        fail validation rather than skip silently.

    Mode is a placeholder for future mode-driven filtering
    (Debrid/P2P/Both); today it has no effect on the merge result.
    Callers should still pass it so the call site documents intent.
    """
    merged = deepcopy(base)
    for key, value in template.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = {**existing, **deepcopy(value)}
        else:
            merged[key] = deepcopy(value)
    return merged
