"""Verify diagnose tools are registered with correct annotations."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_all_diagnose_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected = [
        "diagnose_stack_health",
        "diagnose_rd_health",
        "diagnose_dud_rate",
    ]
    for name in expected:
        assert name in names, f"expected diagnose tool {name!r} not registered"


async def test_total_diagnose_tool_count_is_3() -> None:
    """Phase 8 ships exactly 3 diagnose tools."""
    mcp = create_server()
    tools = await mcp.list_tools()
    diagnose_tools = [t for t in tools if t.name.startswith("diagnose_")]
    assert len(diagnose_tools) == 3


async def test_diagnose_annotation_types_correct() -> None:
    """Locks annotation type per tool: 3 read_only, 0 destructive.

    All three diagnose tools are read-only -- they observe state but
    never mutate addon, RD, or filter-gate state.
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools if t.name.startswith("diagnose_")}

    expected_read_only = {
        "diagnose_stack_health",
        "diagnose_rd_health",
        "diagnose_dud_rate",
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


async def test_total_tool_count_is_43() -> None:
    """Phase 8 lock: 21 aiostreams + 5 torrentio + 7 realdebrid + 6 stremio + 1 compose + 3 diagnose."""
    mcp = create_server()
    tools = await mcp.list_tools()
    assert len(tools) == 43
