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

Wire-vs-model naming asymmetries (the model uses Pythonic snake_case
+ plural lists; the wire format uses upstream's lower/singular keys):

- Wire ``qualityfilter`` <-> model ``quality_filter``
- Wire ``sizefilter`` <-> model ``size_filter``
- Wire ``language`` (singular per upstream ``languages.js:51``
  ``LanguageOptions.key``) <-> model ``languages`` (plural list)
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

Secret-handling: ``TorrentioConfig.debrid_key`` is
:class:`pydantic.SecretStr`-wrapped, so ``repr(cfg)`` and
``cfg.model_dump()`` mask the token as ``SecretStr('**********')``.
The plain-text value only surfaces at the wire-format boundary inside
:func:`build_url` via an explicit ``.get_secret_value()`` call --
callers must avoid logging the build_url RETURN value if logs are
secret-sensitive (the URL string itself isn't masked).

Equivalent ``extra`` masking: ``TorrentioConfig.extra`` values are
also :class:`pydantic.SecretStr`-wrapped. A debrid provider added
upstream AFTER the last :data:`.enums.DEBRID_PROVIDERS` refresh lands
in ``extra`` (not ``debrid_key``), but the masking still applies --
so a stale enum can't silently re-introduce a plain-text leak via
the unknown-key path.
"""

from __future__ import annotations

import contextlib
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr

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
      case-insensitively post-Phase-3.5 to mirror upstream sort.js).
    - ``quality_filter``: subset of :data:`.enums.QUALITY_FILTERS`
      (validated case-insensitively). Items are EXCLUSION tags --
      release types to drop.
    - ``languages``: list of upstream Torrentio language tokens
      (e.g., ``["english", "french"]``); NOT validated client-side
      against any enum constant (the upstream ``languages.js``
      mapping is open-ended). Pythonic plural here; the WIRE form
      is singular ``language=`` per upstream.
    - ``limit``: integer cap on returned streams; silently dropped if
      the URL had a non-int value (see :func:`parse_url` docstring).
    - ``size_filter``: free-form expression evaluated upstream.
      Upstream uppercases the value via ``filter.js`` before
      ``parseSize``, so pass uppercase units (e.g., ``<10GB`` --
      lowercase ``<10gb`` parses as NaN and filters out ALL streams).
      Not validated client-side.
    - ``debrid_provider``: one of :data:`.enums.DEBRID_PROVIDERS`
      (validated case-sensitively).
    - ``debrid_key``: the debrid auth token wrapped in
      :class:`pydantic.SecretStr` so ``repr(cfg)`` /
      ``cfg.model_dump()`` mask it. Unwrap via
      ``cfg.debrid_key.get_secret_value()`` at the wire-format
      boundary (already handled internally by :func:`build_url`).
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
    debrid_key: SecretStr | None = None
    extra: dict[str, SecretStr] = Field(default_factory=dict)


# Anchored to match only at start-of-string OR after a pipe/slash boundary
# (the wire-format key separators). Pre-anchor regex matched anywhere, which
# silently truncated keys with non-alphanumeric prefixes -- e.g.,
# `key-with-dash=value` produced `('dash', 'value')` rather than no match.
_KV_RE = re.compile(r"(?:^|[|/])([a-zA-Z_][a-zA-Z0-9_]*)=([^|/]+)")

# Max chars of a rejected debrid_provider value to show in error messages
# before truncating with an ellipsis -- defends against fat-fingered
# token-in-wrong-field secret leaks via the !r format.
_PREVIEW_CHAR_LIMIT = 8


def parse_url(url: str) -> TorrentioConfig:
    """Parse a Torrentio install URL into a :class:`TorrentioConfig`.

    Decoding steps:

    1. Strip the LEADING scheme + host prefix via the anchored
       ``^https?://[^/]+/?`` regex. Inputs without an ``http://`` or
       ``https://`` scheme are left unchanged (so a path-only
       ``providers=yts/manifest.json`` parses too). Non-http schemes
       (``ftp://``, ``data:``, etc.) are NOT stripped, but the
       downstream :data:`_KV_RE` is anchored to pipe/slash boundaries
       so the host segment of a non-http URL doesn't produce
       spurious kv matches.
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
    # Anchored `^` so we strip only the LEADING scheme+host prefix, not any
    # occurrence of `https?://` later in the string (pre-fix re.sub matched
    # globally and could mangle inputs with embedded URLs).
    base_strip = re.sub(r"^https?://[^/]+/?", "", url).strip("/")
    # Drop query string + fragment BEFORE kv-extraction so a URL like
    # .../providers=yts/manifest.json?realdebrid=LEAKED doesn't swallow the
    # query-string token into providers' value (security: validation error
    # would dump the leaked token; corruption: token lands in wrong field).
    base_strip = base_strip.split("?", 1)[0].split("#", 1)[0]
    # removesuffix (Python 3.9+) is anchored to the END -- pre-fix `.replace`
    # was global and would corrupt a debrid_key containing the literal
    # `/manifest.json` substring.
    base_strip = base_strip.removesuffix("/manifest.json").rstrip("/")

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
        elif key == "language":
            # Wire key is SINGULAR (upstream languages.js:51 `LanguageOptions.key`
            # is 'language'). Model field stays plural per Pythonic snake_case.
            # Pre-fix module matched key=='languages' which NEVER fires against
            # real Torrentio URLs -- real `language=english` URLs landed in
            # cfg.extra and rebuilt as `languages=...` URLs upstream ignored.
            cfg.languages = [lang.strip() for lang in raw.split(",") if lang.strip()]
        elif key == "limit":
            with contextlib.suppress(ValueError):
                cfg.limit = int(raw.strip())
        elif key == "sizefilter":
            cfg.size_filter = raw.strip()
        elif key in DEBRID_PROVIDERS:
            cfg.debrid_provider = key
            # SecretStr wraps the token so repr/model_dump masks it.
            cfg.debrid_key = SecretStr(raw.strip())
        else:
            # Wrap extra values in SecretStr too -- a debrid provider added
            # upstream AFTER the last DEBRID_PROVIDERS refresh lands here,
            # carrying a token, with the same leak surface debrid_key has.
            cfg.extra[key] = SecretStr(raw.strip())
    return cfg


def build_url(cfg: TorrentioConfig, *, base_url: str = "https://torrentio.strem.fun") -> str:
    """Build a Torrentio install URL from a :class:`TorrentioConfig`.

    Inverse of :func:`parse_url`; the round-trip
    ``build_url(parse_url(url))`` is field-preserving for all
    documented fields (providers, sort, quality_filter, languages,
    limit, size_filter, debrid_provider, debrid_key, extra) **EXCEPT**
    in two cases:

    1. ``limit=`` segments with non-int values are silently dropped at
       parse time (see :func:`parse_url` docstring) and therefore
       LOST on round-trip. The rebuilt URL omits the segment.
    2. ``extra`` keys that collide with the wire form of a recognized
       field (``providers``, ``sort``, ``qualityfilter``, ``language``,
       ``limit``, ``sizefilter``, or any
       :data:`.enums.DEBRID_PROVIDERS` member) cause this function to
       emit duplicate ``key=`` segments. On re-parse, the last
       occurrence wins, silently overwriting the typed field's value.
       Callers populating ``extra`` directly (vs. via :func:`parse_url`)
       should avoid these key names.

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
    ``cfg.debrid_key`` in plain text (via the explicit
    ``.get_secret_value()`` call required for wire-format
    serialization). The model itself masks ``debrid_key`` in repr /
    model_dump, but the URL output cannot -- Torrentio addons need
    the literal token in the path. Callers logging the returned URL
    leak the token; sanitize via :func:`urllib.parse.urlparse` +
    drop the path before logging, OR avoid logging the URL entirely.
    """
    parts: list[str] = []
    if cfg.providers:
        parts.append(f"providers={','.join(cfg.providers)}")
    if cfg.sort:
        parts.append(f"sort={cfg.sort}")
    if cfg.quality_filter:
        parts.append(f"qualityfilter={','.join(cfg.quality_filter)}")
    if cfg.languages:
        # Wire key is SINGULAR per upstream languages.js:51 -- emit `language=`
        # not `languages=` so Torrentio actually consumes the list.
        parts.append(f"language={','.join(cfg.languages)}")
    if cfg.limit is not None:
        parts.append(f"limit={cfg.limit}")
    if cfg.size_filter:
        parts.append(f"sizefilter={cfg.size_filter}")
    for k, v in cfg.extra.items():
        # Extras are SecretStr -- unwrap once at the wire-format boundary.
        parts.append(f"{k}={v.get_secret_value()}")
    if cfg.debrid_provider and cfg.debrid_key:
        # Same wire-format boundary unwrap for the typed debrid token.
        parts.append(f"{cfg.debrid_provider}={cfg.debrid_key.get_secret_value()}")

    base = base_url.rstrip("/")
    if not parts:
        return f"{base}/manifest.json"
    return f"{base}/{('|').join(parts)}/manifest.json"


def validate_config(cfg: TorrentioConfig) -> list[str]:
    """Return human-readable validation errors against the enum constants.

    Empty list == valid. Each error string names the offending field
    + the rejected value + the valid set (full enum dump).

    Case-handling: all field values are lowercased before membership
    check against the enum constants. This mirrors upstream Torrentio
    behavior -- ``configuration.js:43`` lowercases parameter keys at
    parse time, and ``sort.js:48`` lowercases the sort value at
    consumption. So ``{"sort": "QualitySize"}``,
    ``{"providers": ["YTS"]}``, and ``{"debrid_provider": "RealDebrid"}``
    all validate. The same applies to ``quality_filter``.

    Fields NOT validated in v1:

    - ``languages``: :data:`.enums.LANGUAGES` exists but is unused
      here (and unused anywhere else in the codebase). Treated as
      free-form list. Dead-constant cleanup is a follow-up item.
    - ``limit`` / ``size_filter``: range / format not validated.
    - ``extra``: catch-all; never errors.

    Error message verbosity (asymmetric across fields):

    - ``providers`` and ``sort`` errors include the FULL enum dump
      (24 / 4 items respectively) for self-discovery.
    - ``quality_filter`` errors are bare (just the rejected value).
      Callers can enumerate valid values via
      :func:`torrentio_list_quality_filters`.
    - ``debrid_provider`` errors include the enum dump (8 items)
      AND truncate the rejected value to first 8 chars + ellipsis
      to avoid leaking a fat-fingered token (see :class:`SecretStr`
      note above).

    UX improvement candidate: trim the providers + sort dumps to
    "did you mean?" suggestions (use ``difflib.get_close_matches``)
    rather than the full list, OR consolidate via the discovery
    tools (``torrentio_list_*``). Out of scope for this docstring
    pass.
    """
    errors: list[str] = []

    for p in cfg.providers:
        if p.lower() not in PROVIDERS:
            errors.append(f"unknown provider: {p!r} (valid: {PROVIDERS})")

    for q in cfg.quality_filter:
        if q.lower() not in QUALITY_FILTERS:
            errors.append(f"unknown quality_filter: {q!r}")

    # Lowercase sort + debrid_provider before membership check to mirror
    # upstream Torrentio behavior (configuration.js:43 lowercases all keys;
    # sort.js:48 lowercases the sort value at consumption). Pre-fix maestro
    # rejected 'QualitySize' which upstream would accept.
    if cfg.sort and cfg.sort.lower() not in SORT_OPTIONS:
        errors.append(f"unknown sort: {cfg.sort!r} (valid: {SORT_OPTIONS})")

    if cfg.debrid_provider and cfg.debrid_provider.lower() not in DEBRID_PROVIDERS:
        # Truncate the rejected value -- a caller might have fat-fingered a
        # debrid token into this field instead of debrid_key, and !r-dumping
        # the full value into a log line would leak the secret.
        preview = cfg.debrid_provider[:_PREVIEW_CHAR_LIMIT]
        if len(cfg.debrid_provider) > _PREVIEW_CHAR_LIMIT:
            preview = preview + "..."
        errors.append(f"unknown debrid_provider: {preview!r} (valid: {DEBRID_PROVIDERS})")

    return errors
