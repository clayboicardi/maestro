"""MaestroErrorMiddleware tests.

The middleware is the single error-handling contract at the MCP tool
boundary. These tests pin the contract: MaestroException -> -32603 with
structured payload, ValidationError -> -32602 with field errors, and
non-Maestro exceptions propagate untouched.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp import McpError
from pydantic import BaseModel, ValidationError

import maestro.middleware as mw
from maestro.errors import AuthError, MaestroException
from maestro.middleware import MaestroErrorMiddleware


def _make_context(tool_name: str = "test_tool") -> MagicMock:
    """Build a minimal MiddlewareContext stub with `.message.name` set.

    The real `MiddlewareContext[CallToolRequestParams]` carries the tool name
    at `context.message.name` (NOT `context.method`, which is the JSON-RPC
    method string "tools/call" for every tool call). The middleware reads
    `.message.name`, so the stub mirrors that surface.
    """
    ctx = MagicMock()
    ctx.message.name = tool_name
    return ctx


def _mock_middleware_log(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace `maestro.middleware.log` with a MagicMock and return it.

    Per-test log mocking gives explicit assertions on log fields AND
    eliminates the stderr-cache pollution from `test_logging.py` (which
    monkeypatches sys.stderr, configures structlog, then lets the buffer
    go out of scope -- subsequent structlog calls would otherwise hit a
    closed file). With the live logger mocked out, that path is never
    executed during these tests.
    """
    mock_log = MagicMock()
    monkeypatch.setattr(mw, "log", mock_log)
    return mock_log


async def test_maestro_exception_translates_to_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MaestroException -> McpError(-32603) with structured payload in `data`."""
    mock_log = _mock_middleware_log(monkeypatch)
    middleware = MaestroErrorMiddleware()
    payload = AuthError(domain="aiostreams", suggestion="check creds")
    call_next = AsyncMock(side_effect=MaestroException(payload))

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(_make_context("aiostreams_get_config"), call_next)

    err = exc_info.value.error
    assert err.code == -32603
    assert err.data == payload.model_dump()
    assert "AuthError" in err.message
    assert "Authentication failed" in err.message

    # Log assertion: the tool-error path MUST log the real tool name (from
    # `context.message.name`), NOT the JSON-RPC method "tools/call". This is
    # the regression guard for Issue 1.
    mock_log.warning.assert_called_once_with(
        "tool_error",
        tool="aiostreams_get_config",
        error_type="AuthError",
    )


async def test_validation_error_translates_to_invalid_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pydantic.ValidationError -> McpError(-32602) with field errors in `data`."""
    mock_log = _mock_middleware_log(monkeypatch)

    class _Sample(BaseModel):
        required_field: int

    with pytest.raises(ValidationError) as ve_info:
        _Sample.model_validate({})  # missing required field -> ValidationError
    validation_error = ve_info.value

    middleware = MaestroErrorMiddleware()
    call_next = AsyncMock(side_effect=validation_error)

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(_make_context("realdebrid_get_user_info"), call_next)

    err = exc_info.value.error
    assert err.code == -32602
    assert err.message.startswith("Invalid params:")
    assert isinstance(err.data, dict)
    assert "validation_errors" in err.data
    assert len(err.data["validation_errors"]) >= 1

    # Log assertion: validation-error path logs the real tool name + error count.
    mock_log.info.assert_called_once_with(
        "tool_input_invalid",
        tool="realdebrid_get_user_info",
        error_count=validation_error.error_count(),
    )


async def test_runtime_error_propagates_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-Maestro / non-Validation exceptions propagate to FastMCP's default handler."""
    mock_log = _mock_middleware_log(monkeypatch)
    middleware = MaestroErrorMiddleware()
    original = RuntimeError("something else broke")
    call_next = AsyncMock(side_effect=original)

    with pytest.raises(RuntimeError) as exc_info:
        await middleware.on_call_tool(_make_context(), call_next)

    # Same instance — middleware must not wrap or replace it.
    assert exc_info.value is original
    # No log emitted on the propagation path — the middleware only logs the
    # paths it actually handles.
    mock_log.warning.assert_not_called()
    mock_log.info.assert_not_called()


async def test_maestro_error_message_reflected_in_mcp_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MaestroError.message field surfaces in the McpError message text."""
    _mock_middleware_log(monkeypatch)
    middleware = MaestroErrorMiddleware()
    payload = AuthError(
        domain="realdebrid",
        message="custom auth failure message",
    )
    call_next = AsyncMock(side_effect=MaestroException(payload))

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(_make_context(), call_next)

    assert "custom auth failure message" in exc_info.value.error.message


async def test_happy_path_returns_call_next_result_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When call_next succeeds, middleware returns its result untouched."""
    _mock_middleware_log(monkeypatch)
    middleware = MaestroErrorMiddleware()
    sentinel: dict[str, Any] = {"result": "ok"}
    call_next = AsyncMock(return_value=sentinel)

    result = await middleware.on_call_tool(_make_context(), call_next)
    assert result is sentinel
