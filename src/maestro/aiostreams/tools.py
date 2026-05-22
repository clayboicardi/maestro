"""AIOStreams MCP tool definitions (21 tools)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

import structlog

from maestro.aiostreams.modify import ConfigStager

log = structlog.get_logger("maestro.aiostreams.tools")

REDACTED = "***REDACTED***"


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
