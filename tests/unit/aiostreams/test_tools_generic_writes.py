"""Generic write-tool tests."""

from typing import Any

import httpx
import pytest
import respx

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "filters": {},
        "sortCriteria": [],
        "misc": {},
        "presets": {"active": "Custom"},
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_set_filter_writes_under_filters_block(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_filter("min_size_gb", 2.5)
    assert mutation.field == "filters.min_size_gb"
    assert mutation.to == 2.5


@pytest.mark.asyncio
async def test_set_sort_order_replaces_criteria(toolset: AIOStreamsToolset) -> None:
    order = [
        {"key": "cached", "direction": "desc"},
        {"key": "resolution", "direction": "desc"},
    ]
    mutation = await toolset.set_sort_order(order)
    assert mutation.to == order


@pytest.mark.asyncio
async def test_set_misc_toggle_writes_under_misc(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_misc_toggle("show_statistics", value=True)
    assert mutation.field == "misc.show_statistics"
    assert mutation.to is True


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_overlays_remote_template(toolset: AIOStreamsToolset) -> None:
    template_url = (
        "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
        "main/templates/complete-sel-setup-v2.6.1.json"
    )
    template_body = {"filters": {"preferred_languages": ["English"]}}
    respx.get(template_url).mock(return_value=httpx.Response(200, json=template_body))

    mutation = await toolset.apply_template(
        template_name="Tamtaro Complete SEL Setup v2.6.1",
        mode="Debrid",
    )
    assert mutation.field == "presets.active"
    assert mutation.to == "Tamtaro Complete SEL Setup v2.6.1"


@pytest.mark.asyncio
async def test_apply_template_unknown_name_raises(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="not found"):
        await toolset.apply_template(
            template_name="DoesNotExist",
            mode="Debrid",
        )


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_handles_missing_presets_in_base() -> None:
    """setdefault on presets path works when base has no presets key."""
    template_url = (
        "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
        "main/templates/complete-sel-setup-v2.6.1.json"
    )
    respx.get(template_url).mock(return_value=httpx.Response(200, json={}))

    # Build a toolset with NO presets key in base
    state: dict[str, Any] = {"filters": {}, "sortCriteria": [], "misc": {}}

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    toolset = AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)
    mutation = await toolset.apply_template(
        template_name="Tamtaro Complete SEL Setup v2.6.1",
        mode="Debrid",
    )
    assert mutation.field == "presets.active"
    assert mutation.to == "Tamtaro Complete SEL Setup v2.6.1"
