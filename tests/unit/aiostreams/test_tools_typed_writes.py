"""Typed write-tool tests (staged in memory, not yet persisted)."""

from typing import Any

import pytest

from maestro.aiostreams.schemas_generated import ExcludedResolution
from maestro.aiostreams.tools import _RESOLUTION_LADDER, AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "filters": {"preferred_languages": [], "excluded_resolutions": []},
        "core_engine": "Standard SEL - 3 per Q/R",
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        state.clear()
        state.update(body)
        return {"ok": True, "install_url": "stremio://x"}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_set_preferred_languages_stages_change(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_preferred_languages(["English"])
    assert mutation.field == "filters.preferred_languages"
    assert mutation.to == ["English"]


@pytest.mark.asyncio
async def test_set_cached_only_stages_boolean(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_cached_only(enabled=True)
    assert mutation.field == "filters.only_cached"
    assert mutation.to is True


@pytest.mark.asyncio
async def test_set_resolution_floor_excludes_below(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_resolution_floor("720p")
    assert mutation.field == "filters.excluded_resolutions"
    assert set(mutation.to) == {"144p", "240p", "360p", "480p", "576p"}
    assert "720p" not in mutation.to


@pytest.mark.asyncio
async def test_set_core_engine_accepts_valid_values(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_core_engine("Extended SEL - 6 per Q/R")
    assert mutation.field == "core_engine"
    assert mutation.to == "Extended SEL - 6 per Q/R"


@pytest.mark.asyncio
async def test_set_core_engine_rejects_invalid_value(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="engine must be one of"):
        await toolset.set_core_engine("Made-up Engine")


def test_resolution_ladder_is_subset_of_schema_enum() -> None:
    """Ladder values MUST be a subset of AIOStreams' ExcludedResolution enum.

    Catches schema-drift breakage when scripts/regen_aiostreams_schemas.sh
    pulls a newer upstream that changes the resolution vocabulary.
    """
    valid = {r.value for r in ExcludedResolution}
    assert set(_RESOLUTION_LADDER) <= valid, (
        f"ladder values not in schema enum: {set(_RESOLUTION_LADDER) - valid}"
    )
