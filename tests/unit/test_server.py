"""Server entry tests."""

import pytest

from maestro.server import create_server


def test_create_server_returns_fastmcp_instance(monkeypatch: object) -> None:
    """create_server() boots a FastMCP app with our identity."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    mcp = create_server()
    assert mcp.name == "maestro"


def test_create_server_registers_no_tools_initially() -> None:
    """Phase 1 server has zero tools registered — domain tools land in later phases."""
    pytest.importorskip("fastmcp")
    import os  # noqa: PLC0415 - imports follow the importorskip guard

    os.environ.setdefault("MAESTRO_RD_TOKEN", "x")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_UUID", "x")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    from maestro.server import create_server  # noqa: PLC0415, I001 - imports follow the importorskip guard

    mcp = create_server()
    tools = mcp._tool_manager.list_tools() if hasattr(mcp, "_tool_manager") else []
    assert len(tools) == 0
