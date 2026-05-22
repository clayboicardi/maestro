"""Staged-write helper for AIOStreams PUT-full-replace semantics.

AIOStreams config writes are PUT (not PATCH) — every write rewrites the
whole user blob. The ConfigStager caches the baseline on first read,
stacks mutations in memory, and flushes the merged result on save().
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

import structlog
from pydantic import BaseModel

log = structlog.get_logger("maestro.aiostreams.modify")

ConfigDict = dict[str, Any]
TransformFn = Callable[[ConfigDict], ConfigDict]


class PendingMutation(BaseModel):
    """Description of one staged change for read-out to Claude."""

    field: str
    from_: Any = None
    to: Any = None


class ConfigStager:
    """Manages staged AIOStreams config writes for one user session.

    Lifecycle:

    1. **Baseline cache** -- on first :meth:`modify` call (or any path
       that reads the staged config), :meth:`_ensure_baseline` fetches
       the current AIOStreams config via the injected ``get_config``
       callback and stores both the baseline (immutable reference) and
       a deep-copy working state (``_staged``). Subsequent
       :meth:`modify` calls operate on ``_staged`` without re-fetching.
    2. **Stage** -- each :meth:`modify` call applies a ``TransformFn``
       to a fresh deep-copy of ``_staged``, records a
       :class:`PendingMutation` describing the change, and replaces
       ``_staged`` with the result.
    3. **Flush** -- :meth:`save` issues a single PUT with ``_staged``
       and, on success, clears baseline/staged/mutations so the next
       :meth:`modify` re-fetches.

    Failure semantics:

    - If ``put_config`` raises during :meth:`save`, staged state
      survives. The caller may retry :meth:`save` without re-staging,
      or call :meth:`invalidate_cache` to drop state and start fresh
      against the latest server-side baseline.
    - :meth:`save` is idempotent for the no-mutations case: returns
      ``{"ok": True, "no_changes": True}`` without issuing a PUT.

    Concurrency: not thread-safe and not coroutine-safe. One stager
    per user session; FastMCP serializes tool invocations within a
    session.
    """

    def __init__(
        self,
        *,
        get_config: Callable[[], Awaitable[ConfigDict]],
        put_config: Callable[[ConfigDict], Awaitable[ConfigDict]],
    ) -> None:
        self._get_config = get_config
        self._put_config = put_config
        self._baseline: ConfigDict | None = None
        self._staged: ConfigDict | None = None
        self._mutations: list[PendingMutation] = []

    async def _ensure_baseline(self) -> ConfigDict:
        """Lazy-load the baseline + initialize ``_staged``.

        Called by any method that needs the current staged state. The
        baseline is the unmodified server-side snapshot; ``_staged`` is
        the working copy that accumulates mutations. Returns ``_staged``.
        """
        if self._baseline is None:
            self._baseline = await self._get_config()
            self._staged = deepcopy(self._baseline)
        assert self._staged is not None
        return self._staged

    async def modify(self, transform: TransformFn, *, field: str) -> PendingMutation:
        """Stage one transformation. Records before/after for the named field."""
        current = await self._ensure_baseline()
        before = _resolve_dotted(current, field)
        new_state = transform(deepcopy(current))
        after = _resolve_dotted(new_state, field)
        self._staged = new_state
        mutation = PendingMutation(field=field, from_=before, to=after)
        self._mutations.append(mutation)
        log.info("aiostreams_modify_staged", field=field, before=before, after=after)
        return mutation

    def pending_mutations(self) -> list[PendingMutation]:
        return list(self._mutations)

    async def save(self) -> dict[str, Any]:
        """PUT the staged config. Clears staging on success.

        Returns ``{"ok": True, "no_changes": True}`` if no mutations
        are staged (no PUT issued). Otherwise returns ``{"ok": True,
        **put_response, "changes_applied": [<field>, ...]}`` where
        ``changes_applied`` is the ordered list of mutation fields
        captured before the staging state is cleared.

        On ``_put_config`` raising, the exception propagates and staged
        state is preserved -- callers may retry :meth:`save` directly
        or call :meth:`invalidate_cache` to discard and restart against
        the latest server-side baseline.
        """
        if not self._mutations:
            return {"ok": True, "no_changes": True}
        assert self._staged is not None
        result = await self._put_config(self._staged)
        log.info("aiostreams_save_flushed", mutation_count=len(self._mutations))
        # Capture applied field list BEFORE clearing — plan text had the
        # comprehension after .clear(), which would have returned [].
        applied = [m.field for m in self._mutations]
        self._baseline = None
        self._staged = None
        self._mutations.clear()
        return {"ok": True, **result, "changes_applied": applied}

    def invalidate_cache(self) -> None:
        """Drop the cached baseline (e.g., after external write)."""
        self._baseline = None
        self._staged = None


def _resolve_dotted(d: ConfigDict, path: str) -> Any:
    """Walk a dot-delimited path through nested dicts; return None on miss.

    Note: a return of None is ambiguous — it can mean either "path not
    present" or "value at path is literally None". PendingMutation.from_
    and .to use this output for display only; callers needing the
    distinction must check membership directly.
    """
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur
