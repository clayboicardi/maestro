"""Staged-write helper tests."""

from typing import Any

import pytest

from maestro.aiostreams.modify import ConfigStager, PendingMutation


@pytest.mark.asyncio
async def test_modify_stages_in_memory_not_remote() -> None:
    """A modify call does not PUT — it caches the transformed config."""
    fetches = 0

    async def fake_get_config() -> dict[str, Any]:
        nonlocal fetches
        fetches += 1
        return {"filters": {"preferred_languages": []}, "addons": []}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("PUT must not fire during modify")

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    mutation = await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )

    assert isinstance(mutation, PendingMutation)
    assert mutation.field == "filters.preferred_languages"
    assert mutation.to == ["English"]
    assert fetches == 1


@pytest.mark.asyncio
async def test_modify_caches_baseline_across_calls() -> None:
    """Multiple modifies stack on the same baseline fetch."""
    fetches = 0

    async def fake_get_config() -> dict[str, Any]:
        nonlocal fetches
        fetches += 1
        return {"filters": {"preferred_languages": [], "excluded_resolutions": []}}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )
    await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "excluded_resolutions": ["480p"]}},
        field="filters.excluded_resolutions",
    )

    assert fetches == 1
    pending = stager.pending_mutations()
    assert len(pending) == 2


@pytest.mark.asyncio
async def test_save_flushes_via_put_and_clears_staging() -> None:
    """save() calls PUT with the merged staged config then clears staging."""
    put_bodies: list[dict[str, Any]] = []

    async def fake_get_config() -> dict[str, Any]:
        return {"filters": {"preferred_languages": []}}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        put_bodies.append(body)
        return {"ok": True, "install_url": "stremio://x"}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    await stager.modify(
        lambda cfg: {**cfg, "filters": {"preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )
    result = await stager.save()

    assert len(put_bodies) == 1
    assert put_bodies[0]["filters"]["preferred_languages"] == ["English"]
    assert result["ok"] is True
    assert stager.pending_mutations() == []


@pytest.mark.asyncio
async def test_save_with_no_pending_is_noop() -> None:
    """Calling save() with nothing staged does not PUT."""
    put_bodies: list[dict[str, Any]] = []

    async def fake_get_config() -> dict[str, Any]:
        return {}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        put_bodies.append(body)
        return {}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    result = await stager.save()
    assert result == {"ok": True, "no_changes": True}
    assert put_bodies == []
