"""Torrentio enum tests."""

from maestro.torrentio.enums import (
    DEBRID_PROVIDERS,
    LANGUAGES,
    PROVIDERS,
    QUALITY_FILTERS,
    SORT_OPTIONS,
)


def test_providers_includes_known_english_set() -> None:
    """English-leaning providers per Clay's optimization-session config."""
    expected = {
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
    }
    actual = set(PROVIDERS)
    missing = expected - actual
    assert not missing, f"missing providers: {missing}"


def test_quality_filters_includes_low_quality_exclusions() -> None:
    expected = {"cam", "ts", "scr", "r5", "r6", "telesync"}
    intersect = expected & set(QUALITY_FILTERS)
    assert intersect, f"expected at least some of {expected} in {QUALITY_FILTERS}"


def test_debrid_providers_includes_realdebrid() -> None:
    assert "realdebrid" in DEBRID_PROVIDERS


def test_languages_includes_english() -> None:
    assert "english" in LANGUAGES


def test_sort_options_includes_quality_then_size() -> None:
    assert "qualitysize" in SORT_OPTIONS
