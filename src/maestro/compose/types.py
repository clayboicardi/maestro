"""Result types for find_best_stream."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StreamMetadata(BaseModel):
    resolution: str | None = None
    codec: str | None = None
    language: str | None = None
    size_gb: float | None = None
    group: str | None = None
    source_addon: str | None = None


class Attempt(BaseModel):
    """One candidate evaluated during composition."""

    hash: str | None = None
    title: str | None = None
    filename: str | None = None
    status: Literal[
        "filter_gate_block",
        "unrestrict_4xx",
        "unrestrict_403_infringing",
        "timeout",
        "success",
        "not_cached",
        "no_url",
    ]
    error: str | None = None


class StreamResolution(BaseModel):
    """Returned by find_best_stream — either success or structured failure."""

    url: str | None = None
    metadata: StreamMetadata | None = None
    source: str = "aiostreams"
    attempts: list[Attempt] = Field(default_factory=list)
    elapsed_ms: int = 0
    suggestion: str | None = None

    @property
    def ok(self) -> bool:
        return self.url is not None
