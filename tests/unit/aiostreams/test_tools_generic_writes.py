"""Generic write-tool tests."""

from copy import deepcopy
from typing import Any

import httpx
import pytest
import respx

from maestro.aiostreams.tools import AIOStreamsToolset

# Reused across apply_template tests (the single curated catalog entry).
_TEMPLATE_URL = (
    "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
    "main/templates/complete-sel-setup-v2.6.1.json"
)
_TEMPLATE_NAME = "Tamtaro Complete SEL Setup v2.6.1"
_MARKER = {"id": _TEMPLATE_NAME, "version": "2.6.1"}


def _toolset_for(state: dict[str, Any]) -> AIOStreamsToolset:
    async def fake_get_config() -> dict[str, Any]:
        return deepcopy(state)

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "filters": {},
        "sortCriteria": [],
        "misc": {},
        # presets is list[Preset3] per v2.29.6 (NOT a dict with .active).
        "presets": [],
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
    template_body = {"filters": {"preferred_languages": ["English"]}}
    respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json=template_body))

    mutation = await toolset.apply_template(template_name=_TEMPLATE_NAME, mode="Debrid")
    # Marker is recorded in the schema-valid appliedTemplates list, not presets.active.
    assert mutation.field == "appliedTemplates"
    assert _MARKER in mutation.to


@pytest.mark.asyncio
async def test_apply_template_unknown_name_raises(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="not found"):
        await toolset.apply_template(
            template_name="DoesNotExist",
            mode="Debrid",
        )


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_then_typed_write_stacks_cleanly(
    toolset: AIOStreamsToolset,
) -> None:
    """A typed write after apply_template preserves the template's overlay."""
    template_url = (
        "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
        "main/templates/complete-sel-setup-v2.6.1.json"
    )
    template_body = {
        "filters": {"preferred_languages": ["Spanish"], "custom_template_field": "kept"},
    }
    respx.get(template_url).mock(return_value=httpx.Response(200, json=template_body))

    # Step 1: apply template (sets preferred_languages=Spanish, adds custom field)
    await toolset.apply_template(
        template_name="Tamtaro Complete SEL Setup v2.6.1",
        mode="Debrid",
    )

    # Step 2: typed write that overrides preferred_languages back to English
    mutation = await toolset.set_preferred_languages(["English"])
    assert mutation.to == ["English"]

    # Both mutations are staged
    pending = toolset._stager.pending_mutations()
    assert len(pending) == 2
    assert pending[0].field == "appliedTemplates"
    assert pending[1].field == "filters.preferred_languages"
    assert pending[1].to == ["English"]


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_with_populated_presets_list_does_not_crash() -> None:
    """Regression: real v2.29.6 configs carry presets as a populated list[Preset3].

    The old ``presets.active`` write raised ``TypeError`` ('list indices must be
    integers') on this shape. The marker now goes to ``appliedTemplates`` and the
    presets list is left untouched.
    """
    respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json={}))
    presets = [{"type": "torrentio", "instanceId": "t1", "enabled": True, "options": {}}]
    toolset = _toolset_for({"filters": {}, "sortCriteria": [], "presets": deepcopy(presets)})

    mutation = await toolset.apply_template(template_name=_TEMPLATE_NAME, mode="Debrid")

    assert mutation.field == "appliedTemplates"
    assert _MARKER in mutation.to
    # The presets list is not the marker's home and is left as-is.
    assert toolset._stager._staged is not None
    assert toolset._stager._staged["presets"] == presets


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_handles_null_applied_templates() -> None:
    """appliedTemplates: None (valid per schema) is replaced with a list, not appended to."""
    respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json={}))
    toolset = _toolset_for({"filters": {}, "appliedTemplates": None})

    mutation = await toolset.apply_template(template_name=_TEMPLATE_NAME, mode="Debrid")

    assert mutation.field == "appliedTemplates"
    assert mutation.to == [_MARKER]


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_dedupes_and_preserves_foreign_entries() -> None:
    """Re-applying de-dupes by id (move-to-end); AIOStreams' own entries are preserved."""
    respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json={}))
    foreign = {"id": "aiostreams-native", "version": "1.0"}
    toolset = _toolset_for(
        {
            "filters": {},
            "presets": [],
            "appliedTemplates": [foreign, deepcopy(_MARKER)],
        }
    )

    mutation = await toolset.apply_template(template_name=_TEMPLATE_NAME, mode="Debrid")

    # Foreign entry preserved; the maestro entry is de-duped and moved to most-recent.
    assert mutation.to == [foreign, _MARKER]


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_then_save_makes_get_active_template_reflect_it() -> None:
    """End-to-end: apply -> save (PUT persists) -> get_active_template reads the marker back."""
    respx.get(_TEMPLATE_URL).mock(return_value=httpx.Response(200, json={}))
    backend: dict[str, Any] = {"filters": {}, "presets": []}

    async def fake_get_config() -> dict[str, Any]:
        return deepcopy(backend)

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        backend.clear()
        backend.update(deepcopy(body))
        return {"install_url": "https://stremio.example/manifest.json"}

    toolset = AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)
    await toolset.apply_template(template_name=_TEMPLATE_NAME, mode="Debrid")
    await toolset.save()

    assert await toolset.get_active_template() == _TEMPLATE_NAME
