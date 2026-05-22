"""Real-Debrid tool tests."""

import httpx
import pytest
import respx

from maestro.realdebrid.filter_gate import FilterGateLearner
from maestro.realdebrid.tools import RDToolset


@pytest.fixture
def toolset(tmp_path) -> RDToolset:
    learner = FilterGateLearner(state_path=tmp_path / "state.json")
    return RDToolset(api_token="test_token", learner=learner, timeout_s=5.0)


def test_filter_gate_check_returns_risk_dict(toolset: RDToolset) -> None:
    result = toolset.filter_gate_check("S01E03.WEB-DL.AMZN.mkv")
    assert result["risk"] == "high"
    assert "WEB-DL" in result["matched_keywords"]


def test_filter_gate_check_low_for_clean_filename(toolset: RDToolset) -> None:
    result = toolset.filter_gate_check("S01E03.BluRay.1080p.x264.mkv")
    assert result["risk"] == "low"
    assert result["matched_keywords"] == []


@respx.mock
@pytest.mark.asyncio
async def test_check_cache_overlays_filter_gate(toolset: RDToolset) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/abc/def").mock(
        return_value=httpx.Response(
            200,
            json={
                "abc": {"rd": [{"1": {"filename": "S01E03.WEB-DL.AMZN.mkv"}}]},
                "def": {"rd": [{"1": {"filename": "S01E03.BluRay.mkv"}}]},
            },
        )
    )

    result = await toolset.check_cache(
        infohashes=["abc", "def"],
        filenames={"abc": "S01E03.WEB-DL.AMZN.mkv", "def": "S01E03.BluRay.mkv"},
    )
    abc = next(r for r in result if r["hash"] == "abc")
    deff = next(r for r in result if r["hash"] == "def")
    assert abc["cached"] is True
    assert abc["filter_gate_risk"] == "high"
    assert deff["filter_gate_risk"] == "low"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_passes_through(toolset: RDToolset) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(200, json={"username": "clay", "premium": 1})
    )
    info = await toolset.get_user_info()
    assert info["username"] == "clay"
