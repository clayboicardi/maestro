"""AIOStreams domain -- config CRUD + Tamtaro template support."""

from __future__ import annotations

from fastmcp import FastMCP

from maestro.aiostreams.client import AIOStreamsClient
from maestro.aiostreams.tools import AIOStreamsToolset
from maestro.annotations import destructive, read_only
from maestro.config import MaestroSettings


def register_tools(mcp: FastMCP, settings: MaestroSettings) -> None:
    """Register all 21 AIOStreams tools on the FastMCP app."""
    client = AIOStreamsClient(
        base_url=str(settings.aiostreams_base_url),
        uuid=settings.aiostreams_uuid,
        password=settings.aiostreams_password.get_secret_value(),
        timeout_s=settings.http_timeout_s,
        retry_attempts=settings.retry_attempts,
    )
    toolset = AIOStreamsToolset(
        get_config=client.get_config,
        put_config=client.put_config,
    )

    # Read tools (9 total)
    mcp.tool(
        name="aiostreams_get_config",
        annotations=read_only(title="Get AIOStreams Config").model_dump(),
    )(toolset.get_config)
    mcp.tool(
        name="aiostreams_get_services",
        annotations=read_only(title="Get AIOStreams Services").model_dump(),
    )(toolset.get_services)
    mcp.tool(
        name="aiostreams_get_addons",
        annotations=read_only(title="List AIOStreams Aggregated Addons").model_dump(),
    )(toolset.get_addons)
    mcp.tool(
        name="aiostreams_get_filters",
        annotations=read_only(title="Get AIOStreams Filters").model_dump(),
    )(toolset.get_filters)
    mcp.tool(
        name="aiostreams_get_sort_order",
        annotations=read_only(title="Get AIOStreams Sort Order").model_dump(),
    )(toolset.get_sort_order)
    mcp.tool(
        name="aiostreams_get_template_list",
        annotations=read_only(title="List Available Templates").model_dump(),
    )(toolset.get_template_list)
    mcp.tool(
        name="aiostreams_get_active_template",
        annotations=read_only(title="Get Active Template Name").model_dump(),
    )(toolset.get_active_template)
    mcp.tool(
        name="aiostreams_get_statistics",
        annotations=read_only(title="Get AIOStreams Statistics").model_dump(),
    )(toolset.get_statistics)
    mcp.tool(
        name="aiostreams_get_install_url",
        annotations=read_only(title="Get Stremio Install URL").model_dump(),
    )(toolset.get_install_url)

    # Write tools (12 total)
    mcp.tool(
        name="aiostreams_set_preferred_languages",
        annotations=destructive(title="Set Preferred Languages").model_dump(),
    )(toolset.set_preferred_languages)
    mcp.tool(
        name="aiostreams_set_cached_only",
        annotations=destructive(title="Set Cached-Only Filter").model_dump(),
    )(toolset.set_cached_only)
    mcp.tool(
        name="aiostreams_set_resolution_floor",
        annotations=destructive(title="Set Resolution Floor").model_dump(),
    )(toolset.set_resolution_floor)
    mcp.tool(
        name="aiostreams_set_core_engine",
        annotations=destructive(title="Set SEL Core Engine").model_dump(),
    )(toolset.set_core_engine)
    mcp.tool(
        name="aiostreams_add_addon",
        annotations=destructive(title="Add Aggregated Addon").model_dump(),
    )(toolset.add_addon)
    mcp.tool(
        name="aiostreams_remove_addon",
        annotations=destructive(title="Remove Aggregated Addon").model_dump(),
    )(toolset.remove_addon)
    mcp.tool(
        name="aiostreams_toggle_addon",
        annotations=destructive(title="Toggle Aggregated Addon").model_dump(),
    )(toolset.toggle_addon)
    mcp.tool(
        name="aiostreams_set_filter",
        annotations=destructive(title="Set Generic Filter").model_dump(),
    )(toolset.set_filter)
    mcp.tool(
        name="aiostreams_set_sort_order",
        annotations=destructive(title="Set Sort Order").model_dump(),
    )(toolset.set_sort_order)
    mcp.tool(
        name="aiostreams_set_misc_toggle",
        annotations=destructive(title="Set Misc Toggle").model_dump(),
    )(toolset.set_misc_toggle)
    mcp.tool(
        name="aiostreams_apply_template",
        annotations=destructive(title="Apply Template (DESTRUCTIVE)").model_dump(),
    )(toolset.apply_template)
    mcp.tool(
        name="aiostreams_save",
        annotations=destructive(title="Save Staged Writes").model_dump(),
    )(toolset.save)
