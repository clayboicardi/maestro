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
