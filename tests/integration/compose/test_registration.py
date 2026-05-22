"""Verify find_best_stream is registered as an MCP tool with destructive annotation."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_find_best_stream_registered() -> None:
    """find_best_stream MCP tool must surface in the registered tool list.

    Uses the async public API ``mcp.list_tools()`` -- FastMCP 3.3.1 has no
    ``_tool_manager`` attribute (Phase 3 lesson).
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    assert "find_best_stream" in names


async def test_find_best_stream_annotation_is_destructive() -> None:
    """find_best_stream is classified destructive: rd_unrestrict_link burns RD daily-cap quota.

    Mirrors the annotation-type lock pattern from Phase 5+6 integration tests.
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools}
    tool = by_name["find_best_stream"]
    ann = tool.annotations
    assert ann is not None, "find_best_stream: missing annotations"
    assert ann.readOnlyHint is False, (
        f"find_best_stream: expected readOnlyHint=False, got {ann.readOnlyHint}"
    )
    assert ann.destructiveHint is True, (
        f"find_best_stream: expected destructiveHint=True, got {ann.destructiveHint}"
    )


async def test_total_tool_count_is_40() -> None:
    """Phase 7.3 lock: 21 aiostreams + 5 torrentio + 7 realdebrid + 6 stremio + 1 compose."""
    mcp = create_server()
    tools = await mcp.list_tools()
    assert len(tools) == 40
