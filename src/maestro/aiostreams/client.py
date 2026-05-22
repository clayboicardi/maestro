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
    """Tenacity predicate: only UpstreamError payloads are retried.

    AuthError/InstanceError are non-transient and must surface immediately.
    """
    return isinstance(exc, MaestroException) and isinstance(exc.error, UpstreamError)


class AIOStreamsClient:
    """Async client for one AIOStreams instance + one user account."""

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
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=httpx.Timeout(self._timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
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
        """Retry-wrapped request honoring per-instance retry_attempts."""
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
        """Fetch the current full UserData blob."""
        log.info("aiostreams_get_config_request")
        response = await self._request("GET")
        return response.json()

    async def put_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """Full-replace PUT of the user config."""
        log.info("aiostreams_put_config_request", body_keys=list(body.keys()))
        response = await self._request("PUT", json=body)
        return response.json()
