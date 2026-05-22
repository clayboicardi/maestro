"""Addon management tool tests."""

from typing import Any

import pytest

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "addons": [
            {"name": "Comet", "enabled": True, "manifestUrl": "https://comet.example/m.json"},
            {"name": "MediaFusion", "enabled": True, "manifestUrl": "https://mf.example/m.json"},
        ],
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_add_addon_appends_to_list(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.add_addon(addon_url="https://peerflix.example/manifest.json")
    assert mutation.field == "addons"
    assert len(mutation.to) == 3
    assert mutation.to[-1]["manifestUrl"] == "https://peerflix.example/manifest.json"


@pytest.mark.asyncio
async def test_add_addon_at_position(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.add_addon(
        addon_url="https://peerflix.example/manifest.json",
        position=0,
    )
    assert mutation.to[0]["manifestUrl"] == "https://peerflix.example/manifest.json"


@pytest.mark.asyncio
async def test_remove_addon_by_name(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.remove_addon("Comet")
    names = [a["name"] for a in mutation.to]
    assert "Comet" not in names
    assert "MediaFusion" in names


@pytest.mark.asyncio
async def test_remove_addon_unknown_raises(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="not found"):
        await toolset.remove_addon("NonexistentAddon")


@pytest.mark.asyncio
async def test_toggle_addon_flips_enabled(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.toggle_addon("Comet", enabled=False)
    target = next(a for a in mutation.to if a["name"] == "Comet")
    assert target["enabled"] is False


@pytest.mark.asyncio
async def test_toggle_addon_unknown_raises(toolset: AIOStreamsToolset) -> None:
    """Symmetry with remove: toggle on a missing addon also raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await toolset.toggle_addon("NonexistentAddon", enabled=False)
