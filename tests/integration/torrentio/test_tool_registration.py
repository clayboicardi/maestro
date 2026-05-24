"""Verify Torrentio tools are registered with correct annotations."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_all_torrentio_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected = [
        "torrentio_parse_url",
        "torrentio_build_url",
        "torrentio_validate_config",
        "torrentio_list_providers",
        "torrentio_list_quality_filters",
        "torrentio_list_sort_options",
        "torrentio_list_debrid_providers",
    ]
    for name in expected:
        assert name in names, f"expected torrentio tool {name!r} not registered"


async def test_total_torrentio_tool_count_is_7() -> None:
    """Locks the torrentio tool surface count: 1 read_only + 6 pure_compute = 7."""
    mcp = create_server()
    tools = await mcp.list_tools()
    torrentio_tools = [t for t in tools if t.name.startswith("torrentio_")]
    assert len(torrentio_tools) == 7


async def test_torrentio_annotation_types_correct() -> None:
    """Locks annotation type per tool: 1 read_only (parse_url), 4 pure_compute.

    pure_compute() factory sets readOnlyHint=False, destructiveHint=False,
    idempotentHint=True, openWorldHint=False. read_only() sets
    readOnlyHint=True, destructiveHint=False, idempotentHint=True (default),
    openWorldHint=True (default).

    FastMCP 3.3.1 surfaces `tool.annotations` as a `ToolAnnotations` pydantic
    model with attribute access (`ann.readOnlyHint`, `ann.destructiveHint`).
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools if t.name.startswith("torrentio_")}

    # torrentio_parse_url is read_only -- it decodes an external URL into a config.
    parse_tool = by_name["torrentio_parse_url"]
    parse_ann = parse_tool.annotations
    assert parse_ann is not None, "torrentio_parse_url: missing annotations"
    assert parse_ann.readOnlyHint is True, (
        f"torrentio_parse_url: expected readOnlyHint=True, got {parse_ann.readOnlyHint}"
    )
    assert parse_ann.destructiveHint is False, (
        f"torrentio_parse_url: expected destructiveHint=False, got {parse_ann.destructiveHint}"
    )

    # The other 6 are pure_compute -- no I/O, deterministic transforms over fixed enums.
    expected_pure_compute = {
        "torrentio_build_url",
        "torrentio_validate_config",
        "torrentio_list_providers",
        "torrentio_list_quality_filters",
        "torrentio_list_sort_options",
        "torrentio_list_debrid_providers",
    }
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
