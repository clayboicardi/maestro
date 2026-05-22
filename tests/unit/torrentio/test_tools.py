"""Torrentio tool tests."""

from maestro.torrentio.tools import (
    torrentio_build_url,
    torrentio_list_providers,
    torrentio_list_quality_filters,
    torrentio_parse_url,
    torrentio_validate_config,
)


def test_torrentio_list_providers_returns_string_list() -> None:
    providers = torrentio_list_providers()
    assert isinstance(providers, list)
    assert "yts" in providers


def test_torrentio_list_quality_filters_returns_string_list() -> None:
    qfs = torrentio_list_quality_filters()
    assert "cam" in qfs


def test_torrentio_parse_url_returns_config_dict() -> None:
    url = "https://torrentio.strem.fun/providers=yts|sort=qualitysize/manifest.json"
    cfg = torrentio_parse_url(url)
    assert cfg["providers"] == ["yts"]
    assert cfg["sort"] == "qualitysize"


def test_torrentio_build_url_returns_string() -> None:
    cfg_dict = {"providers": ["yts", "eztv"]}
    url = torrentio_build_url(cfg_dict)
    assert "providers=yts,eztv" in url


def test_torrentio_validate_config_returns_errors_list() -> None:
    errors = torrentio_validate_config({"providers": ["yts", "bogus"]})
    assert any("bogus" in e for e in errors)


def test_torrentio_validate_config_clean_returns_empty_list() -> None:
    errors = torrentio_validate_config({"providers": ["yts"], "sort": "qualitysize"})
    assert errors == []
