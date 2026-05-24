"""Encode + decode Torrentio install URLs (pipe-delimited config segment).

Pipe-delimited URL grammar per Torrentio's upstream parser
(``addon/lib/configuration.js`` on the torrentio-scraper repo):

    <base>/<key>=<value>[|<key>=<value>...]/manifest.json

Where:

- ``<base>`` defaults to ``https://torrentio.strem.fun`` (overridable
  in :func:`build_url` via ``base_url=``; ``MAESTRO_TORRENTIO_BASE_URL``
  env var is NOT consumed in v1, so the override is per-call only).
- ``<value>`` is comma-delimited for list fields
  (``providers=yts,eztv`` or ``qualityfilter=cam,ts``).
- Debrid keys use ``<provider>=<token>`` form (e.g., ``realdebrid=ABC``)
  rather than the generic ``debrid=...`` -- the parser detects debrid
  by matching the key against :data:`.enums.DEBRID_PROVIDERS`.

Wire-vs-model naming asymmetries (the model uses Pythonic snake_case;
the wire format does NOT):

- Wire ``qualityfilter`` <-> model ``quality_filter``
- Wire ``sizefilter`` <-> model ``size_filter``
- Wire ``<debrid_provider>`` (e.g., ``realdebrid``) <-> model
  ``debrid_provider`` + ``debrid_key``

``parse_url`` lowercases keys before dispatch but PRESERVES the case
of values. Validation case-handling is itself asymmetric (see
:func:`validate_config` docstring).

Silent-drop surfaces (input edge cases that don't raise):

- ``limit=foo`` (non-int): the ``int(raw.strip())`` call is wrapped
  in :func:`contextlib.suppress(ValueError)`; the field stays
  ``None`` and the rest of the config still parses. By design --
  legacy URLs with malformed limits should still surface as much
  config as possible. Worth a follow-up to surface the drop as a
  ``validate_config`` warning.

Secret-handling note: ``TorrentioConfig.debrid_key`` carries the
debrid auth token in plain text (not :class:`pydantic.SecretStr`).
Callers logging the config dict OR the URL output of :func:`build_url`
will emit the token in their logs. Document the risk at any
:func:`build_url` call site that touches a logged surface.
"""

from __future__ import annotations

import contextlib
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from maestro.torrentio.enums import DEBRID_PROVIDERS, PROVIDERS, QUALITY_FILTERS, SORT_OPTIONS


