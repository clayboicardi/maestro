"""Encode/decode Torrentio install URLs.

URL grammar (per addon/lib/configuration.js):

    <base>/<key>=<value>[|<key>=<value>...]/manifest.json

Where each <value> is comma-delimited for list fields. Debrid keys use
`<provider>=<token>` form rather than `debrid=...`.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from pydantic import BaseModel, Field

from maestro.torrentio.enums import DEBRID_PROVIDERS, PROVIDERS, QUALITY_FILTERS, SORT_OPTIONS


class TorrentioConfig(BaseModel):
    """A Torrentio install-URL configuration."""

    providers: list[str] = Field(default_factory=list)
    sort: str | None = None
    quality_filter: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    limit: int | None = None
    size_filter: str | None = None
    debrid_provider: str | None = None
    debrid_key: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


_KV_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)=([^|/]+)")


def parse_url(url: str) -> TorrentioConfig:
    """Parse a Torrentio install URL into a TorrentioConfig."""
    base_strip = re.sub(r"https?://[^/]+/?", "", url).strip("/")
    base_strip = base_strip.replace("/manifest.json", "").rstrip("/")

    cfg = TorrentioConfig()
    for match in _KV_RE.finditer(base_strip):
        key = match.group(1).lower()
        raw = match.group(2)
        if key == "providers":
            cfg.providers = [p.strip() for p in raw.split(",") if p.strip()]
        elif key == "sort":
            cfg.sort = raw.strip()
        elif key == "qualityfilter":
            cfg.quality_filter = [q.strip() for q in raw.split(",") if q.strip()]
        elif key == "languages":
            cfg.languages = [lang.strip() for lang in raw.split(",") if lang.strip()]
        elif key == "limit":
            with contextlib.suppress(ValueError):
                cfg.limit = int(raw.strip())
        elif key == "sizefilter":
            cfg.size_filter = raw.strip()
        elif key in DEBRID_PROVIDERS:
            cfg.debrid_provider = key
            cfg.debrid_key = raw.strip()
        else:
            cfg.extra[key] = raw.strip()
    return cfg


def build_url(cfg: TorrentioConfig, *, base_url: str = "https://torrentio.strem.fun") -> str:
    """Build a Torrentio install URL from a TorrentioConfig."""
    parts: list[str] = []
    if cfg.providers:
        parts.append(f"providers={','.join(cfg.providers)}")
    if cfg.sort:
        parts.append(f"sort={cfg.sort}")
    if cfg.quality_filter:
        parts.append(f"qualityfilter={','.join(cfg.quality_filter)}")
    if cfg.languages:
        parts.append(f"languages={','.join(cfg.languages)}")
    if cfg.limit is not None:
        parts.append(f"limit={cfg.limit}")
    if cfg.size_filter:
        parts.append(f"sizefilter={cfg.size_filter}")
    for k, v in cfg.extra.items():
        parts.append(f"{k}={v}")
    if cfg.debrid_provider and cfg.debrid_key:
        parts.append(f"{cfg.debrid_provider}={cfg.debrid_key}")

    base = base_url.rstrip("/")
    if not parts:
        return f"{base}/manifest.json"
    return f"{base}/{('|').join(parts)}/manifest.json"


def validate_config(cfg: TorrentioConfig) -> list[str]:
    """Return a list of human-readable validation errors. Empty = valid."""
    errors: list[str] = []

    for p in cfg.providers:
        if p.lower() not in PROVIDERS:
            errors.append(f"unknown provider: {p!r} (valid: {PROVIDERS})")

    for q in cfg.quality_filter:
        if q.lower() not in QUALITY_FILTERS:
            errors.append(f"unknown quality_filter: {q!r}")

    if cfg.sort and cfg.sort not in SORT_OPTIONS:
        errors.append(f"unknown sort: {cfg.sort!r} (valid: {SORT_OPTIONS})")

    if cfg.debrid_provider and cfg.debrid_provider not in DEBRID_PROVIDERS:
        errors.append(f"unknown debrid_provider: {cfg.debrid_provider!r}")

    return errors


def _data() -> dict[str, Any]:
    """Diagnostic dump of which constants are loaded."""
    return {
        "providers": PROVIDERS,
        "quality_filters": QUALITY_FILTERS,
        "debrid_providers": DEBRID_PROVIDERS,
        "sort_options": SORT_OPTIONS,
    }
