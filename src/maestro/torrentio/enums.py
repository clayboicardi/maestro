"""Torrentio enum values extracted from `addon/lib/filter.js`.

Source: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/filter.js

These are the valid values that Torrentio's config parser accepts.
Refresh when upstream adds providers/qualities.
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
