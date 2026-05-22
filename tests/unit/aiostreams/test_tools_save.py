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
    """If never saved, return empty string (no fallback URL construction yet)."""
    url = await toolset_with_install_url.get_install_url()
    assert url == ""


@pytest.mark.asyncio
async def test_noop_save_does_not_overwrite_install_url(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    """A no-op save() must not clobber the URL captured by a prior real save."""
    await toolset_with_install_url.set_preferred_languages(["English"])
    await toolset_with_install_url.save()  # real save sets _last_install_url
    first_url = await toolset_with_install_url.get_install_url()
    assert first_url.startswith("stremio://")

    # Second save with nothing staged — must NOT touch _last_install_url
    await toolset_with_install_url.save()
    second_url = await toolset_with_install_url.get_install_url()
    assert second_url == first_url
