"""MCP tool annotation helpers.

Anthropic's Connectors Directory requires every MCP tool to declare
`title` plus `readOnlyHint` or `destructiveHint`. We bake these
into helper factories so every tool registration site sets them
explicitly -- no defaults that could regress.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AnnotationKind = Literal["read", "write", "compute"]

# Verb substrings (wrapped underscores let "get_x" and "x_get_y" both match).
_READ_INFIXES = ("_get_", "_list_", "_check_", "_validate_", "_parse_")
_READ_EXACT = {
    "realdebrid_get_user_info",
    "stremio_query_addon",
    "stremio_query_addons_parallel",
    "stremio_get_manifest",
}
_COMPUTE_EXACT = {
    "stremio_dedupe_streams",
    "stremio_filter_streams",
    "stremio_rank_streams",
    "torrentio_build_url",
    "torrentio_validate_config",
    "torrentio_list_providers",
    "torrentio_list_quality_filters",
    "realdebrid_filter_gate_check",
}


class ToolAnnotations(BaseModel):
    """Shape we pass into FastMCP's `@mcp.tool(annotations=...)`."""

    title: str
    readOnlyHint: bool = False
    destructiveHint: bool = False
    idempotentHint: bool = False
    openWorldHint: bool = True


def read_only(*, title: str, idempotent: bool = True) -> ToolAnnotations:
    return ToolAnnotations(title=title, readOnlyHint=True, idempotentHint=idempotent)


def destructive(*, title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, destructiveHint=True)


def pure_compute(*, title: str) -> ToolAnnotations:
    """Tools that don't touch external state -- pure transforms."""
    return ToolAnnotations(title=title, openWorldHint=False, idempotentHint=True)


def compute_annotation(tool_name: str) -> AnnotationKind:
    """Heuristic mapping for CI lint to verify each tool sets the right annotation.

    Not used at runtime -- runtime registration is explicit.
    """
    if tool_name in _COMPUTE_EXACT:
        return "compute"
    if tool_name in _READ_EXACT:
        return "read"
    if any(p in f"_{tool_name}_" for p in _READ_INFIXES):
        return "read"
    if tool_name == "find_best_stream":
        return "write"
    return "write"
