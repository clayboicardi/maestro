"""Stremio addon protocol domain -- generic client + 6 MCP tools.

Re-exports:

- :func:`.client.normalize_addon_base_url` -- the canonical URL
  normalizer; promoted to package-public so the diagnose domain's
  health probe can apply the same normalization without duplicating
  the policy.
- :func:`.client.compose_addon_url` -- the query-preserving path joiner;
  package-public for the same reason (the health probe composes the
  ``/manifest.json`` URL the same way the streaming path does).
- :func:`.tools.register_tools` -- registers the 6 tools on a FastMCP
  app and returns the :class:`.tools.StremioToolset` so the composer
  can share the same client instance.
"""

from maestro.stremio.client import compose_addon_url, normalize_addon_base_url
from maestro.stremio.tools import register_tools

__all__ = ["compose_addon_url", "normalize_addon_base_url", "register_tools"]
