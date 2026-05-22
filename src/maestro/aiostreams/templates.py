"""Template fetching + merging for Tamtaro/Vidhin community configs.

Templates are JSON files hosted on GitHub by the community
(Tam-Taro/SEL-Filtering-and-Sorting, Vidhin05/Releases-Regex).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import httpx
import structlog

log = structlog.get_logger("maestro.aiostreams.templates")

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
    """Fetch a template JSON from its source URL."""
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
      - If both base[key] and template[key] are dicts: shallow-merge with
        template winning on key conflicts. Keys present in base[key] but
        not template[key] are preserved.
      - Otherwise (including template[key] is None or a list): replace
        base[key] wholesale. Setting a key to None intentionally erases
        the base entry.

    Mode is a placeholder for future mode-driven filtering (Debrid/P2P/Both);
    today it has no effect on the merge result. Callers should still pass
    it so the call site documents intent.
    """
    merged = deepcopy(base)
    for key, value in template.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = {**existing, **deepcopy(value)}
        else:
            merged[key] = deepcopy(value)
    return merged
