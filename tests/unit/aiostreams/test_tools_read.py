"""Read-tool tests for AIOStreams domain (with secret redaction check)."""

from copy import deepcopy
from typing import Any

import pytest

from maestro.aiostreams.tools import (
    AIOStreamsToolset,
    _redact_secrets,
)


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "services": [
            {
                "id": "realdebrid",
                "credentials": {"apiKey": "rd_token_real_secret"},
                "enabled": True,
            }
        ],
        "addons": [
            {
                "name": "Comet",
                "enabled": True,
                "manifestUrl": "https://comet.example/manifest.json",
            },
            {
                "name": "MediaFusion",
                "enabled": False,
                "manifestUrl": "https://mf.example/manifest.json",
            },
        ],
        "filters": {"preferred_languages": ["English"], "excluded_resolutions": ["480p"]},
        "sortCriteria": [{"key": "cached", "direction": "desc"}],
        "presets": {"active": "tamtaro_recommended"},
        "statistics": {"enabled": True, "show_errors": True},
        # Top-level sensitive fields (UserDataSchema in schemas_generated.py).
        "tmdbApiKey": "tmdb_secret_token",
        "rpdbApiKey": "rpdb_secret_token",
        "addonPassword": "addon_password_secret",
        # Optional proxy surface (Proxy2 schema).
        "proxy": {
            "enabled": True,
            "url": "https://proxy.example",
            "credentials": "proxy_secret_creds",
        },
    }


@pytest.fixture
def toolset(sample_config: dict[str, Any]) -> AIOStreamsToolset:
    async def fake_get_config() -> dict[str, Any]:
        return deepcopy(sample_config)  # avoid shared-mutable hazard

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_get_config_redacts_service_credentials_by_default(
    toolset: AIOStreamsToolset,
) -> None:
    """Service `credentials` dict values are redacted; credential-name keys preserved."""
    result = await toolset.get_config(include_secrets=False)
    assert result["services"][0]["credentials"] == {"apiKey": "***REDACTED***"}