class TorrentioConfig(BaseModel):
    """A Torrentio install-URL configuration; round-trippable with parse + build.

    Validation: ``extra="forbid"`` so callers passing wire-form keys
    (e.g., ``qualityfilter`` instead of model ``quality_filter``) get
    a loud :class:`pydantic.ValidationError` rather than a silent
    drop. The wire-vs-model name asymmetry (see module docstring) was
    a silent-data-loss surface before this guard.

    Snake-case Python model that mirrors the kebab-case wire format
    (see module docstring for the asymmetries). Field semantics:

    - ``providers``: subset of :data:`.enums.PROVIDERS` (validated
      case-insensitively but wire-emitted verbatim from the input).
    - ``sort``: one of :data:`.enums.SORT_OPTIONS` (validated
      case-sensitively, unlike ``providers``).
    - ``quality_filter``: subset of :data:`.enums.QUALITY_FILTERS`
      (validated case-insensitively). Items are EXCLUSION tags --
      release types to drop.
    - ``languages``: subset of :data:`.enums.LANGUAGES` (NOT currently
      validated; the LANGUAGES constant is defined for reference but
      :func:`validate_config` doesn't check membership).
    - ``limit``: integer cap on returned streams; silently dropped if
      the URL had a non-int value (see :func:`parse_url` docstring).
    - ``size_filter``: free-form expression evaluated upstream
      (e.g., ``<10gb``); not validated client-side.
    - ``debrid_provider``: one of :data:`.enums.DEBRID_PROVIDERS`
      (validated case-sensitively).
    - ``debrid_key``: the debrid auth token; **carries a secret in
      plain text** (no :class:`pydantic.SecretStr` wrapping). Callers
      logging the config OR the URL output of :func:`build_url` leak
      the token.
    - ``extra``: catch-all for unrecognized keys parsed from a URL.
      ``parse_url`` populates this with any ``key=value`` segment whose
      key isn't a known field name and isn't in
      :data:`.enums.DEBRID_PROVIDERS`. ``build_url`` round-trips these
      back into the URL.
    """

    model_config = ConfigDict(extra="forbid")

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
    """Parse a Torrentio install URL into a :class:`TorrentioConfig`.

    Decoding steps:

    1. Strip the scheme + host prefix via the ``https?://[^/]+/?`` regex.
       Inputs without an ``http://`` or ``https://`` scheme are left
       unchanged (so a path-only ``providers=yts/manifest.json`` parses
       too); other schemes (``ftp://`` etc.) are NOT stripped.
    2. Strip a trailing ``/manifest.json`` suffix and surrounding slashes.
    3. Iterate :data:`_KV_RE` matches over the remaining pipe-delimited
       segment. Each ``<key>=<value>`` pair is lowercased on key and
       dispatched to the matching :class:`TorrentioConfig` field.

    Key dispatch rules:

    - ``providers`` / ``qualityfilter`` / ``languages``: comma-split,
      empty items dropped. Per-item case PRESERVED (the wire format
      is case-sensitive on the upstream side; we don't normalize).
    - ``sort`` / ``sizefilter``: trimmed string assigned verbatim.
    - ``limit``: parsed via ``int(raw.strip())`` wrapped in
      :func:`contextlib.suppress(ValueError)` -- non-int values are
      SILENTLY DROPPED and the field stays ``None``. By design (legacy
      URLs with malformed limits should still surface as much config
      as possible); a future improvement could surface the drop as
      a warning through :func:`validate_config`.
    - Any key matching a :data:`.enums.DEBRID_PROVIDERS` entry
      (e.g., ``realdebrid``, ``alldebrid``): treated as the debrid
      pair -- sets both ``debrid_provider`` and ``debrid_key``. Note:
      if multiple debrid keys appear in the URL, the LAST one wins
      (overwrites previous).
    - Unknown keys: dumped into ``cfg.extra`` so the round-trip
      preserves them. ``build_url`` will re-emit them on output.

    The function does NOT raise on a malformed URL -- worst case
    returns an empty/default :class:`TorrentioConfig`. Validate
    afterwards with :func:`validate_config` to surface unknown
    providers / sort options / debrid providers.
    """
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
    """Build a Torrentio install URL from a :class:`TorrentioConfig`.

    Inverse of :func:`parse_url`; the round-trip
    ``build_url(parse_url(url))`` is field-preserving for all
    documented fields (providers, sort, quality_filter, languages,
    limit, size_filter, debrid_provider, debrid_key, extra).

    Field-emission order (fixed; produces deterministic URLs for
    snapshot testing):

    1. ``providers`` (comma-joined) if non-empty
    2. ``sort``
    3. ``qualityfilter`` (note: wire form, no underscore;
       comma-joined)
    4. ``languages`` (comma-joined)
    5. ``limit`` (as int literal)
    6. ``sizefilter`` (wire form, no underscore)
    7. Any ``cfg.extra`` items in dict-insertion order
    8. ``<debrid_provider>=<debrid_key>`` if both set

    Empty list / ``None`` fields are SKIPPED (no ``key=`` empty pair
    emitted), so ``build_url(TorrentioConfig())`` produces
    ``<base>/manifest.json`` with no config segment.

    ``base_url`` trailing slashes are stripped. The default
    ``https://torrentio.strem.fun`` matches the public Torrentio
    instance; private mirrors override via the ``base_url=`` kwarg.
    There is NO env-var driven override in v1
    (``MAESTRO_TORRENTIO_BASE_URL`` is not consumed) -- callers
    needing the override must pass it per-call.

    **Secret-leak surface**: the returned URL embeds
    ``cfg.debrid_key`` in plain text. Any logger / display surface
    that consumes the returned URL leaks the token. Callers must
    sanitize or avoid logging.
    """
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
    """Return human-readable validation errors against the enum constants.

    Empty list == valid. Each error string names the offending field
    + the rejected value + the valid set (full enum dump).

    Case-handling asymmetry (intentional but worth knowing):

    - ``providers`` and ``quality_filter`` items are lowercased before
      membership check against :data:`.enums.PROVIDERS` /
      :data:`.enums.QUALITY_FILTERS`. So ``"YTS"`` and ``"yts"``
      both validate as the same provider.
    - ``sort`` and ``debrid_provider`` are checked WITHOUT lowercasing.
      So ``"qualitysize"`` validates but ``"QualitySize"`` errors.

    This asymmetry mirrors the upstream Torrentio behavior:
    providers/quality_filter are case-folded by the addon, but sort
    and debrid keys are matched verbatim. The error messages do NOT
    flag the asymmetry, so callers misinterpreting a case-sensitive
    rejection may waste time -- worth surfacing in a future polish
    item.

    Fields NOT validated in v1:

    - ``languages``: :data:`.enums.LANGUAGES` exists but is unused
      here (and unused anywhere else in the codebase). Treated as
      free-form list. Dead-constant cleanup is a follow-up item.
    - ``limit`` / ``size_filter``: range / format not validated.
    - ``extra``: catch-all; never errors.

    Error message verbosity: provider / quality-filter errors include
    the FULL enum dump (24 providers, 19 quality filters). UX
    improvement candidate -- trim to a "did you mean?" suggestion or
    a link instead of the full list.
    """
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
    """Diagnostic dump of which enum constants are loaded.

    DEAD CODE in v1 -- nothing imports or calls this. Retained as a
    debugging hook for ``uv run python -c`` introspection, but
    candidate for removal. Pyright flags it as unused; the
    flag is documented and acknowledged rather than suppressed.
    """
    return {
        "providers": PROVIDERS,
        "quality_filters": QUALITY_FILTERS,
        "debrid_providers": DEBRID_PROVIDERS,
        "sort_options": SORT_OPTIONS,
    }
