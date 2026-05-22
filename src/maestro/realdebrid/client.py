"""Async httpx client for the Real-Debrid REST API.

API docs: https://api.real-debrid.com/
Auth: ``Authorization: Bearer <api_token>`` header.

Status-code mapping (raised as ``MaestroException`` wrapping a typed payload):

- ``401`` -> ``AuthError`` (non-transient; check ``MAESTRO_RD_TOKEN``)
- ``403`` -> ``UpstreamError`` (non-transient at this layer; the filter-gate
  policy layer in Phase 5 Task 5.4 will translate the ``infringing_file``
  body shape into ``FilterGateStrike``)
- ``429`` -> ``RateLimitError`` (transient; surfaces ``Retry-After``)
- ``5xx`` -> ``UpstreamError`` (transient; retried via ``AsyncRetrying``)
- Other ``4xx`` -> ``UpstreamError`` (non-transient)

Retry policy mirrors ``maestro.aiostreams.client``: only ``UpstreamError``
payloads are retried so 4xx-like failures (auth, rate limit) surface
immediately to the caller.
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

from maestro.errors import (
    AuthError,
    MaestroException,
    RateLimitError,
    UpstreamError,
)

log = structlog.get_logger("maestro.realdebrid.client")

BASE_URL = "https://api.real-debrid.com/rest/1.0"

# Real-Debrid REST API publishes ~250 req/min; default backoff after Retry-After
# is missing or unparsable.
_DEFAULT_RETRY_AFTER_S = 30.0


def _is_transient(exc: BaseException) -> bool:
    """Tenacity predicate: only transient UpstreamError payloads are retried.

    AuthError / RateLimitError are non-transient at this layer:
    - AuthError: never recovers without operator intervention
    - RateLimitError: caller should honor ``retry_after_s`` rather than
      hammering the endpoint inside the retry loop

    UpstreamError is split by the ``is_transient`` field on the payload:
    5xx defaults to True (worth retrying), 4xx is raised with False
    (auth/permissions/not-found do not recover from a retry).
    """
    return (
        isinstance(exc, MaestroException)
        and isinstance(exc.error, UpstreamError)
        and exc.error.is_transient
    )


class RDClient:
    """Async client for the Real-Debrid REST API.

    One instance is bound to one API token. Construct with explicit
    args (not a settings object) so per-call timeouts / retry counts can
    be overridden by callers without rebuilding ``MaestroSettings``.
    """

    def __init__(
        self,
        *,
        api_token: str,
        timeout_s: float = 15.0,
        retry_attempts: int = 3,
    ) -> None:
        self._token = api_token
        self._timeout_s = timeout_s
        self._retry_attempts = retry_attempts
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=httpx.Timeout(self._timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Single attempt: issue the request and translate status codes."""
        client = await self._get_client()
        url = f"{BASE_URL}{path}"
        try:
            response = await client.request(method, url, data=data)
        except httpx.HTTPError as e:
            raise MaestroException(
                UpstreamError(
                    domain="realdebrid",
                    message=f"HTTP error: {e}",
                )
            ) from e

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise MaestroException(
                AuthError(
                    domain="realdebrid",
                    suggestion="Check MAESTRO_RD_TOKEN",
                )
            )
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            retry_after_raw = response.headers.get("Retry-After", "")
            try:
                retry_after = float(retry_after_raw) if retry_after_raw else _DEFAULT_RETRY_AFTER_S
            except ValueError:
                retry_after = _DEFAULT_RETRY_AFTER_S
            raise MaestroException(
                RateLimitError(
                    domain="realdebrid",
                    retry_after_s=retry_after,
                    message="RD rate-limited (~250 req/min)",
                )
            )
        if HTTPStatus.INTERNAL_SERVER_ERROR <= response.status_code < 600:  # noqa: PLR2004
            raise MaestroException(
                UpstreamError(
                    domain="realdebrid",
                    message=f"RD {response.status_code}",
                )
            )
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            # 4xx other than 401/429 — non-transient. Include a short body
            # excerpt so the filter-gate layer (Task 5.4) can pattern-match
            # the ``infringing_file`` shape when 403 hits.
            body_excerpt = response.text[:200]
            raise MaestroException(
                UpstreamError(
                    domain="realdebrid",
                    message=f"RD {response.status_code}: {body_excerpt}",
                    is_transient=False,
                )
            )
        return response

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Retry-wrapped request honoring per-instance ``retry_attempts``."""
        response: httpx.Response | None = None
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_transient),
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(min=1, max=4),
            reraise=True,
        ):
            with attempt:
                response = await self._do_request(method, path, data=data)
        # AsyncRetrying guarantees response is set on success (else it reraises).
        assert response is not None
        return response

    async def get_user_info(self) -> dict[str, Any]:
        """GET /user -- premium status, expiration, etc."""
        log.info("rd_get_user_info_request")
        response = await self._request("GET", "/user")
        return response.json()

    async def check_cache(self, infohashes: list[str]) -> dict[str, dict[str, Any]]:
        """GET /torrents/instantAvailability/<hash>/<hash>/... — batch cache probe.

        Returns ``{hash: {"cached": bool, "files": <raw_entry_or_None>}}``.
        The ``files`` payload is the raw RD shape (a dict of variant maps when
        cached, ``None`` when not) so downstream selectors can pick a file
        without a second round trip.
        """
        if not infohashes:
            return {}
        path = "/torrents/instantAvailability/" + "/".join(infohashes)
        log.info("rd_check_cache_request", count=len(infohashes))
        response = await self._request("GET", path)
        raw = response.json()
        result: dict[str, dict[str, Any]] = {}
        for h in infohashes:
            entry = raw.get(h, [])
            if isinstance(entry, dict) and entry.get("rd"):
                result[h] = {"cached": True, "files": entry}
            else:
                result[h] = {"cached": False, "files": None}
        return result

    async def add_magnet(self, magnet: str) -> dict[str, Any]:
        """POST /torrents/addMagnet — returns ``{id, uri}`` for the new torrent."""
        log.info("rd_add_magnet_request")
        response = await self._request("POST", "/torrents/addMagnet", data={"magnet": magnet})
        return response.json()

    async def get_torrent_status(self, torrent_id: str) -> dict[str, Any]:
        """GET /torrents/info/<id> — current status, file list, progress."""
        log.info("rd_get_torrent_status_request", torrent_id=torrent_id)
        response = await self._request("GET", f"/torrents/info/{torrent_id}")
        return response.json()

    async def unrestrict_link(self, restricted_url: str) -> dict[str, Any]:
        """POST /unrestrict/link — convert an RD restricted URL into a CDN URL.

        The ``download`` field on the response is a playable URL.
        """
        log.info("rd_unrestrict_link_request")
        response = await self._request("POST", "/unrestrict/link", data={"link": restricted_url})
        return response.json()

    async def get_library(self) -> list[dict[str, Any]]:
        """GET /torrents — list torrents in the user's RD library."""
        log.info("rd_get_library_request")
        response = await self._request("GET", "/torrents")
        return response.json()
