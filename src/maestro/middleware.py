"""MCP tool-boundary error middleware.

Translates Maestro's typed exceptions into structured MCP errors so all
tool authors can just `raise MaestroException(SomeError(...))` without
per-tool try/except boilerplate.
"""

from __future__ import annotations

import structlog
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp import McpError
from mcp.types import CallToolRequestParams, ErrorData
from pydantic import ValidationError

from maestro.errors import MaestroException

log = structlog.get_logger("maestro.middleware")


class MaestroErrorMiddleware(Middleware):
    """Translate Maestro exceptions to structured MCP errors at the tool boundary.

    Contract (every entry is load-bearing):

    1. ``MaestroException`` -> ``McpError`` with JSON-RPC code ``-32603``
       (Internal error) and the structured ``MaestroError`` payload serialized
       into ``data``. Tools raise ``MaestroException(SomeError(...))``; this
       middleware is the only place that converts it to a wire response, so
       no per-tool try/except boilerplate is required.
    2. ``pydantic.ValidationError`` -> ``McpError`` with JSON-RPC code
       ``-32602`` (Invalid params) and the field-level errors in ``data``.
       Catches input-schema mismatches surfaced by FastMCP's argument
       validation layer.
    3. Any other exception propagates unchanged to FastMCP's default handler
       — never swallow unknown errors. Loud failures are debuggable; silent
       failures are not.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except MaestroException as e:
            log.warning(
                "tool_error",
                tool=context.message.name,
                error_type=type(e.error).__name__,
            )
            raise McpError(
                ErrorData(
                    code=-32603,
                    message=f"{type(e.error).__name__}: {e.error.message}",
                    data=e.error.model_dump(),
                )
            ) from e
        except ValidationError as e:
            log.info(
                "tool_input_invalid",
                tool=context.message.name,
                error_count=e.error_count(),
            )
            raise McpError(
                ErrorData(
                    code=-32602,
                    message=f"Invalid params: {e.error_count()} validation errors",
                    data={"validation_errors": e.errors()},
                )
            ) from e
