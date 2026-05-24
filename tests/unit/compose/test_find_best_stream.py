"""find_best_stream composer tests with mocked sub-domains."""

from unittest.mock import AsyncMock

import pytest

from maestro.compose.find_best_stream import find_best_stream
from maestro.errors import MaestroException, UpstreamError
from maestro.realdebrid.filter_gate import FilterGateLearner


@pytest.fixture
def learner() -> FilterGateLearner:
    return FilterGateLearner(state_path=None)


@pytest.mark.asyncio
async def test_returns_playable_url_on_happy_path(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value="tt12345")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "abc", "title": "S01E03.1080p.BluRay.mkv", "url": "https://restricted/x"},
        ]
    )
    rd_check_cache = AsyncMock(
        return_value={
            "abc": {"cached": True, "files": {}},
        }
    )
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="Return to Eden",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=["English"],
        exclude_quality=["CAM"],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://aiostreams.example",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    assert result.url == "https://rd.example/cdn/x.mkv"


@pytest.mark.asyncio
async def test_returns_failure_when_cinemeta_misses(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value=None)

    result = await find_best_stream(
        title="Made-up Title Nobody Has",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=AsyncMock(),
        rd_check_cache=AsyncMock(),
        rd_unrestrict=AsyncMock(),
        budget_s=60.0,
    )
    assert not result.ok
    assert result.suggestion is not None
    assert "imdb_id" in result.suggestion.lower()


@pytest.mark.asyncio
async def test_skips_filter_gate_risk_when_cached(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "S01E03.WEB-DL.AMZN.mkv", "url": "https://r/1"},
            {"infoHash": "h2", "title": "S01E03.BluRay.mkv", "url": "https://r/2"},
        ]
    )
    rd_check_cache = AsyncMock(
        return_value={
            "h1": {"cached": True, "files": {}},
            "h2": {"cached": True, "files": {}},
        }
    )
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    rd_unrestrict.assert_called_once_with("https://r/2")


@pytest.mark.asyncio
async def test_retries_next_candidate_on_unrestrict_failure(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value="tt9")
    # Both candidates use BluRay (not a KNOWN_KEYWORDS filter-gate term) so
    # the test exercises the retry-on-unrestrict-failure path, not the
    # filter-gate-block path. Differentiated by hash only.
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "S01E03.720p.BluRay.mkv", "url": "https://r/1"},
            {"infoHash": "h2", "title": "S01E03.1080p.BluRay.mkv", "url": "https://r/2"},
        ]
    )
    rd_check_cache = AsyncMock(
        return_value={
            "h1": {"cached": True},
            "h2": {"cached": True},
        }
    )

    call_count = 0

    async def unrestrict_side(url: str) -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise MaestroException(
                UpstreamError(domain="realdebrid", message="403 infringing_file")
            )
        return {"download": f"https://rd.example/cdn/{call_count}.mkv"}

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=AsyncMock(side_effect=unrestrict_side),
        budget_s=60.0,
    )
    assert result.ok
    assert len(result.attempts) == 2
    assert result.attempts[0].status == "unrestrict_403_infringing"
    assert result.attempts[1].status == "success"


@pytest.mark.asyncio
async def test_no_cached_streams_without_fallback_returns_failure(
    learner: FilterGateLearner,
) -> None:
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "x", "url": "https://r/1"},
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": False}})

    result = await find_best_stream(
        title="x",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=[],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=AsyncMock(),
        budget_s=60.0,
    )
    assert not result.ok
    assert result.suggestion is not None


@pytest.mark.asyncio
async def test_extract_filename_finds_filename_line_in_multiline_title(
    learner: FilterGateLearner,
) -> None:
    """Regression: multi-line AIOStreams titles put the real filename on line 2+.

    Line 0 is the human episode label (no release tags). The filename line
    (often prefixed with a folder emoji) carries WEB-DL/AMZN/etc that
    filter-gate cares about. The old _extract_filename took line 0 and silently
    returned LOW risk -- breaking filter-gate-aware sort. With the fix, line 2
    is selected (it contains .mkv), predict_risk sees "WEB-DL", returns HIGH,
    and require_cached + fallback_to_uncached=False produces a filter_gate_block
    Attempt instead of attempting unrestrict.
    """
    cinemeta_search = AsyncMock(return_value="tt9")
    multiline_title = (
        "S01E03 - Episode Name\n"
        "[FOLDER] Show.S01E03.1080p.WEB-DL.AMZN.mkv\n"
        "[SIZE] 8.2 GB\n"
        "[SEEDERS] 200 seeders"
    )
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": multiline_title, "url": "https://r/1"},
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": True, "files": {}}})
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=[],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert not result.ok
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "filter_gate_block"
    # The filename recorded on the Attempt should be the .mkv line, not line 0
    assert result.attempts[0].filename is not None
    assert ".mkv" in result.attempts[0].filename
    rd_unrestrict.assert_not_called()


