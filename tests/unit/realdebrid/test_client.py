"""Real-Debrid client tests (respx-mocked)."""

import httpx
import pytest
import respx

from maestro.errors import AuthError, MaestroException, RateLimitError, UpstreamError
from maestro.realdebrid.client import RDClient


@pytest.fixture
def client() -> RDClient:
    return RDClient(api_token="test_token_abc", timeout_s=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_happy_path(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(200, json={"id": 42, "username": "clay", "type": "premium"})
    )
    info = await client.get_user_info()
    assert info["username"] == "clay"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_401_raises_auth_error(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(return_value=httpx.Response(401))
    with pytest.raises(MaestroException) as exc_info:
        await client.get_user_info()
    assert isinstance(exc_info.value.error, AuthError)
    assert exc_info.value.error.domain == "realdebrid"


@respx.mock
@pytest.mark.asyncio
async def test_check_cache_batch_returns_map(client: RDClient) -> None:
    hashes = ["abc123", "def456", "789xyz"]
    payload = {
        "abc123": {"rd": [{"1": {"filename": "f.mkv"}}]},
        "def456": {"rd": [{"2": {"filename": "g.mkv"}}]},
        "789xyz": [],
    }
    respx.get(
        "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/abc123/def456/789xyz"
    ).mock(return_value=httpx.Response(200, json=payload))

    result = await client.check_cache(hashes)
    assert result["abc123"]["cached"] is True
    assert result["def456"]["cached"] is True
    assert result["789xyz"]["cached"] is False


@respx.mock
@pytest.mark.asyncio
async def test_unrestrict_link_returns_playable_url(client: RDClient) -> None:
    respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(
            200, json={"download": "https://rd.example/cdn/abc.mkv", "filename": "abc.mkv"}
        )
    )
    result = await client.unrestrict_link("https://restricted.rd/x")
    assert result["download"] == "https://rd.example/cdn/abc.mkv"


@respx.mock
@pytest.mark.asyncio
async def test_unrestrict_403_with_infringing_file_returns_structured(
    client: RDClient,
) -> None:
    respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(403, json={"error": "infringing_file", "error_code": 35})
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.unrestrict_link("https://restricted.rd/x")
    assert isinstance(exc_info.value.error, UpstreamError)
    assert exc_info.value.error.code == "upstream_error"
    assert "infringing_file" in exc_info.value.error.message.lower()


@respx.mock
@pytest.mark.asyncio
async def test_4xx_body_excerpt_redacts_bearer_token(client: RDClient) -> None:
    """A 4xx body that echoes the bearer token is scrubbed at the client layer.

    The body excerpt is embedded in the UpstreamError message, which flows
    through MCP exception logging -- redact-at-source so every RD tool inherits
    it. (client fixture token is "test_token_abc".)
    """
    respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(400, text="bad request near token=test_token_abc here")
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.unrestrict_link("https://restricted.rd/x")
    msg = exc_info.value.error.message
    assert "test_token_abc" not in msg
    assert "***REDACTED***" in msg


@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_429_raises_rate_limit_error(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(
            429, json={"error": "rate_limit"}, headers={"Retry-After": "30"}
        )
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.get_user_info()
    assert isinstance(exc_info.value.error, RateLimitError)
    assert exc_info.value.error.retry_after_s == 30.0


@respx.mock
@pytest.mark.asyncio
async def test_add_magnet_sends_form_data(client: RDClient) -> None:
    route = respx.post("https://api.real-debrid.com/rest/1.0/torrents/addMagnet").mock(
        return_value=httpx.Response(200, json={"id": "abc", "uri": "magnet:?xt=urn:btih:DEADBEEF"})
    )
    result = await client.add_magnet("magnet:?xt=urn:btih:DEADBEEF")
    assert result["id"] == "abc"
    # Verify form-encoded body carries the magnet param.
    assert route.calls.last.request.content == b"magnet=magnet%3A%3Fxt%3Durn%3Abtih%3ADEADBEEF"


@respx.mock
@pytest.mark.asyncio
async def test_get_torrent_status_returns_info(client: RDClient) -> None:
    payload = {
        "id": "abc",
        "filename": "movie.mkv",
        "status": "downloaded",
        "progress": 100,
        "files": [{"id": 1, "path": "/movie.mkv", "selected": 1}],
    }
    respx.get("https://api.real-debrid.com/rest/1.0/torrents/info/abc").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await client.get_torrent_status("abc")
    assert result["status"] == "downloaded"
    assert result["files"][0]["path"] == "/movie.mkv"


@respx.mock
@pytest.mark.asyncio
async def test_get_library_returns_list(client: RDClient) -> None:
    payload = [
        {"id": "abc", "filename": "a.mkv", "status": "downloaded"},
        {"id": "def", "filename": "b.mkv", "status": "downloading"},
    ]
    respx.get("https://api.real-debrid.com/rest/1.0/torrents").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await client.get_library()
    assert len(result) == 2
    assert result[0]["id"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_4xx_does_not_retry(client: RDClient) -> None:
    """Regression guard: 4xx (non-401/429) must NOT trigger the retry loop.

    A 404 on /unrestrict/link is non-transient (UpstreamError with
    is_transient=False). The retry predicate must honor that field.
    """
    route = respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(404, json={"error": "not_found", "error_code": 7})
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.unrestrict_link("https://restricted.rd/missing")
    assert isinstance(exc_info.value.error, UpstreamError)
    assert exc_info.value.error.is_transient is False
    assert route.call_count == 1
