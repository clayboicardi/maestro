"""Stremio addon client tests."""

import httpx
import pytest
import respx

from maestro.errors import AddonMalformed, AddonTimeout, MaestroException
from maestro.stremio.client import StremioAddonClient


@pytest.fixture
def client() -> StremioAddonClient:
    return StremioAddonClient(timeout_s=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_get_manifest_returns_addon_manifest(client: StremioAddonClient) -> None:
    respx.get("https://addon.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "addon", "version": "1.0.0", "name": "T"})
    )
    manifest = await client.get_manifest("https://addon.example/manifest.json")
    assert manifest["id"] == "addon"


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_returns_list(client: StremioAddonClient) -> None:
    respx.get("https://addon.example/stream/series/tt1234567:1:3.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "streams": [
                    {"name": "test", "title": "S01E03 1080p", "infoHash": "abc"},
                ]
            },
        )
    )

    streams = await client.query_stream(
        addon_url="https://addon.example",
        content_type="series",
        imdb_id="tt1234567",
        season=1,
        episode=3,
    )
    assert len(streams) == 1
    assert streams[0]["infoHash"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_timeout_raises_addon_timeout(client: StremioAddonClient) -> None:
    respx.get("https://addon.example/stream/movie/tt9999.json").mock(
        side_effect=httpx.TimeoutException("slow")
    )

    with pytest.raises(MaestroException) as exc_info:
        await client.query_stream(
            addon_url="https://addon.example",
            content_type="movie",
            imdb_id="tt9999",
        )
    assert isinstance(exc_info.value.error, AddonTimeout)
    assert exc_info.value.error.domain == "stremio"


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_malformed_json_raises(client: StremioAddonClient) -> None:
    respx.get("https://addon.example/stream/movie/tt9999.json").mock(
        return_value=httpx.Response(200, text="not json")
    )

    with pytest.raises(MaestroException) as exc_info:
        await client.query_stream(
            addon_url="https://addon.example",
            content_type="movie",
            imdb_id="tt9999",
        )
    assert isinstance(exc_info.value.error, AddonMalformed)
    assert exc_info.value.error.domain == "stremio"


@respx.mock
@pytest.mark.asyncio
async def test_cinemeta_search_resolves_title_to_imdb_id(client: StremioAddonClient) -> None:
    respx.get(
        "https://v3-cinemeta.strem.io/catalog/series/top/search=Return%20to%20Eden.json"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "metas": [
                    {"id": "tt12345", "name": "Return to Eden", "year": 1983},
                ]
            },
        )
    )

    imdb_id = await client.cinemeta_search(title="Return to Eden", content_type="series")
    assert imdb_id == "tt12345"


@respx.mock
@pytest.mark.asyncio
async def test_cinemeta_search_escapes_slash_in_title(client: StremioAddonClient) -> None:
    """S-1 regression: titles with '/' must be percent-encoded to %2F in the URL path.

    Pre-fix: quote(title) defaulted to safe='/', so 'Face/Off' generated the path
    '.../search=Face/Off.json' which Cinemeta would 404 (and worse, could be
    interpreted as a different path segment). Fix: quote(title, safe='').
    """
    respx.get("https://v3-cinemeta.strem.io/catalog/movie/top/search=Face%2FOff.json").mock(
        return_value=httpx.Response(200, json={"metas": [{"id": "tt0119094", "name": "Face/Off"}]})
    )
    imdb_id = await client.cinemeta_search(title="Face/Off", content_type="movie")
    assert imdb_id == "tt0119094"


@respx.mock
@pytest.mark.asyncio
async def test_cinemeta_search_returns_none_on_non_dict_root(client: StremioAddonClient) -> None:
    """M-1 regression: cinemeta_search must return None when JSON root is not a dict.

    Pre-fix bug: payload.get("metas") raised AttributeError when the response root
    was a list/string/number, breaking the "never raises" contract documented in
    the cinemeta_search docstring.
    """
    respx.get("https://v3-cinemeta.strem.io/catalog/series/top/search=Whatever.json").mock(
        return_value=httpx.Response(200, json=["not", "a", "dict"])
    )

    imdb_id = await client.cinemeta_search(title="Whatever", content_type="series")
    assert imdb_id is None  # must not raise


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_raises_on_non_dict_root(client: StremioAddonClient) -> None:
    """M-1 regression: query_stream raises documented MaestroException on non-dict JSON root.

    Pre-fix bug: payload.get("streams", []) raised uncaught AttributeError when the
    response root was a list. Now wrapped in the documented MaestroException(AddonMalformed)
    so MCP middleware translates correctly.
    """
    respx.get("https://addon.example/stream/movie/tt9999.json").mock(
        return_value=httpx.Response(200, json=["not", "a", "dict"])
    )

    with pytest.raises(MaestroException) as exc_info:
        await client.query_stream(
            addon_url="https://addon.example",
            content_type="movie",
            imdb_id="tt9999",
        )
    assert isinstance(exc_info.value.error, AddonMalformed)
    assert "root is not a dict" in exc_info.value.error.message