@pytest.mark.asyncio
async def test_get_config_redacts_top_level_sensitive_fields(
    toolset: AIOStreamsToolset,
) -> None:
    """Top-level API tokens + passwords are redacted by default."""
    result = await toolset.get_config(include_secrets=False)
    assert result["tmdbApiKey"] == "***REDACTED***"
    assert result["rpdbApiKey"] == "***REDACTED***"
    assert result["addonPassword"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_get_config_redacts_proxy_credentials(
    toolset: AIOStreamsToolset,
) -> None:
    """Optional proxy.credentials surface is redacted; sibling fields preserved."""
    result = await toolset.get_config(include_secrets=False)
    assert result["proxy"]["credentials"] == "***REDACTED***"
    assert result["proxy"]["url"] == "https://proxy.example"
    assert result["proxy"]["enabled"] is True


@pytest.mark.asyncio
async def test_get_config_can_include_secrets_when_explicit(
    toolset: AIOStreamsToolset,
) -> None:
    """include_secrets=True returns all sensitive surfaces raw."""
    result = await toolset.get_config(include_secrets=True)
    assert result["services"][0]["credentials"] == {"apiKey": "rd_token_real_secret"}
    assert result["tmdbApiKey"] == "tmdb_secret_token"
    assert result["rpdbApiKey"] == "rpdb_secret_token"
    assert result["addonPassword"] == "addon_password_secret"
    assert result["proxy"]["credentials"] == "proxy_secret_creds"


@pytest.mark.asyncio
async def test_get_services_returns_redacted_list(toolset: AIOStreamsToolset) -> None:
    """get_services redacts per-service credentials but preserves id + enabled."""
    services = await toolset.get_services()
    assert services[0]["credentials"] == {"apiKey": "***REDACTED***"}
    assert services[0]["id"] == "realdebrid"
    assert services[0]["enabled"] is True


@pytest.mark.asyncio
async def test_get_addons_returns_full_list(toolset: AIOStreamsToolset) -> None:
    addons = await toolset.get_addons()
    assert len(addons) == 2
    assert addons[0]["name"] == "Comet"
    assert addons[1]["enabled"] is False


@pytest.mark.asyncio
async def test_get_filters_returns_filter_block(toolset: AIOStreamsToolset) -> None:
    filters = await toolset.get_filters()
    assert filters["preferred_languages"] == ["English"]


@pytest.mark.asyncio
async def test_get_sort_order_returns_criteria(toolset: AIOStreamsToolset) -> None:
    sort_order = await toolset.get_sort_order()
    assert sort_order == [{"key": "cached", "direction": "desc"}]


@pytest.mark.asyncio
async def test_get_active_template(toolset: AIOStreamsToolset) -> None:
    name = await toolset.get_active_template()
    assert name == "tamtaro_recommended"


@pytest.mark.asyncio
async def test_get_statistics(toolset: AIOStreamsToolset) -> None:
    stats = await toolset.get_statistics()
    assert stats["enabled"] is True


@pytest.mark.asyncio
async def test_get_template_list_returns_known_templates(toolset: AIOStreamsToolset) -> None:
    """get_template_list returns the curated KNOWN_TEMPLATES catalog."""
    templates = await toolset.get_template_list()
    assert len(templates) >= 1
    names = [t["name"] for t in templates]
    assert "Tamtaro Complete SEL Setup v2.6.1" in names


# --- Defensive redaction tests (G-fix-1, R-2, R-3 from PR #7 octo:review cycle) ---


def test_redact_secrets_handles_null_services_field() -> None:
    """G-fix-1: `services: null` (per upstream schema) does not raise TypeError."""
    config: dict[str, Any] = {"services": None, "tmdbApiKey": "leak_me"}
    result = _redact_secrets(config)
    assert result["services"] is None
    assert result["tmdbApiKey"] == "***REDACTED***"


def test_redact_secrets_handles_missing_services_field() -> None:
    """G-fix-1: absent `services` key does not raise."""
    config: dict[str, Any] = {"tmdbApiKey": "leak_me"}
    result = _redact_secrets(config)
    assert "services" not in result
    assert result["tmdbApiKey"] == "***REDACTED***"


def test_redact_secrets_redacts_non_dict_service_credentials() -> None:
    """R-3: non-dict `services[].credentials` value (legacy schema or malformed upstream)
    gets defensively redacted (replaced wholesale with REDACTED string) rather than
    silently bypassed.
    """
    config: dict[str, Any] = {
        "services": [
            {
                "id": "legacy_service",
                "credentials": "legacy_string_token_should_not_leak",
                "enabled": True,
            }
        ]
    }
    result = _redact_secrets(config)
    assert result["services"][0]["credentials"] == "***REDACTED***"
    assert result["services"][0]["id"] == "legacy_service"


def test_redact_secrets_handles_dict_proxy_credentials() -> None:
    """R-2: defensive support for hypothetical Proxy2 schema evolution where
    `proxy.credentials` becomes a dict (mirroring Service5.credentials).
    """
    config: dict[str, Any] = {
        "proxy": {
            "enabled": True,
            "url": "https://proxy.example",
            "credentials": {"apiKey": "future_proxy_secret"},
        }
    }
    result = _redact_secrets(config)
    assert result["proxy"]["credentials"] == {"apiKey": "***REDACTED***"}
    assert result["proxy"]["url"] == "https://proxy.example"


def test_redact_secrets_redacts_parent_config_password() -> None:
    """parentConfig.password (the 4th, nested sensitive site) is redacted in place."""
    config: dict[str, Any] = {
        "parentConfig": {
            "uuid": "00000000-0000-0000-0000-000000000000",
            "password": "parent_secret_should_not_leak",
        },
        "tmdbApiKey": "leak_me",
    }
    result = _redact_secrets(config)
    assert result["parentConfig"]["password"] == "***REDACTED***"
    assert result["parentConfig"]["uuid"] == "00000000-0000-0000-0000-000000000000"
    assert result["tmdbApiKey"] == "***REDACTED***"


def test_redact_secrets_handles_missing_or_null_parent_config() -> None:
    """Absent or null parentConfig is a safe no-op (no KeyError / TypeError)."""
    assert "parentConfig" not in _redact_secrets({"tmdbApiKey": "x"})
    assert _redact_secrets({"parentConfig": None})["parentConfig"] is None
