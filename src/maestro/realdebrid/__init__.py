"""Real-Debrid domain -- REST client, filter-gate learner, and 7 MCP tools.

This package owns the MCP tool surface (7 total) for the Real-Debrid
restricted-URL CDN integration plus the May 2026 filter-gate runtime
learning loop. Layered as:

- :mod:`.client` -- async httpx wrapper around the RD REST API
  (``api.real-debrid.com/rest/1.0``) with retry + tenacity transient-
  error classification. Bearer-token auth; per-status-code translation
  to typed :class:`maestro.errors.MaestroException` payloads.
- :mod:`.filter_gate` -- :class:`.filter_gate.FilterGateLearner`
  predicts ``infringing_file`` risk per filename from a static
  ``KNOWN_KEYWORDS`` baseline plus a runtime-learned set persisted to
  ``~/.config/maestro/filter_gate_state.json``.
- :mod:`.tools` -- :class:`.tools.RDToolset` exposes the seven MCP
  tools enumerated below: four read-only queries (cache check,
  library list, user info, torrent status), one pure-compute risk
  heuristic (filter-gate check), and two destructive ops (add
  torrent, unrestrict link). The cache-check tool overlays the
  filter-gate risk heuristic so Claude can avoid burning daily-cap
  quota on ``infringing_file`` 403s.
- :func:`.tools.register_tools` -- wires the toolset onto a FastMCP app
  and returns the live toolset so a downstream composer
  (``find_best_stream``) can share the client + learner without
  re-instantiating.

Key contracts (see module-level docstrings for details):

- Bearer token is unwrapped from ``SecretStr`` exactly at register
  time and bound into the httpx ``Authorization`` header for the
  lifetime of the process.
- Filter-gate state is single-process, single-writer; atomic-replace
  via a sibling ``.tmp`` file. No schema_version field in v1 -- state
  is recoverable from ``KNOWN_KEYWORDS`` + future strikes if the file
  is ever discarded or fails to parse.
- ``RDClient.aclose`` is intentionally not invoked at stdio-MCP
  shutdown.
"""

from maestro.realdebrid.tools import register_tools

__all__ = ["register_tools"]
