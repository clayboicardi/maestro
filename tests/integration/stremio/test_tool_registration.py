"""Verify Stremio tools are registered with correct annotations."""

import pytest

from maestro.server import create_server


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


async def test_all_stremio_tools_registered() -> None:
    mcp = create_server()
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    expected = [
        "stremio_query_addon",
        "stremio_query_addons_parallel",
        "stremio_get_manifest",
        "stremio_dedupe_streams",
        "stremio_filter_streams",
        "stremio_rank_streams",
    ]
    for name in expected:
        assert name in names, f"expected stremio tool {name!r} not registered"


async def test_total_stremio_tool_count_is_6() -> None:
    """Locks the tool surface count -- Phase 6 ships exactly 6 Stremio tools."""
    mcp = create_server()
    tools = await mcp.list_tools()
    stremio_tools = [t for t in tools if t.name.startswith("stremio_")]
    assert len(stremio_tools) == 6


async def test_stremio_annotation_types_correct() -> None:
    """Locks annotation type per tool: 3 read_only, 3 pure_compute, 0 destructive.

    Distribution:
    - read_only (3): query_addon, query_addons_parallel, get_manifest
      (network IO, no state mutation)
    - pure_compute (3): dedupe_streams, filter_streams, rank_streams
      (pure transforms, no network)
    - destructive (0): Stremio is read-only by protocol; addons don't
      have a "write" surface from a client's perspective.

    FastMCP 3.3.1 surfaces ``tool.annotations`` as a ``ToolAnnotations``
    pydantic model with attribute access (``ann.readOnlyHint``,
    ``ann.destructiveHint``, ``ann.idempotentHint``, ``ann.openWorldHint``).
    """
    mcp = create_server()
    tools = await mcp.list_tools()
    by_name = {t.name: t for t in tools if t.name.startswith("stremio_")}

    expected_read_only = {
        "stremio_query_addon",
        "stremio_query_addons_parallel",
        "stremio_get_manifest",
    }
    expected_pure_compute = {
        "stremio_dedupe_streams",
        "stremio_filter_streams",
        "stremio_rank_streams",
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

    stremio_tools = [t for t in tools if t.name.startswith("stremio_")]
    destructive_count = sum(
        1 for t in stremio_tools if t.annotations and t.annotations.destructiveHint
    )
    assert destructive_count == 0, (
        f"expected 0 destructive Stremio tools, found {destructive_count}"
    )
