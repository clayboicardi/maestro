"""Stremio tool tests -- 3 pure-compute + 2 IO."""

from __future__ import annotations

import httpx
import pytest
import respx

from maestro.stremio.tools import (
    StremioToolset,
    stremio_dedupe_streams,
    stremio_filter_streams,
    stremio_rank_streams,
)


def test_dedupe_by_infohash() -> None:
    """Streams sharing an infoHash collapse to one entry; the first survives."""
    streams = [
        {"infoHash": "abc", "title": "1"},
        {"infoHash": "abc", "title": "2"},
        {"infoHash": "def", "title": "3"},
    ]
    deduped = stremio_dedupe_streams(streams)
    assert len(deduped) == 2
    assert deduped[0]["title"] == "1"
    assert deduped[1]["infoHash"] == "def"


def test_filter_streams_by_language_keyword() -> None:
    """Case-insensitive substring match against title + name."""
    streams = [
        {"title": "S01E03 English", "infoHash": "a"},
        {"title": "S01E03 Russian", "infoHash": "b"},
    ]
    filtered = stremio_filter_streams(streams, preferred_languages=["English"])
    assert len(filtered) == 1
    assert filtered[0]["infoHash"] == "a"


def test_rank_streams_cached_first() -> None:
    """Cached streams sort before uncached when 'cached' leads the strategy."""
    streams = [
        {"title": "uncached", "infoHash": "a"},
        {"title": "cached", "infoHash": "b", "cached": True},
    ]
    ranked = stremio_rank_streams(streams, sort_strategy=["cached"])
    assert ranked[0]["infoHash"] == "b"


@respx.mock
@pytest.mark.asyncio
async def test_toolset_query_addon_wraps_client() -> None:
    """StremioToolset.query_addon delegates to StremioAddonClient.query_stream."""
    respx.get("https://addon.example/stream/series/tt1:1:3.json").mock(
        return_value=httpx.Response(200, json={"streams": [{"infoHash": "abc"}]})
    )

    toolset = StremioToolset(timeout_s=5.0)
    streams = await toolset.query_addon(
        addon_url="https://addon.example",
        content_type="series",
        imdb_id="tt1",
        season=1,
        episode=3,
    )
    assert streams[0]["infoHash"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_query_addons_parallel_fans_out() -> None:
    """Parallel fan-out across N addons returns {url: streams}."""
    respx.get("https://a.example/stream/movie/tt9.json").mock(
        return_value=httpx.Response(200, json={"streams": [{"infoHash": "h1"}]})
    )
    respx.get("https://b.example/stream/movie/tt9.json").mock(
        return_value=httpx.Response(200, json={"streams": [{"infoHash": "h2"}]})
    )

    toolset = StremioToolset(timeout_s=5.0)
    result = await toolset.query_addons_parallel(
        addon_urls=["https://a.example", "https://b.example"],
        content_type="movie",
        imdb_id="tt9",
    )
    flat = [s for addon_streams in result.values() for s in addon_streams]
    assert {"h1", "h2"} == {s["infoHash"] for s in flat}
