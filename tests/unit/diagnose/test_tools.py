"""Diagnostic tool tests."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from maestro.diagnose.tools import DiagnoseToolset
from maestro.errors import MaestroException, UpstreamError
from maestro.realdebrid.filter_gate import FilterGateLearner


@respx.mock
@pytest.mark.asyncio
async def test_stack_health_pings_each_addon() -> None:
    """Each configured addon's manifest is probed; per-addon status surfaces."""
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "a"})
    )
    respx.get("https://b.example/manifest.json").mock(return_value=httpx.Response(500))

    toolset = DiagnoseToolset(
        addon_urls=["https://a.example", "https://b.example"],
        rd_get_user_info=None,
        learner=FilterGateLearner(state_path=None),
        timeout_s=5.0,
    )
    health = await toolset.stack_health()
    assert health["addons"]["https://a.example"]["status"] == "ok"
    assert health["addons"]["https://b.example"]["status"] == "error"


@pytest.mark.asyncio
async def test_rd_health_reports_auth_state() -> None:
    """``rd_health`` returns authenticated=True and forwards RD user info."""
    rd_user = AsyncMock(return_value={"username": "clay", "premium": 1})
    learner = FilterGateLearner(state_path=None)

    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=rd_user,
        learner=learner,
        timeout_s=5.0,
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is True
    assert health["username"] == "clay"


@pytest.mark.asyncio
async def test_rd_health_reports_filter_gate_learning_count() -> None:
    """Learning state surfaces -- the count of runtime-promoted keywords."""
    learner = FilterGateLearner(state_path=None)
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")

    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(return_value={"username": "x"}),
        learner=learner,
        timeout_s=5.0,
    )
    health = await toolset.rd_health()
    assert health["filter_gate"]["learned_count"] == 1


@pytest.mark.asyncio
async def test_dud_rate_returns_v1x_stub() -> None:
    """v1.x stub -- explicit status flag so callers can branch on it."""
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=None,
        learner=FilterGateLearner(state_path=None),
    )
    result = await toolset.dud_rate(window="30d")
    assert result["status"] == "not_implemented_v1"
    assert result["window"] == "30d"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, [], "str", 42])
async def test_rd_health_non_dict_user_info_degrades(bad: object) -> None:
    """A 200 /user body that is valid JSON but not an object degrades gracefully, no raise."""
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(return_value=bad),
        learner=FilterGateLearner(state_path=None),
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is False
    assert health["error"] == "malformed_user_response"


@pytest.mark.asyncio
async def test_rd_health_json_decode_error_is_malformed() -> None:
    """A JSONDecodeError (bad body from get_user_info's un-wrapped .json()) -> malformed_user_response."""
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(side_effect=json.JSONDecodeError("x", "doc", 0)),
        learner=FilterGateLearner(state_path=None),
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is False
    assert health["error"] == "malformed_user_response"


@pytest.mark.asyncio
async def test_rd_health_unexpected_error_is_distinct() -> None:
    """A non-JSON ValueError (client/config bug) -> unexpected_error, not mislabeled malformed (C-3)."""
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(side_effect=ValueError("invalid RD client config")),
        learner=FilterGateLearner(state_path=None),
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is False
    assert health["error"] == "unexpected_error"


@pytest.mark.asyncio
async def test_rd_health_surfaces_error_code_not_leaky_message() -> None:
    """A caught MaestroException surfaces the leak-free code, never the body-bearing message."""
    leaky = MaestroException(
        UpstreamError(domain="realdebrid", message="RD 403: Bearer SUPERSECRET leaked")
    )
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(side_effect=leaky),
        learner=FilterGateLearner(state_path=None),
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is False
    assert health["error"] == "upstream_error"
    assert "SUPERSECRET" not in str(health)


@pytest.mark.asyncio
async def test_rd_health_degenerate_error_payload_does_not_crash() -> None:
    """Crash-proof: a MaestroException with a missing error payload degrades, not raises (FF-1)."""
    exc = MaestroException(UpstreamError(domain="realdebrid"))
    exc.error = None  # type: ignore[assignment]  # simulate a degenerate payload
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(side_effect=exc),
        learner=FilterGateLearner(state_path=None),
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is False
    assert health["error"] == "unknown_error"


@pytest.mark.asyncio
async def test_rd_health_splits_candidate_and_active_learned() -> None:
    """learned_count counts all candidates; active_learned_count only promoted (>= threshold)."""
    learner = FilterGateLearner(state_path=None)
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")  # NOVELKW count=1 (sub-threshold)
    learner.record_strike("x.PROMOTED.mkv", "infringing_file")  # PROMOTED count=1
    learner.record_strike("y.PROMOTED.mkv", "infringing_file")  # PROMOTED count=2 -> active
    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=None,
        learner=learner,
    )
    fg = (await toolset.rd_health())["filter_gate"]
    assert fg["learned_count"] == 2
    assert fg["active_learned_count"] == 1
    assert fg["active_learned_keywords"] == ["PROMOTED"]
    assert "NOVELKW" not in fg["active_learned_keywords"]
