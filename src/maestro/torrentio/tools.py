"""Torrentio MCP tool definitions -- five pure-compute tools listed below.

All five tools are deterministic functions over the Torrentio config
grammar -- no network, no in-memory state, no side effects. Wraps
:mod:`.encoder` and :mod:`.enums` so Claude can manipulate configs as
plain dicts without round-tripping through the :class:`.encoder.TorrentioConfig`
Pydantic model.

Per-tool annotation mapping is enumerated in
:func:`.register_tools` (see :mod:`maestro.torrentio` package
docstring); kept as per-tool callouts there rather than integer tally
here to avoid drift on future tool addition.

Tool contracts at a glance:

- ``torrentio_parse_url`` -- decode wire URL to config dict;
  best-effort (never raises, returns defaults on malformed input).
- ``torrentio_build_url`` -- encode config dict to wire URL;
  deterministic field-order output.
- ``torrentio_validate_config`` -- enumerate validation errors;
  empty list means valid.
- ``torrentio_list_providers`` / ``torrentio_list_quality_filters``
  -- snapshot the corresponding :mod:`.enums` constant.
"""

from __future__ import annotations

from typing import Any

from maestro.torrentio.encoder import (
    TorrentioConfig,
    build_url,
    parse_url,
    validate_config,
)
from maestro.torrentio.enums import PROVIDERS, QUALITY_FILTERS


def torrentio_parse_url(url: str) -> dict[str, Any]:
    """Decode a Torrentio install URL into its config dict.

    Wraps :func:`.encoder.parse_url` and returns the dict serialization
    of the :class:`.encoder.TorrentioConfig` model.

    Returned dict keys (snake_case model field names; see
    :class:`.encoder.TorrentioConfig` for per-field semantics):
    ``providers``, ``sort``, ``quality_filter``, ``languages``,
    ``limit``, ``size_filter``, ``debrid_provider``, ``debrid_key``,
    ``extra``.

    Wire-vs-dict naming asymmetries to remember:

    - Wire ``qualityfilter`` -> dict ``quality_filter``
    - Wire ``sizefilter`` -> dict ``size_filter``
    - Wire ``realdebrid=ABC`` -> dict ``debrid_provider="realdebrid"``
      + ``debrid_key="ABC"``

    Best-effort: never raises on a malformed URL; worst case returns
    a default config. Validate downstream with
    :func:`torrentio_validate_config` to surface unknown values.

    **Secret-leak surface**: returned dict's ``debrid_key`` field
    carries the plain-text debrid auth token if the URL had one.
    Callers logging the dict will leak the token. Sanitize via
    pop/redact before any log call.

    Reference: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/configuration.js
    """
    return parse_url(url).model_dump()


def torrentio_build_url(
    config: dict[str, Any],
    *,
    base_url: str = "https://torrentio.strem.fun",
) -> str:
    """Build a Torrentio install URL from a config dict.

    Wraps :func:`.encoder.build_url` after Pydantic-validating the
    input dict into a :class:`.encoder.TorrentioConfig` (raises
    :class:`pydantic.ValidationError` on unrecognized field names or
    type mismatches).

    Field-emission order is deterministic (providers / sort /
    qualityfilter / languages / limit / sizefilter / extra / debrid),
    so the same config dict always produces the same URL byte-for-byte
    -- useful for snapshot testing and config-equivalence checks.

    ``base_url`` defaults to the public Torrentio instance
    (``https://torrentio.strem.fun``); pass an alternate ``base_url``
    for private mirrors. There is no ``MAESTRO_TORRENTIO_BASE_URL``
    env-var fallback in v1.

    **Secret-leak surface**: the returned URL embeds
    ``config["debrid_key"]`` in plain text. Any logger / display
    surface consuming the URL leaks the token. Sanitize before
    logging.
    """
    cfg = TorrentioConfig.model_validate(config)
    return build_url(cfg, base_url=base_url)


def torrentio_validate_config(config: dict[str, Any]) -> list[str]:
    """Validate a Torrentio config dict against the known enum constants.

    Returns a list of human-readable error strings; empty list means
    the config validates. Wraps :func:`.encoder.validate_config`
    after Pydantic-validating the input dict.

    **Case-handling asymmetry** (mirrors the upstream Torrentio addon;
    intentional but worth knowing):

    - ``providers`` and ``quality_filter`` items are lowercased before
      membership check -- ``{"providers": ["YTS"]}`` validates.
    - ``sort`` and ``debrid_provider`` are matched verbatim --
      ``{"sort": "Qualitysize"}`` errors despite being a valid value.

    Fields NOT validated in v1 (callers should know):

    - ``languages``: pass-through, no membership check (the
      :data:`.enums.LANGUAGES` constant is unused).
    - ``limit`` / ``size_filter``: type-checked by Pydantic only.
    - ``extra``: catch-all, never errors.

    Pydantic-stage errors (unknown field names, type mismatches) raise
    :class:`pydantic.ValidationError` BEFORE this function's enum
    check runs; this function only sees configs that already passed
    schema validation.
    """
    cfg = TorrentioConfig.model_validate(config)
    return validate_config(cfg)


def torrentio_list_providers() -> list[str]:
    """Return a snapshot of all known torrent providers (lowercase strings).

    Returns a NEW list copy of :data:`.enums.PROVIDERS` (callers
    mutating the returned list won't affect the module constant).
    Refresh cadence: the constant is hand-maintained against the
    upstream Torrentio ``filter.js`` file; no automated drift check.
    """
    return list(PROVIDERS)


def torrentio_list_quality_filters() -> list[str]:
    """Return a snapshot of valid quality-filter tags for exclusion config.

    Returns a NEW list copy of :data:`.enums.QUALITY_FILTERS`. The
    tags are EXCLUSION markers (release types to DROP from results),
    so passing ``["cam", "ts"]`` filters out cam/telesync rips.
    Refresh cadence: same as :func:`torrentio_list_providers` --
    hand-maintained, no drift check.
    """
    return list(QUALITY_FILTERS)
