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
import structlog
from mcp import McpError
from pydantic import BaseModel, ValidationError

from maestro.errors import AuthError, MaestroException
from maestro.middleware import MaestroErrorMiddleware


@pytest.fixture(autouse=True)
def _reset_structlog_logger() -> None:
    """Force the middleware's cached logger to rebind to live stderr.

    `test_logging.py` monkeypatches sys.stderr to a StringIO, configures
    structlog (which caches the file via PrintLoggerFactory), and lets the
    StringIO go out of scope. Subsequent structlog calls then hit a closed
    file. Reset config + clear the cache to force a fresh bind.
    """
    structlog.reset_defaults()
    # Bust the module-level cached logger so it re-resolves on next call.
    import maestro.middleware as mw  # noqa: PLC0415 - test-local rebind

    mw.log = structlog.get_logger("maestro.middleware")


def _make_context(method: str = "test_tool") -> MagicMock:
    """Build a minimal MiddlewareContext stub with a `.method` attribute."""
    ctx = MagicMock()
    ctx.method = method
    return ctx


async def test_maestro_exception_translates_to_internal_error() -> None:
    """MaestroException -> McpError(-32603) with structured payload in `data`."""
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


async def test_validation_error_translates_to_invalid_params() -> None:
    """pydantic.ValidationError -> McpError(-32602) with field errors in `data`."""

    class _Sample(BaseModel):
        required_field: int

    try:
        _Sample.model_validate({})  # missing required field -> ValidationError
    except ValidationError as ve:
        validation_error: ValidationError = ve
    else:  # pragma: no cover - defensive; model_validate must raise above
        pytest.fail("ValidationError was not raised by model_validate")

    middleware = MaestroErrorMiddleware()
    call_next = AsyncMock(side_effect=validation_error)

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(_make_context(), call_next)

    err = exc_info.value.error
    assert err.code == -32602
    assert err.message.startswith("Invalid params:")
    assert isinstance(err.data, dict)
    assert "validation_errors" in err.data
    assert len(err.data["validation_errors"]) >= 1


async def test_runtime_error_propagates_untouched() -> None:
    """Non-Maestro / non-Validation exceptions propagate to FastMCP's default handler."""
    middleware = MaestroErrorMiddleware()
    original = RuntimeError("something else broke")
    call_next = AsyncMock(side_effect=original)

    with pytest.raises(RuntimeError) as exc_info:
        await middleware.on_call_tool(_make_context(), call_next)

    # Same instance — middleware must not wrap or replace it.
    assert exc_info.value is original


async def test_maestro_error_message_reflected_in_mcp_error() -> None:
    """The MaestroError.message field surfaces in the McpError message text."""
    middleware = MaestroErrorMiddleware()
    payload = AuthError(
        domain="realdebrid",
        message="custom auth failure message",
    )
    call_next = AsyncMock(side_effect=MaestroException(payload))

    with pytest.raises(McpError) as exc_info:
        await middleware.on_call_tool(_make_context(), call_next)

    assert "custom auth failure message" in exc_info.value.error.message


async def test_happy_path_returns_call_next_result_unchanged() -> None:
    """When call_next succeeds, middleware returns its result untouched."""
    middleware = MaestroErrorMiddleware()
    sentinel: dict[str, Any] = {"result": "ok"}
    call_next = AsyncMock(return_value=sentinel)

    result = await middleware.on_call_tool(_make_context(), call_next)
    assert result is sentinel
