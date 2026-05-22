"""MCP tool-boundary error middleware.

Translates Maestro's typed exceptions into structured MCP errors so all
tool authors can just `raise MaestroException(SomeError(...))` without
per-tool try/except boilerplate.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp import McpError
from mcp.types import ErrorData
from pydantic import ValidationError

from maestro.errors import MaestroException

log = structlog.get_logger("maestro.middleware")


class MaestroErrorMiddleware(Middleware):
    """Translate Maestro exceptions to structured MCP errors at the tool boundary.

    Contract:
    - MaestroException -> McpError(-32603) with the structured MaestroError payload in `data`
    - pydantic.ValidationError -> McpError(-32602 Invalid params) with field errors in `data`
    - Other exceptions propagate to FastMCP's default handler (don't swallow)
    """

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        try:
            return await call_next(context)
        except MaestroException as e:
            log.warning(
                "tool_error",
                tool=context.method,
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
                tool=context.method,
                error_count=e.error_count(),
            )
            raise McpError(
                ErrorData(
                    code=-32602,
                    message=f"Invalid params: {e.error_count()} validation errors",
                    data={"validation_errors": e.errors()},
                )
            ) from e
