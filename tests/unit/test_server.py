"""Server entry tests."""

import pytest

from maestro.server import _strip_userinfo, create_server


def test_create_server_returns_fastmcp_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_server() boots a FastMCP app with our identity."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    mcp = create_server()
    assert mcp.name == "maestro"


async def test_create_server_registers_no_tools_initially(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 1 server has zero tools registered -- domain tools land in later phases."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    mcp = create_server()
    tools = await mcp.list_tools()
    assert len(tools) == 0


def test_strip_userinfo_with_creds() -> None:
    assert _strip_userinfo("https://user:pass@example.com/path") == "https://example.com/path"


def test_strip_userinfo_with_user_only() -> None:
    assert _strip_userinfo("https://user@example.com/") == "https://example.com/"


def test_strip_userinfo_with_port() -> None:
    assert _strip_userinfo("https://user:pass@example.com:8080/x") == "https://example.com:8080/x"


def test_strip_userinfo_clean_url() -> None:
    assert _strip_userinfo("https://example.com/path") == "https://example.com/path"
