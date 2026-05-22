"""Live RD auth smoke test (opt-in via MAESTRO_SMOKE=1)."""

import os

import pytest

from maestro.config import MaestroSettings
from maestro.realdebrid.client import RDClient

pytestmark = pytest.mark.smoke


@pytest.mark.skipif(
    os.environ.get("MAESTRO_SMOKE") != "1",
    reason="MAESTRO_SMOKE=1 required",
)
@pytest.mark.asyncio
async def test_live_rd_user_info_returns_account() -> None:
    settings = MaestroSettings()
    client = RDClient(
        api_token=settings.rd_token.get_secret_value(),
        timeout_s=settings.http_timeout_s,
    )
    try:
        info = await client.get_user_info()
    finally:
        await client.aclose()
    assert "username" in info
