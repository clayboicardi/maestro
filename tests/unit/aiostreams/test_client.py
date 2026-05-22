"""AIOStreamsClient tests (respx-mocked)."""

import httpx
import pytest
import respx

from maestro.aiostreams.client import AIOStreamsClient
from maestro.errors import AuthError, InstanceError, MaestroException, UpstreamError


@pytest.fixture
def client() -> AIOStreamsClient:
    return AIOStreamsClient(
        base_url="https://aiostreams.elfhosted.com",
        uuid="user-uuid-1234",
        password="secret-pw",
        timeout_s=5.0,
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_config_happy_path(client: AIOStreamsClient) -> None:
    respx.get("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(200, json={"filters": {}, "addons": [], "services": []})
    )
    cfg = await client.get_config()
    assert "filters" in cfg
    assert "addons" in cfg


@respx.mock
@pytest.mark.asyncio
async def test_get_config_401_raises_auth_error(client: AIOStreamsClient) -> None:
    respx.get("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(401, json={"error": "unauthorized"})
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.get_config()
    assert isinstance(exc_info.value.error, AuthError)


@respx.mock
@pytest.mark.asyncio
async def test_get_config_404_raises_instance_error(client: AIOStreamsClient) -> None:
    respx.get("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(MaestroException) as exc_info:
        await client.get_config()
    assert isinstance(exc_info.value.error, InstanceError)


@respx.mock
@pytest.mark.asyncio
async def test_get_config_500_retries_then_raises(client: AIOStreamsClient) -> None:
    """5xx triggers retry (3 attempts) then surfaces UpstreamError."""
    route = respx.get("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(MaestroException) as exc_info:
        await client.get_config()
    assert isinstance(exc_info.value.error, UpstreamError)
    assert route.call_count == 3  # default retry_attempts


@respx.mock
@pytest.mark.asyncio
async def test_get_config_500_respects_custom_retry_attempts() -> None:
    """retry_attempts ctor arg controls actual attempt count."""
    custom_client = AIOStreamsClient(
        base_url="https://aiostreams.elfhosted.com",
        uuid="user-uuid-1234",
        password="secret-pw",
        timeout_s=5.0,
        retry_attempts=2,
    )
    route = respx.get("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(MaestroException):
        await custom_client.get_config()
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_put_config_round_trip(client: AIOStreamsClient) -> None:
    body = {"filters": {"preferred_languages": ["English"]}, "addons": []}
    respx.put("https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = await client.put_config(body)
    assert result == {"ok": True}
