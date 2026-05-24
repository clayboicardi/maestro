"""Torrentio URL config encode/decode tests."""

import pytest
from pydantic import SecretStr, ValidationError

from maestro.torrentio.encoder import (
    TorrentioConfig,
    build_url,
    parse_url,
    validate_config,
)


def test_parse_url_strips_query_string_before_kv_extraction() -> None:
    """M-3 regression: ?query and #fragment after /manifest.json must not contaminate fields.

    Pre-fix bug: a URL like '.../providers=yts/manifest.json?realdebrid=LEAKED'
    parsed as providers=['yts?realdebrid=LEAKED'] -- the query-string debrid
    token was swallowed into providers' value rather than landing in debrid_key,
    AND a downstream validate_config error would dump the leaked token in
    its message. Post-fix: query+fragment dropped before _KV_RE extraction.
    """
    url_with_query = (
        "https://torrentio.strem.fun/providers=yts/manifest.json?realdebrid=LEAKED"
    )
    cfg = parse_url(url_with_query)
    assert cfg.providers == ["yts"]
    assert cfg.debrid_key is None  # query-string token NOT mis-routed into debrid_key
    assert "LEAKED" not in (cfg.debrid_key or "")
    assert "LEAKED" not in str(cfg.providers)

    url_with_fragment = "https://torrentio.strem.fun/providers=yts/manifest.json#frag"
    cfg = parse_url(url_with_fragment)
    assert cfg.providers == ["yts"]  # no #frag contamination


def test_torrentio_config_rejects_wire_form_keys() -> None:
    """M-1 regression: extra='forbid' must reject wire-form keys silently dropped pre-fix.

    Pre-fix bug: TorrentioConfig had no extra='forbid', so a caller passing the
    wire-form 'qualityfilter' (instead of the model 'quality_filter') silently
    dropped the data with zero error. My validate_config docstring claimed
    Pydantic raises ValidationError on unknown fields; the claim was false.

    Post-fix: extra='forbid' produces ValidationError on the wire-form name.
    """
    with pytest.raises(ValidationError):
        TorrentioConfig.model_validate({"qualityfilter": ["cam"]})
    with pytest.raises(ValidationError):
        TorrentioConfig.model_validate({"sizefilter": "<10GB"})
    # Known model field stays valid
    cfg = TorrentioConfig.model_validate({"quality_filter": ["cam"]})
    assert cfg.quality_filter == ["cam"]


def test_parse_url_extracts_providers() -> None:
    url = (
        "https://torrentio.strem.fun/"
        "providers=yts,eztv,rarbg|sort=qualitysize|"
        "qualityfilter=cam,ts|realdebrid=ABC123/manifest.json"
    )
    cfg = parse_url(url)
    assert cfg.providers == ["yts", "eztv", "rarbg"]
    assert cfg.sort == "qualitysize"
    assert cfg.quality_filter == ["cam", "ts"]
    assert cfg.debrid_provider == "realdebrid"
    assert cfg.debrid_key is not None
    assert cfg.debrid_key.get_secret_value() == "ABC123"


def test_build_url_round_trips() -> None:
    cfg = TorrentioConfig(
        providers=["yts", "eztv"],
        sort="qualitysize",
        quality_filter=["cam"],
        debrid_provider="realdebrid",
        debrid_key=SecretStr("RD_TOKEN"),
    )
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    reparsed = parse_url(url)
    assert reparsed.providers == cfg.providers
    assert reparsed.debrid_key is not None
    assert reparsed.debrid_key.get_secret_value() == "RD_TOKEN"


def test_validate_config_rejects_unknown_provider() -> None:
    cfg = TorrentioConfig(providers=["yts", "made_up_provider"])
    errors = validate_config(cfg)
    assert any("made_up_provider" in e for e in errors)


def test_validate_config_accepts_clay_optimization_config() -> None:
    cfg = TorrentioConfig(
        providers=[
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
            "nekobt",
        ],
        sort="qualitysize",
        quality_filter=["3d", "480p", "scr", "cam"],
        debrid_provider="realdebrid",
        debrid_key=SecretStr("RD_TOKEN"),
    )
    errors = validate_config(cfg)
    assert errors == []


def test_parse_url_handles_minimal() -> None:
    url = "https://torrentio.strem.fun/manifest.json"
    cfg = parse_url(url)
    assert cfg.providers == []
    assert cfg.debrid_provider is None