@pytest.mark.asyncio
async def test_budget_exhaustion_returns_timeout_attempt(
    learner: FilterGateLearner,
) -> None:
    """budget_s=0.0 trips the in-loop timeout check on the first iteration."""
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "S01E03.1080p.BluRay.mkv", "url": "https://r/1"},
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": True}})
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=[],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=0.0,
    )
    assert not result.ok
    assert result.attempts[-1].status == "timeout"
    assert result.suggestion is not None
    rd_unrestrict.assert_not_called()


@pytest.mark.asyncio
async def test_cached_high_risk_filter_gate_blocks_when_no_fallback(
    learner: FilterGateLearner,
) -> None:
    """A single cached candidate flagged HIGH risk produces a filter_gate_block."""
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {
                "infoHash": "h1",
                "title": "Show.S01E03.1080p.WEB-DL.AMZN.mkv",
                "url": "https://r/1",
            },
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": True, "files": {}}})
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=[],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert not result.ok
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "filter_gate_block"
    rd_unrestrict.assert_not_called()


@pytest.mark.asyncio
async def test_no_url_attempt_when_stream_missing_url_field(
    learner: FilterGateLearner,
) -> None:
    """A cached candidate without a url field produces a no_url Attempt."""
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "S01E03.1080p.BluRay.mkv"},
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": True}})
    rd_unrestrict = AsyncMock()

    result = await find_best_stream(
        title="x",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=[],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert not result.ok
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "no_url"
    rd_unrestrict.assert_not_called()


@pytest.mark.asyncio
async def test_exclude_quality_filters_out_matching_streams(
    learner: FilterGateLearner,
) -> None:
    """exclude_quality=['CAM'] drops the CAM candidate before unrestrict."""
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "Show.2024.CAM.x264.mkv", "url": "https://r/cam"},
            {"infoHash": "h2", "title": "Show.2024.1080p.BluRay.mkv", "url": "https://r/bluray"},
        ]
    )
    rd_check_cache = AsyncMock(
        return_value={
            "h1": {"cached": True},
            "h2": {"cached": True},
        }
    )
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=[],
        exclude_quality=["CAM"],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    # Only the BluRay stream should have reached unrestrict; CAM was filtered.
    rd_unrestrict.assert_called_once_with("https://r/bluray")


@pytest.mark.asyncio
async def test_language_filter_no_longer_false_positives_on_english_words(
    learner: FilterGateLearner,
) -> None:
    """S-4 regression: titles with words containing former 3-letter LANG_TOKENS pass through.

    Pre-fix bug: _LANG_TOKENS contained 'fre'/'ita'/'rus'/'hin' which substring-matched
    English words like 'Free'/'Capital'/'Crusher'/'Shine'. Those streams got silently
    dropped despite being preferred-language candidates. Also dropped MULTI/Dual
    (audio-multiplicity markers that almost always include English).

    Post-fix: only full-word language names in _LANG_TOKENS.
    """
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "Show.Free.Lossless.1080p.mkv", "url": "https://r/1"},
            {"infoHash": "h2", "title": "Capital.Letter.Show.1080p.mkv", "url": "https://r/2"},
            {"infoHash": "h3", "title": "Show.MULTI.LANG.1080p.mkv", "url": "https://r/3"},
            {"infoHash": "h4", "title": "Show.Dual.Audio.1080p.mkv", "url": "https://r/4"},
        ]
    )
    rd_check_cache = AsyncMock(
        return_value={
            "h1": {"cached": True},
            "h2": {"cached": True},
            "h3": {"cached": True},
            "h4": {"cached": True},
        }
    )
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    # First candidate (Free Lossless) should reach unrestrict; others would too
    # but the composer returns on first success.
    rd_unrestrict.assert_called_once_with("https://r/1")


@pytest.mark.asyncio
async def test_language_filter_still_drops_explicit_foreign_tag(
    learner: FilterGateLearner,
) -> None:
    """S-4 regression: full-word language tokens like 'french' still drop foreign releases."""
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(
        return_value=[
            {"infoHash": "h1", "title": "Show.French.1080p.mkv", "url": "https://r/fr"},
            {"infoHash": "h2", "title": "Show.English.1080p.mkv", "url": "https://r/en"},
        ]
    )
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": True}, "h2": {"cached": True}})
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    # French stream dropped (full-word match); English stream attempted.
    rd_unrestrict.assert_called_once_with("https://r/en")
