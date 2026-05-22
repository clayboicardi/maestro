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
