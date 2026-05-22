"""Template fetcher tests (respx-mocked GitHub raw URLs)."""

import httpx
import pytest
import respx

from maestro.aiostreams.templates import (
    KNOWN_TEMPLATES,
    fetch_template,
    list_templates,
    merge_template_into_config,
)


def test_known_templates_includes_tamtaro_recommended() -> None:
    names = [t["name"] for t in KNOWN_TEMPLATES]
    assert "Tamtaro Complete SEL Setup v2.6.1" in names


def test_list_templates_returns_known_set() -> None:
    templates = list_templates()
    assert len(templates) >= 1
    for t in templates:
        assert "name" in t
        assert "source_url" in t
        assert "description" in t


@respx.mock
@pytest.mark.asyncio
async def test_fetch_template_pulls_json_from_url() -> None:
    payload = {"filters": {"preferred_languages": ["English"]}, "addons": []}
    respx.get("https://example.com/template.json").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await fetch_template("https://example.com/template.json")
    assert result == payload


def test_merge_template_overlays_template_keys_on_config() -> None:
    base = {
        "filters": {"preferred_languages": [], "other": "keep"},
        "addons": [{"name": "Existing"}],
        "untouched": "value",
    }
    template = {
        "filters": {"preferred_languages": ["English"]},
        "addons": [{"name": "New"}],
    }
    merged = merge_template_into_config(base, template, mode="Debrid")

    assert merged["filters"]["preferred_languages"] == ["English"]
    assert merged["filters"]["other"] == "keep"
    assert merged["addons"] == [{"name": "New"}]
    assert merged["untouched"] == "value"
