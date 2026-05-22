"""Async httpx client for AIOStreams /api/v1/user CRUD.

Auth: HTTP Basic with `<uuid>:<password>` since AIOStreams v2.30.
Endpoints: GET / PUT / DELETE under `/api/v1/user/<uuid>`.

PUT is full-replace, not PATCH — callers must read-modify-write.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from maestro.errors import AuthError, InstanceError, MaestroException, UpstreamError

log = structlog.get_logger("maestro.aiostreams.client")


def _is_transient(exc: BaseException) -> bool:
    """Tenacity predicate: only transient UpstreamError payloads are retried.

    AuthError/InstanceError are non-transient at this layer:
    - AuthError: never recovers without operator intervention
    - InstanceError: 404 on the AIOStreams base URL — operator config issue

    UpstreamError is split by the ``is_transient`` field on the payload:
    5xx defaults to True (worth retrying), 4xx is raised with False
    (auth/permissions/not-found do not recover from a retry).
    """
    return (
        isinstance(exc, MaestroException)
        and isinstance(exc.error, UpstreamError)
        and exc.error.is_transient
    )


class AIOStreamsClient:
    """Async client for one AIOStreams instance + one user account.

    Lifecycle: the underlying ``httpx.AsyncClient`` is lazy-initialized
    on first request and reused across calls within the same instance.
    Call :meth:`aclose` to release the connection pool -- note that in
    stdio-MCP deployments this is not currently invoked at shutdown
    (process exit reclaims the sockets); see :meth:`aclose` for the
    rationale.

    Auth model is HTTP Basic with ``<uuid>:<password>``. The same UUID
    appears both in the URL path (``/api/v1/user/<uuid>``) and as the
    basic auth username -- AIOStreams treats the URL path as the
    lookup key and the basic auth header as the credential check.

    Writes are full-replace PUT (not PATCH). Read-modify-write is the
    caller's responsibility; see
    :class:`maestro.aiostreams.modify.ConfigStager` for the in-memory
    staging pattern that bridges per-tool edits onto a single PUT
    flush.
    """

    def __init__(
        self,
        *,
        base_url: str,
        uuid: str,
        password: str,
        timeout_s: float = 15.0,
        retry_attempts: int = 3,
    ) -> None:
        self._uuid = uuid
        self._base = base_url.rstrip("/")
        self._user_url = f"{self._base}/api/v1/user/{uuid}"
        self._auth = httpx.BasicAuth(uuid, password)
        self._timeout_s = timeout_s
        self._retry_attempts = retry_attempts
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the lazy-initialized async HTTP client.

        Constructs an ``httpx.AsyncClient`` on first call (binding auth
        + timeout) and reuses it on subsequent calls. Resetting the
        pool requires :meth:`aclose`.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=httpx.Timeout(self._timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
        """Release the underlying connection pool.

        Idempotent: safe to call multiple times. After close, the next
        request lazily reinitializes the client.

        Known trade-off (CF11): the stdio-MCP server does not call this
        on shutdown -- process exit reclaims sockets, and FastMCP's
        lifespan hooks do not currently expose a clean teardown signal
        for per-domain clients. Revisit if maestro migrates to a
        long-running transport (HTTP/SSE) where leaked pools matter.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _do_request(self, method: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Single attempt: issue the request and translate status codes to MaestroException."""
        client = await self._get_client()
        try:
            response = await client.request(method, self._user_url, json=json)
        except httpx.HTTPError as e:
            raise MaestroException(
                UpstreamError(
                    domain="aiostreams",
                    message=f"HTTP error: {e}",
                )
            ) from e

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise MaestroException(
                AuthError(
                    domain="aiostreams",
                    suggestion="Check MAESTRO_AIOSTREAMS_UUID and MAESTRO_AIOSTREAMS_PASSWORD",
                )
            )
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise MaestroException(
                InstanceError(
                    domain="aiostreams",
                    suggestion="Verify MAESTRO_AIOSTREAMS_BASE_URL + MAESTRO_AIOSTREAMS_UUID exist",
                )
            )
        if HTTPStatus.INTERNAL_SERVER_ERROR <= response.status_code < 600:  # noqa: PLR2004
            raise MaestroException(
                UpstreamError(
                    domain="aiostreams",
                    message=f"upstream {response.status_code}",
                )
            )
        return response

    async def _request(self, method: str, json: dict[str, Any] | None = None) -> httpx.Response:
        """Retry-wrapped request honoring per-instance ``retry_attempts``.

        Wraps :meth:`_do_request` in tenacity's ``AsyncRetrying`` with
        the :func:`_is_transient` predicate (only ``UpstreamError``
        payloads marked transient are retried). Backoff is exponential
        with a 1-4 second window.

        ``response`` is typed ``Response | None`` so the type checker
        accepts the initial state; on the success path the loop body
        assigns it before exit. ``reraise=True`` ensures retry
        exhaustion propagates the underlying exception rather than
        tenacity's ``RetryError`` wrapper, so the assert never fires in
        practice -- either the loop assigns ``response`` or it raises.
        """
        response: httpx.Response | None = None
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_transient),
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(min=1, max=4),
            reraise=True,
        ):
            with attempt:
                response = await self._do_request(method, json)
        # AsyncRetrying guarantees response is set on success (else it reraises).
        assert response is not None
        return response

    async def get_config(self) -> dict[str, Any]:
        """Fetch the current full UserData blob.

        Returns the raw JSON body of ``GET /api/v1/user/<uuid>`` -- shape
        matches the auto-generated Pydantic model derived from the
        upstream AIOStreams Zod schema (see
        :mod:`maestro.aiostreams.schemas_generated`). Includes sensitive
        fields (debrid service credentials, top-level API keys);
        callers serving the result through MCP tools should redact via
        :func:`maestro.aiostreams.tools._redact_secrets` unless the
        caller has explicitly opted into ``include_secrets``.
        """
        log.info("aiostreams_get_config_request")
        response = await self._request("GET")
        return response.json()

    async def put_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """Full-replace PUT of the user config.

        ``body`` must be the entire UserData blob -- AIOStreams does
        not merge partial bodies. The response is the server-side
        state after the write (typically the same blob plus a freshly
        issued ``install_url``). On 4xx/5xx the wrapper translates to
        :class:`maestro.errors.MaestroException`; see :meth:`_do_request`.
        """
        log.info("aiostreams_put_config_request", body_keys=list(body.keys()))
        response = await self._request("PUT", json=body)
        return response.json()
