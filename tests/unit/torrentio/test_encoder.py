"""Torrentio URL config encode/decode tests."""

import pytest
from pydantic import ValidationError

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
    assert cfg.debrid_key == "ABC123"


def test_build_url_round_trips() -> None:
    cfg = TorrentioConfig(
        providers=["yts", "eztv"],
        sort="qualitysize",
        quality_filter=["cam"],
        debrid_provider="realdebrid",
        debrid_key="RD_TOKEN",
    )
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    reparsed = parse_url(url)
    assert reparsed.providers == cfg.providers
    assert reparsed.debrid_key == "RD_TOKEN"


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
        debrid_key="RD_TOKEN",
    )
    errors = validate_config(cfg)
    assert errors == []


def test_parse_url_handles_minimal() -> None:
    url = "https://torrentio.strem.fun/manifest.json"
    cfg = parse_url(url)
    assert cfg.providers == []
    assert cfg.debrid_provider is None


def test_build_url_omits_unset_keys() -> None:
    cfg = TorrentioConfig(providers=["yts"])
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    assert "providers=yts" in url
    assert "qualityfilter" not in url
    assert "realdebrid=" not in url
    assert url.endswith("/manifest.json")
