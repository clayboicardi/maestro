"""AIOStreams MCP tool definitions (21 tools)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

import structlog

from maestro.aiostreams.modify import ConfigStager, PendingMutation

log = structlog.get_logger("maestro.aiostreams.tools")

REDACTED = "***REDACTED***"

# Resolution floor ladder — must remain a subset of
# maestro.aiostreams.schemas_generated.ExcludedResolution.
# Ordered lowest→highest. "Unknown" intentionally excluded since it
# is a catch-all bucket, not an ordinal resolution.
_RESOLUTION_LADDER: list[str] = [
    "144p",
    "240p",
    "360p",
    "480p",
    "576p",
    "720p",
    "1080p",
    "1440p",
    "2160p",
]


def _redact_secrets(config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(config)
    for service in out.get("services", []):
        if "credential" in service:
            service["credential"] = REDACTED
    return out


class AIOStreamsToolset:
    """Holds the stager + exposes one method per MCP tool.

    The server module wires each method to a FastMCP @tool registration
    with the right annotations.

    Read tools return references into the freshly-fetched config (no
    deepcopy on passthrough fields like addons/filters/sortCriteria/
    statistics). Callers MUST NOT mutate the returned objects. The
    `get_config` and `get_services` paths deepcopy because they pass
    through `_redact_secrets`. If a future client introduces a fetch
    cache, audit each passthrough method for safety.
    """

    def __init__(
        self,
        *,
        get_config: Callable[[], Awaitable[dict[str, Any]]],
        put_config: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        self._stager: ConfigStager = ConfigStager(get_config=get_config, put_config=put_config)
        self._get_config = get_config

    async def get_config(self, *, include_secrets: bool = False) -> dict[str, Any]:
        """Fetch the entire AIOStreams config. Secrets redacted unless explicit."""
        cfg = await self._get_config()
        if not include_secrets:
            cfg = _redact_secrets(cfg)
            log.info("aiostreams_get_config_redacted")
        else:
            log.warning("aiostreams_get_config_with_secrets")
        return cfg

    async def get_services(self) -> list[dict[str, Any]]:
        """List debrid services + priority order (credentials redacted)."""
        cfg = await self._get_config()
        return _redact_secrets(cfg).get("services", [])

    async def get_addons(self) -> list[dict[str, Any]]:
        """List aggregated addons with enabled state + URLs."""
        cfg = await self._get_config()
        return cfg.get("addons", [])

    async def get_filters(self) -> dict[str, Any]:
        """Return current filter settings (language, quality, resolution, etc)."""
        cfg = await self._get_config()
        return cfg.get("filters", {})

    async def get_sort_order(self) -> list[dict[str, Any]]:
        """Return current sort hierarchy."""
        cfg = await self._get_config()
        return cfg.get("sortCriteria", [])

    async def get_active_template(self) -> str:
        """Return active template name, or 'Custom' if hand-edited."""
        cfg = await self._get_config()
        return cfg.get("presets", {}).get("active", "Custom")

    async def get_statistics(self) -> dict[str, Any]:
        """Return Show Statistics & Errors block for dud-rate debugging."""
        cfg = await self._get_config()
        return cfg.get("statistics", {})

    async def get_template_list(self) -> list[dict[str, Any]]:
        """Return available templates (Tamtaro variants + community).

        Phase 3 stub - implementation in Task 3.4 (templates.py).
        """
        return []

    async def _stage_filter(self, *, key: str, value: Any) -> PendingMutation:
        """Internal helper: stage a write under `filters.<key>`.

        Used by typed filter setters and (Task 3.7's) generic `set_filter`.
        """
        return await self._stager.modify(
            lambda cfg: {**cfg, "filters": {**cfg.get("filters", {}), key: value}},
            field=f"filters.{key}",
        )

    async def set_preferred_languages(self, languages: list[str]) -> PendingMutation:
        """Stage `filters.preferred_languages`. Order matters - first is primary."""
        return await self._stage_filter(key="preferred_languages", value=list(languages))

    async def set_cached_only(self, *, enabled: bool) -> PendingMutation:
        """Stage `filters.only_cached`. When true, AIOStreams returns only RD-cached streams."""
        return await self._stage_filter(key="only_cached", value=enabled)

    async def set_resolution_floor(self, min_resolution: str) -> PendingMutation:
        """Exclude all resolutions below `min_resolution`.

        Valid values: 144p, 240p, 360p, 480p, 576p, 720p, 1080p, 1440p, 2160p.
        (Matches AIOStreams' ExcludedResolution enum minus "Unknown".)
        """
        if min_resolution not in _RESOLUTION_LADDER:
            raise ValueError(
                f"min_resolution must be one of {_RESOLUTION_LADDER}, got {min_resolution!r}"
            )
        index = _RESOLUTION_LADDER.index(min_resolution)
        excluded = _RESOLUTION_LADDER[:index]
        return await self._stage_filter(key="excluded_resolutions", value=excluded)

    async def set_core_engine(self, engine: str) -> PendingMutation:
        """Set the SEL core engine. Valid: 'Standard SEL - 3 per Q/R', 'Extended SEL - 6 per Q/R'."""
        valid = {"Standard SEL - 3 per Q/R", "Extended SEL - 6 per Q/R"}
        if engine not in valid:
            raise ValueError(f"engine must be one of {sorted(valid)}, got {engine!r}")
        return await self._stager.modify(
            lambda cfg: {**cfg, "core_engine": engine},
            field="core_engine",
        )
