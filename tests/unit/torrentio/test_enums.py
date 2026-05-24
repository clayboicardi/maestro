"""Torrentio enum tests."""

from maestro.torrentio.enums import (
    DEBRID_PROVIDERS,
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
    """QUALITY_FILTERS post-Phase-3.5 refresh against upstream filter.js."""
    # Upstream keys verified via curl during the Phase 3.5 fix-PR refresh.
    expected = {"cam", "scr", "4k", "1080p", "720p", "480p", "other", "unknown"}
    missing = expected - set(QUALITY_FILTERS)
    assert not missing, f"missing upstream quality filters: {missing}"


def test_debrid_providers_includes_realdebrid() -> None:
    assert "realdebrid" in DEBRID_PROVIDERS


def test_sort_options_matches_upstream_four_keys() -> None:
    """SORT_OPTIONS post-Phase-3.5 refresh matches upstream sort.js:14-32 exactly."""
    # Upstream SortOptions has 4 keys: quality, qualitysize, seeders, size.
    # Pre-Phase-3.5 maestro had 6 keys with 3 fictional (qualityseeders,
    # sizequality, seedersquality) and missing the actual upstream 'quality'.
    assert set(SORT_OPTIONS) == {"quality", "qualitysize", "seeders", "size"}
