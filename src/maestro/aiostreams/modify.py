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
    """Manages staged AIOStreams config writes for one user session."""

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
        """PUT the staged config. Clears staging on success."""
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
