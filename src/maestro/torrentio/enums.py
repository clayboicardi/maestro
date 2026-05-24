"""Torrentio enum values extracted from upstream ``addon/lib/filter.js``.

Source: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/filter.js

Frozen snapshots of the values Torrentio's config parser accepts as
of the last manual refresh (no version pin -- the file in upstream
may have moved on). Refresh by re-reading the upstream file and
diffing against the constants below; there is NO automated drift
check in v1.

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
  (case-sensitive, unlike providers/quality_filter).
- :data:`SORT_OPTIONS` -- enforced by
  :func:`.encoder.validate_config` on ``cfg.sort`` (case-sensitive).
- :data:`RESOLUTIONS` -- **DEFINED BUT UNUSED in v1**. Neither
  validation nor parsing consults this constant. Retained for
  reference; dead-constant cleanup candidate.
- :data:`LANGUAGES` -- **DEFINED BUT UNUSED in v1**. Same status as
  :data:`RESOLUTIONS`. The ``TorrentioConfig.languages`` field is
  populated by ``parse_url`` and round-tripped by ``build_url`` but
  membership against this constant is never checked.

Drift-detection suggestion (post-v0.1.0 polish item): a small smoke
test that fetches the upstream ``filter.js`` SHA and asserts it
matches a pinned hash here, equivalent to the
``aiostreams_schema.sha256`` drift gate already in use for AIOStreams.
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

QUALITY_FILTERS: list[str] = [
    "cam",
    "ts",
    "telesync",
    "scr",
    "screener",
    "r5",
    "r6",
    "hdcam",
    "hdts",
    "hdtelesync",
    "hdrip",
    "brrip",
    "bdrip",
    "dvdrip",
    "dvdr",
    "dvdscr",
    "3d",
    "480p",
    "240p",
    "360p",
]

RESOLUTIONS: list[str] = [
    "240p",
    "360p",
    "480p",
    "720p",
    "1080p",
    "1440p",
    "4k",
    "8k",
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

LANGUAGES: list[str] = [
    "english",
    "russian",
    "italian",
    "portuguese",
    "spanish",
    "french",
    "german",
    "japanese",
    "korean",
    "chinese",
    "polish",
]

SORT_OPTIONS: list[str] = [
    "qualitysize",
    "qualityseeders",
    "sizequality",
    "seedersquality",
    "seeders",
    "size",
]