def test_debrid_key_is_secretstr_masked_in_repr() -> None:
    """M-5 regression: debrid_key must be SecretStr-masked in repr/model_dump."""
    cfg = TorrentioConfig(
        debrid_provider="realdebrid",
        debrid_key=SecretStr("SECRET_TOKEN"),
    )
    assert "SECRET_TOKEN" not in repr(cfg)
    assert "SECRET_TOKEN" not in str(cfg.model_dump())
    # But the wire URL still embeds the real token (get_secret_value path).
    url = build_url(cfg)
    assert "SECRET_TOKEN" in url


def test_extra_field_secret_leak_surface_is_masked() -> None:
    """M-6 regression: extra-field values (unknown debrid providers) must also be SecretStr.

    A future debrid provider added upstream after the last DEBRID_PROVIDERS
    refresh lands in cfg.extra with the same token-carrying shape. Pre-fix:
    extra was dict[str, str] -- plain leak. Post-fix: dict[str, SecretStr].
    """
    url = "https://torrentio.strem.fun/newdebrid=NEW_TOKEN/manifest.json"
    cfg = parse_url(url)
    # newdebrid isn't in DEBRID_PROVIDERS so it lands in extra
    assert "newdebrid" in cfg.extra
    # The extra value is SecretStr-masked in repr
    assert "NEW_TOKEN" not in repr(cfg)
    # But round-trips back into the URL via .get_secret_value() at build time
    rebuilt = build_url(cfg)
    assert "newdebrid=NEW_TOKEN" in rebuilt


def test_language_wire_key_is_singular_per_upstream() -> None:
    """M-4 regression: wire key for language list must be singular per upstream.

    Pre-fix: maestro emitted/parsed `languages=` (plural) but upstream Torrentio
    addon uses `language=` (singular -- LanguageOptions.key='language' in
    upstream addon/lib/languages.js:51). Real Torrentio URLs with `language=`
    landed in cfg.extra; maestro-built URLs with `languages=` upstream ignored.
    Verified by curl'ing upstream languages.js + configuration.js.
    """
    # Round-trip: parse upstream-shaped URL, rebuild, must produce upstream-shaped URL
    url = "https://torrentio.strem.fun/providers=yts|language=english,french/manifest.json"
    cfg = parse_url(url)
    assert cfg.languages == ["english", "french"]  # parsed into the model field
    assert "language" not in cfg.extra  # NOT mis-routed to extra
    rebuilt = build_url(cfg)
    assert "language=english,french" in rebuilt  # singular wire key
    assert "languages=" not in rebuilt  # NOT emitting plural


def test_validate_config_lowercases_sort_and_debrid_to_mirror_upstream() -> None:
    """M-2 regression: validate_config must case-fold sort + debrid_provider per upstream.

    Pre-fix: validate_config rejected 'QualitySize' (sort) and 'RealDebrid' (debrid)
    despite upstream Torrentio accepting both via .toLowerCase() at consumption.
    Project-CC live-fetched upstream sort.js:48 to refute the pre-fix docstring
    claim that maestro 'mirrors upstream behavior.'
    """
    cfg = TorrentioConfig(sort="QualitySize", debrid_provider="RealDebrid")
    errors = validate_config(cfg)
    assert errors == [], f"unexpected errors: {errors}"


def test_validate_config_does_not_leak_debrid_token_via_error_message() -> None:
    """S-4 regression: validate_config error must not !r-dump the full debrid_provider value.

    A caller fat-fingering a debrid token into the debrid_provider field would
    have leaked the secret via the error message's !r formatting. Post-fix:
    first 8 chars + ellipsis only.
    """
    cfg = TorrentioConfig(debrid_provider="leaked_token_pretending_to_be_provider_name")
    errors = validate_config(cfg)
    assert len(errors) == 1
    # Long token-shaped value gets truncated; full value NOT in error
    assert "leaked_token_pretending" not in errors[0]
    assert "leaked_t..." in errors[0]


def test_build_url_omits_unset_keys() -> None:
    cfg = TorrentioConfig(providers=["yts"])
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    assert "providers=yts" in url
    assert "qualityfilter" not in url
    assert "realdebrid=" not in url
    assert url.endswith("/manifest.json")
