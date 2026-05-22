"""Verify Real-Debrid tools are registered with correct annotations."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_all_realdebrid_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected = [
        "realdebrid_get_user_info",
        "realdebrid_check_cache",
        "realdebrid_filter_gate_check",
        "realdebrid_add_torrent",
        "realdebrid_get_torrent_status",
        "realdebrid_unrestrict_link",
        "realdebrid_get_library",
    ]
    for name in expected:
        assert name in names, f"expected realdebrid tool {name!r} not registered"


async def test_total_realdebrid_tool_count_is_7() -> None:
    """Locks the tool surface count -- Phase 5 ships exactly 7 RD tools."""
    mcp = create_server()
    tools = await mcp.list_tools()
    rd_tools = [t for t in tools if t.name.startswith("realdebrid_")]
    assert len(rd_tools) == 7


async def test_realdebrid_annotation_types_correct() -> None:
    """Locks annotation type per tool: 4 read_only, 1 pure_compute, 2 destructive.

    Distribution per handoff:
    - read_only (4): get_user_info, check_cache, get_torrent_status, get_library
    - pure_compute (1): filter_gate_check (heuristic only, no network)
    - destructive (2): add_torrent (modifies RD state), unrestrict_link
      (consumes daily-cap quota -- classified destructive per handoff)

    FastMCP 3.3.1 surfaces ``tool.annotations`` as a ``ToolAnnotations``
    pydantic model with attribute access (``ann.readOnlyHint``,
    ``ann.destructiveHint``, ``ann.idempotentHint``, ``ann.openWorldHint``).
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools if t.name.startswith("realdebrid_")}

    expected_read_only = {
        "realdebrid_get_user_info",
        "realdebrid_check_cache",
        "realdebrid_get_torrent_status",
        "realdebrid_get_library",
    }
    expected_pure_compute = {"realdebrid_filter_gate_check"}
    expected_destructive = {
        "realdebrid_add_torrent",
        "realdebrid_unrestrict_link",
    }

    for name in expected_read_only:
        tool = by_name[name]
        ann = tool.annotations
        assert ann is not None, f"{name}: missing annotations"
        assert ann.readOnlyHint is True, (
            f"{name}: expected readOnlyHint=True, got {ann.readOnlyHint}"
        )
        assert ann.destructiveHint is False, (
            f"{name}: expected destructiveHint=False, got {ann.destructiveHint}"
        )

    for name in expected_pure_compute:
        tool = by_name[name]
        ann = tool.annotations
        assert ann is not None, f"{name}: missing annotations"
        assert ann.readOnlyHint is False, (
            f"{name}: expected readOnlyHint=False, got {ann.readOnlyHint}"
        )
        assert ann.destructiveHint is False, (
            f"{name}: expected destructiveHint=False, got {ann.destructiveHint}"
        )
        assert ann.idempotentHint is True, (
            f"{name}: expected idempotentHint=True, got {ann.idempotentHint}"
        )
        assert ann.openWorldHint is False, (
            f"{name}: expected openWorldHint=False, got {ann.openWorldHint}"
        )

    for name in expected_destructive:
        tool = by_name[name]
        ann = tool.annotations
        assert ann is not None, f"{name}: missing annotations"
        assert ann.readOnlyHint is False, (
            f"{name}: expected readOnlyHint=False, got {ann.readOnlyHint}"
        )
        assert ann.destructiveHint is True, (
            f"{name}: expected destructiveHint=True, got {ann.destructiveHint}"
        )
