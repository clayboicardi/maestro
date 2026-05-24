"""Torrentio enum values extracted from upstream ``addon/lib/filter.js`` + ``sort.js``.

Source:
- https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/filter.js
- https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/sort.js

Frozen snapshots of the values Torrentio's config parser accepts as
of the 2026-05-23 refresh (last manual verification via ``curl`` of
upstream JS during Phase 3.5 fix-PR). There is NO automated drift
check in v1 -- refresh manually by re-reading upstream and diffing
against the constants below.

Usage map (which constants are referenced where):

- :data:`PROVIDERS` -- enforced by :func:`.encoder.validate_config`
  on ``cfg.providers`` (case-insensitive); exposed via the
  ``torrentio_list_providers`` MCP tool.
- :data:`QUALITY_FILTERS` -- enforced by
  :func:`.encoder.validate_config` on ``cfg.quality_filter``
  (case-insensitive); exposed via the
  ``torrentio_list_quality_filters`` MCP tool.
- :data:`DEBRID_PROVIDERS` -- consumed by :func:`.encoder.parse_url`
  to detect debrid-style ``<provider>=<key>`` segments AND enforced by
  :func:`.encoder.validate_config` on ``cfg.debrid_provider``
  (case-insensitive post-Phase-3.5-fix; mirrors upstream behavior).
- :data:`SORT_OPTIONS` -- enforced by
  :func:`.encoder.validate_config` on ``cfg.sort``
  (case-insensitive); exposed via ``torrentio_list_sort_options``.

Drift-detection suggestion (post-v0.1.0 polish item): a small smoke
test that fetches the upstream JS file SHAs and asserts they match
pinned hashes here, equivalent to the
``aiostreams_schema.sha256`` drift gate already in use for AIOStreams.
The Phase 3.5 triangulation surfaced significant drift in both
``QUALITY_FILTERS`` (8+ new upstream keys missing; multiple stale
keys removed upstream) and ``SORT_OPTIONS`` (3 of 6 maestro keys
didn't exist upstream); automated drift detection would have
caught both.
"""

from __future__ import annotations

PROVIDERS: list[str] = [
    "yts",
    "eztv",
    "rarbg",
    "1337x",
    "thepiratebay",
    "kickasstorrents",
    "torrentgalaxy",
    "magnetdl",
    "horriblesubs",
    "nyaasi",
    "tokyotosho",
    "anidex",
    "rutor",
    "rutracker",
    "comando",
    "bludv",
    "micoleaodublado",
    "torrent9",
    "ilcorsaronero",
    "mejortorrent",
    "wolfmax4k",
    "cinecalidad",
    "besttorrents",
    "nekobt",
]

# QUALITY_FILTERS refreshed against upstream filter.js as of 2026-05-23.
# Pre-Phase-3.5 list had ~17 stale values (ts, telesync, r5, r6, hdcam, hdts,
# hdtelesync, hdrip, brrip, bdrip, dvdrip, dvdr, dvdscr, 240p, 360p) that
# upstream no longer recognizes, AND was missing 8+ current upstream keys
# (brremux, hdrall, dolbyvision, dolbyvisionwithhdr, threed, nonthreed, 4k,
# 1080p, 720p, other, unknown). Both directions of drift would produce
# validation false-positives -- callers with the upstream values would get
# "unknown" errors, callers with maestro's stale values would build URLs
# that upstream silently no-ops.
QUALITY_FILTERS: list[str] = [
    "brremux",
    "hdrall",
    "dolbyvision",
    "dolbyvisionwithhdr",
    "threed",
    "nonthreed",
    "4k",
    "1080p",
    "720p",
    "480p",
    "other",
    "scr",
    "cam",
    "unknown",
]

DEBRID_PROVIDERS: list[str] = [
    "realdebrid",
    "premiumize",
    "alldebrid",
    "debridlink",
    "easydebrid",
    "offcloud",
    "torbox",
    "putio",
]

# SORT_OPTIONS refreshed against upstream sort.js:14-32 as of 2026-05-23.
# Pre-Phase-3.5 list had 3 keys upstream doesn't recognize: 'qualityseeders'
# (upstream uses 'quality' for that option), 'sizequality' and
# 'seedersquality' (don't exist upstream at all). Maestro was missing the
# actual upstream 'quality' key. Validation would pass on values upstream
# silently no-ops.
SORT_OPTIONS: list[str] = [
    "quality",
    "qualitysize",
    "seeders",
    "size",
]
