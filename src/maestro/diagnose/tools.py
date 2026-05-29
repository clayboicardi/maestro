"""Diagnostic MCP tool definitions (3 tools).

The diagnose domain surfaces three read-only health probes:

- ``diagnose_stack_health`` -- pings each configured addon's manifest
  endpoint; returns per-addon status + latency.
- ``diagnose_rd_health`` -- verifies RD auth state and reports filter-gate
  learning counts. See :meth:`DiagnoseToolset.rd_health` for the exact
  meaning of each count -- it distinguishes ``learned_count`` (all tracked
  candidates) from ``active_learned_count`` (only the promoted keywords
  that actually influence risk classification).
- ``diagnose_dud_rate`` -- v1.x stub. Returns ``not_implemented_v1``
  until a persistent telemetry layer lands (see design doc's
  "Open questions deferred to v1.x").

The toolset is parameterized to accept callables and the existing
:class:`FilterGateLearner` instance so it stays unit-testable without
spinning up an MCP server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP

from maestro.annotations import read_only
from maestro.diagnose.stack_health import probe_all
from maestro.errors import MaestroException
from maestro.realdebrid.filter_gate import LEARNED_PROMOTION_THRESHOLD, FilterGateLearner

RDUserInfoFn = Callable[[], Awaitable[dict[str, Any]]]


class DiagnoseToolset:
    """Encapsulates configured addon URLs + RD/learner refs for the diagnose tools."""

    def __init__(
        self,
        *,
        addon_urls: list[str],
        rd_get_user_info: RDUserInfoFn | None,
        learner: FilterGateLearner,
        timeout_s: float = 10.0,
    ) -> None:
        self._addon_urls = addon_urls
        self._rd_get_user_info = rd_get_user_info
        self._learner = learner
        self._timeout_s = timeout_s

    async def stack_health(self) -> dict[str, Any]:
        """Ping each configured addon's manifest. Returns per-addon status + latency."""
        addons = await probe_all(self._addon_urls, timeout_s=self._timeout_s)
        return {"addons": addons}

    async def rd_health(self) -> dict[str, Any]:
        """Verify RD auth + report filter-gate learning state.

        Crash-proofing: a health probe must report status without raising.
        ``RDClient`` wraps HTTP-level failures (non-2xx status + transport/
        timeout) in ``MaestroException``, but ``get_user_info`` returns
        ``response.json()`` un-wrapped, so a 200 response with a bad body
        can still surface as a raw ``ValueError`` (non-JSON) or a non-dict
        payload (``null``/list). All three are handled -> graceful
        ``authenticated=False`` with a short ``error`` token, never a raise.

        Secret hygiene: on a caught ``MaestroException`` the response
        surfaces the structured ``error.code`` (+ fixed ``suggestion``),
        NOT ``error.message``. The 4xx-other ``UpstreamError`` message
        embeds a 200-byte upstream body excerpt that can reflect a bearer
        token, a credential-bearing URL, or a filename; the ``code`` enum
        is leak-free. (Redacting the body excerpt at the ``RDClient`` source
        -- which would also cover the other RD tools -- is tracked as a
        follow-up; this probe defends its own surface.)

        ``filter_gate`` counts:

        - ``known_count`` -- size of the static ``KNOWN_KEYWORDS`` baseline.
        - ``learned_count`` / ``learned_keywords`` -- ALL runtime-tracked
          candidates, including sub-threshold ones (evidence ``count`` below
          :data:`~maestro.realdebrid.filter_gate.LEARNED_PROMOTION_THRESHOLD`)
          that do NOT yet influence ``predict_risk``.
        - ``active_learned_count`` / ``active_learned_keywords`` -- only the
          promoted candidates (``count`` >= threshold) that actually gate
          risk classification. Always ``active_learned_count <= learned_count``.
        """
        auth_state: dict[str, Any] = {"authenticated": False}
        if self._rd_get_user_info is not None:
            try:
                info = await self._rd_get_user_info()
            except MaestroException as e:
                auth_state = {
                    "authenticated": False,
                    "error": e.error.code,
                    "suggestion": e.error.suggestion,
                }
            except ValueError:
                auth_state = {"authenticated": False, "error": "malformed_user_response"}
            else:
                if isinstance(info, dict):
                    auth_state = {
                        "authenticated": True,
                        "username": info.get("username"),
                        "premium": info.get("premium"),
                    }
                else:
                    auth_state = {"authenticated": False, "error": "malformed_user_response"}
        state = self._learner.export_state()
        learned = self._learner.learned_keywords
        active = sorted(kw for kw, ev in learned.items() if ev.count >= LEARNED_PROMOTION_THRESHOLD)
        return {
            **auth_state,
            "filter_gate": {
                "known_count": len(state["known_keywords"]),
                "learned_count": len(learned),
                "learned_keywords": list(learned.keys()),
                "active_learned_count": len(active),
                "active_learned_keywords": active,
            },
        }

    async def dud_rate(self, window: str = "7d") -> dict[str, Any]:
        """v1.x stub -- returns ``not_implemented_v1`` until persistent telemetry lands."""
        return {
            "status": "not_implemented_v1",
            "message": (
                "diagnose_dud_rate requires a persistent telemetry layer "
                "(deferred to v1.x). See docs/specs/2026-05-21-maestro-design.md "
                "'Open questions deferred to v1.x'."
            ),
            "window": window,
        }


def register_tools(
    mcp: FastMCP,
    *,
    addon_urls: list[str],
    rd_get_user_info: RDUserInfoFn,
    learner: FilterGateLearner,
    timeout_s: float = 10.0,
) -> DiagnoseToolset:
    """Register the 3 diagnose tools on the FastMCP app.

    Returns the toolset so callers can introspect or test the instance
    without re-instantiating it.

    Annotation contract: all three are ``read_only`` with
    ``idempotent=False`` -- repeated calls sample changing state (addon
    latency, RD auth/premium status, learner counts), so a client must
    not treat a prior result as still-valid. The ``idempotent=False`` on
    ``diagnose_dud_rate`` is forward-looking: today it returns a constant
    stub (which IS trivially idempotent and touches nothing), but the
    annotation is set for its v1.x telemetry-backed behavior so clients
    don't have to re-learn the hint when the stub is replaced.
    ``openWorldHint`` is left at its ``read_only`` default (True) for the
    same forward-looking reason.
    """
    toolset = DiagnoseToolset(
        addon_urls=addon_urls,
        rd_get_user_info=rd_get_user_info,
        learner=learner,
        timeout_s=timeout_s,
    )

    mcp.tool(
        name="diagnose_stack_health",
        annotations=read_only(title="Probe Addon Stack Health", idempotent=False).model_dump(),
    )(toolset.stack_health)
    mcp.tool(
        name="diagnose_rd_health",
        annotations=read_only(
            title="Probe Real-Debrid Auth + Filter-Gate State", idempotent=False
        ).model_dump(),
    )(toolset.rd_health)
    mcp.tool(
        name="diagnose_dud_rate",
        annotations=read_only(
            title="Dud-Rate Telemetry (v1.x stub)", idempotent=False
        ).model_dump(),
    )(toolset.dud_rate)
    return toolset
