"""Verify AIOStreams tools are registered with correct annotations."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_all_aiostreams_read_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected_reads = [
        "aiostreams_get_config",
        "aiostreams_get_services",
        "aiostreams_get_addons",
        "aiostreams_get_filters",
        "aiostreams_get_sort_order",
        "aiostreams_get_template_list",
        "aiostreams_get_active_template",
        "aiostreams_get_statistics",
        "aiostreams_get_install_url",
    ]
    for name in expected_reads:
        assert name in names, f"expected read tool {name!r} not registered"


async def test_all_aiostreams_write_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected_writes = [
        "aiostreams_set_preferred_languages",
        "aiostreams_set_cached_only",
        "aiostreams_set_resolution_floor",
        "aiostreams_set_core_engine",
        "aiostreams_add_addon",
        "aiostreams_remove_addon",
        "aiostreams_toggle_addon",
        "aiostreams_set_filter",
        "aiostreams_set_sort_order",
        "aiostreams_set_misc_toggle",
        "aiostreams_apply_template",
        "aiostreams_save",
    ]
    for name in expected_writes:
        assert name in names, f"expected write tool {name!r} not registered"


async def test_total_aiostreams_tool_count_is_21() -> None:
    """Locks the tool surface count -- Phase 3 ships exactly 21 AIOStreams tools."""
    mcp = create_server()
    tools = await mcp.list_tools()
    aiostreams_tools = [t for t in tools if t.name.startswith("aiostreams_")]
    assert len(aiostreams_tools) == 21


async def test_aiostreams_annotation_types_correct() -> None:
    """Locks annotation type per tool: 9 read_only, 12 destructive.

    Catches future regressions if a tool is swapped from read to destructive
    or vice versa (e.g., marking aiostreams_save as read-only by mistake).
    FastMCP 3.3.1 surfaces `tool.annotations` as a `ToolAnnotations` pydantic
    model with attribute access (`ann.readOnlyHint`, `ann.destructiveHint`).
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools if t.name.startswith("aiostreams_")}

    expected_read_only = {
        "aiostreams_get_config",
        "aiostreams_get_services",
        "aiostreams_get_addons",
        "aiostreams_get_filters",
        "aiostreams_get_sort_order",
        "aiostreams_get_template_list",
        "aiostreams_get_active_template",
        "aiostreams_get_statistics",
        "aiostreams_get_install_url",
    }
    expected_destructive = {
        "aiostreams_set_preferred_languages",
        "aiostreams_set_cached_only",
        "aiostreams_set_resolution_floor",
        "aiostreams_set_core_engine",
        "aiostreams_add_addon",
        "aiostreams_remove_addon",
        "aiostreams_toggle_addon",
        "aiostreams_set_filter",
        "aiostreams_set_sort_order",
        "aiostreams_set_misc_toggle",
        "aiostreams_apply_template",
        "aiostreams_save",
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
