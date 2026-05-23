"""Stremio addon protocol domain -- generic client + 6 MCP tools.

Re-exports:

- :func:`.client.normalize_addon_base_url` -- the canonical URL
  normalizer; promoted to package-public so the diagnose domain's
  health probe can apply the same normalization without duplicating
  the policy.
- :func:`.tools.register_tools` -- registers the 6 tools on a FastMCP
  app and returns the :class:`.tools.StremioToolset` so the composer
  can share the same client instance.
"""

from maestro.stremio.client import normalize_addon_base_url
from maestro.stremio.tools import register_tools

__all__ = ["normalize_addon_base_url", "register_tools"]
