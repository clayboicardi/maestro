"""Save + install-URL tool tests."""

from typing import Any

import pytest

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset_with_install_url() -> AIOStreamsToolset:
    state: dict[str, Any] = {"filters": {"preferred_languages": []}}

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "install_url": "stremio://aiostreams.elfhosted.com/abcdef/manifest.json",
        }

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_save_flushes_staged_writes(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    await toolset_with_install_url.set_preferred_languages(["English"])
    result = await toolset_with_install_url.save()
    assert result["ok"] is True
    assert "install_url" in result
    assert "filters.preferred_languages" in result["changes_applied"]


@pytest.mark.asyncio
async def test_save_with_nothing_staged_is_noop(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    result = await toolset_with_install_url.save()
    assert result["no_changes"] is True


@pytest.mark.asyncio
async def test_get_install_url_from_last_save(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    await toolset_with_install_url.set_preferred_languages(["English"])
    await toolset_with_install_url.save()
    url = await toolset_with_install_url.get_install_url()
    assert url.startswith("stremio://")


@pytest.mark.asyncio
async def test_get_install_url_without_save_uses_fallback(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    """If never saved, fall back to constructing from instance + UUID."""
    url = await toolset_with_install_url.get_install_url()
    assert url == ""
