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
        return result


def merge_template_into_config(
    base: dict[str, Any],
    template: dict[str, Any],
    *,
    mode: Mode,
) -> dict[str, Any]:
    """Overlay template keys onto a base config.

    Mode is recorded but currently a passthrough — future versions may apply
    mode-specific filtering. For each top-level key in ``template``: if both
    base and template values are dicts, the template's keys are shallow-merged
    into the base dict (template wins on conflict, base keys not in template
    are preserved). Otherwise the template's value REPLACES the base value.
    """
    merged = deepcopy(base)
    for key, value in template.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = {**existing, **deepcopy(value)}
        else:
            merged[key] = deepcopy(value)
    merged.setdefault("_meta", {})["applied_mode"] = mode
    return merged
