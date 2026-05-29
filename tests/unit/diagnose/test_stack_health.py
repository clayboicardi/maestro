"""Stack-health probe tests -- failure taxonomy + query-safe URL composition + key sanitization."""

import httpx
import pytest
import respx

from maestro.diagnose.stack_health import probe_addon, probe_all


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_ok_populates_manifest_id() -> None:
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "org.a"})
    )
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "ok"
    assert result["manifest_id"] == "org.a"


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_dict_without_id_is_ok_with_none() -> None:
    """A reachable manifest object lacking ``id`` -> ok + manifest_id=None (reachability, not schema)."""
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"name": "no id here"})
    )
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "ok"
    assert result["manifest_id"] is None


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], [1, 2], "a-string", 42, True])
async def test_probe_addon_non_dict_200_is_error_not_raise(body: object) -> None:
    """A valid-JSON-but-non-object 200 body degrades to status=error, never raises (P1 guard)."""
    respx.get("https://a.example/manifest.json").mock(return_value=httpx.Response(200, json=body))
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "error"
    assert "object" in result["error"]
    assert "latency_ms" in result


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_literal_null_body_is_error() -> None:
    """A literal JSON ``null`` body -> response.json() is None -> guarded as non-object, not a crash."""
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(
            200, content=b"null", headers={"content-type": "application/json"}
        )
    )
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "error"
    assert "object" in result["error"]


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_non_json_body_is_caught() -> None:
    """A 200 with a non-JSON body raises JSONDecodeError (a ValueError) -> caught."""
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "error"


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_connection_error_is_caught() -> None:
    """The httpx.HTTPError catch path -> status=error with latency recorded (CF25)."""
    respx.get("https://down.example/manifest.json").mock(side_effect=httpx.ConnectError("boom"))
    result = await probe_addon("https://down.example", timeout_s=5.0)
    assert result["status"] == "error"
    assert "latency_ms" in result


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_http_error_status() -> None:
    respx.get("https://a.example/manifest.json").mock(return_value=httpx.Response(503))
    result = await probe_addon("https://a.example", timeout_s=5.0)
    assert result["status"] == "error"
    assert result["error"] == "HTTP 503"


@respx.mock
@pytest.mark.asyncio
async def test_probe_addon_query_auth_url_composes_correctly() -> None:
    """A query-auth base composes to https://host/manifest.json?token=... (P2: path correct, query preserved)."""
    route = respx.get("https://q.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "q"})
    )
    result = await probe_addon("https://q.example?token=SECRET", timeout_s=5.0)
    assert result["status"] == "ok"
    assert route.called
    assert str(route.calls.last.request.url) == "https://q.example/manifest.json?token=SECRET"


@respx.mock
@pytest.mark.asyncio
async def test_probe_all_one_malformed_addon_does_not_sink_others() -> None:
    """P1 blast radius: a non-dict 200 from one addon must not fail the whole gather."""
    respx.get("https://good.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "good"})
    )
    respx.get("https://bad.example/manifest.json").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    results = await probe_all(["https://good.example", "https://bad.example"], timeout_s=5.0)
    assert results["https://good.example"]["status"] == "ok"
    assert results["https://bad.example"]["status"] == "error"


@respx.mock
@pytest.mark.asyncio
async def test_probe_all_sanitizes_query_token_from_keys() -> None:
    """P6: a query-string token must not appear as a result dict key."""
    respx.get("https://q.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "q"})
    )
    results = await probe_all(["https://q.example?token=SECRET"], timeout_s=5.0)
    assert "https://q.example" in results
    assert all("SECRET" not in key for key in results)


@respx.mock
@pytest.mark.asyncio
async def test_probe_all_strips_path_embedded_token_from_keys() -> None:
    """C-2: a token in the URL PATH (torrentio/RD style) must not surface as a key."""
    respx.get(url__regex=r"https://addon\.example/.*").mock(
        return_value=httpx.Response(200, json={"id": "x"})
    )
    results = await probe_all(["https://addon.example/realdebrid=RD_SECRET/"], timeout_s=5.0)
    assert all("RD_SECRET" not in key for key in results)
    assert "https://addon.example" in results


@respx.mock
@pytest.mark.asyncio
async def test_probe_all_same_host_addons_do_not_collide() -> None:
    """C-1: two configs on the same host both surface (counter-suffix, no silent overwrite)."""
    respx.get(url__regex=r".*token=BAD.*").mock(return_value=httpx.Response(503))
    respx.get(url__regex=r".*token=GOOD.*").mock(
        return_value=httpx.Response(200, json={"id": "ok"})
    )
    results = await probe_all(
        ["https://a.example?token=BAD", "https://a.example?token=GOOD"], timeout_s=5.0
    )
    assert len(results) == 2
    assert sorted(r["status"] for r in results.values()) == ["error", "ok"]


@pytest.mark.asyncio
async def test_probe_all_empty_list() -> None:
    assert await probe_all([], timeout_s=5.0) == {}
