"""Stremio addon protocol domain (generic client + 6 MCP tools)."""

from maestro.stremio.client import normalize_addon_base_url
from maestro.stremio.tools import register_tools

__all__ = ["normalize_addon_base_url", "register_tools"]
