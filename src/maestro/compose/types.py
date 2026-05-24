"""Pydantic result types returned by :func:`maestro.compose.find_best_stream`.

Three classes:

- :class:`StreamMetadata` -- best-effort descriptor of the resolved stream
  (resolution, codec, language); fields are heuristically extracted from
  the addon's ``title`` blob and may all be ``None`` if the addon ships
  sparse metadata.
- :class:`Attempt` -- one candidate evaluation row; ``status`` is the
  Literal enumerator of recognized outcomes (success, filter-gate block,
  upstream 4xx, timeout, etc.). Several attempts accumulate per call
  because the composer retries candidates until success or budget.
- :class:`StreamResolution` -- top-level return type; either a success
  envelope (``url`` set, ``metadata`` populated) OR a structured failure
  envelope (``url=None``, ``suggestion`` populated, ``attempts``
  enumerating per-candidate diagnostics).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StreamMetadata(BaseModel):
    """Heuristically-extracted descriptors of the resolved stream.

    All fields are best-effort -- they're substring-matched from the
    addon-supplied ``title`` / ``name`` text blob, not parsed from a
    structured manifest. Any field may be ``None`` when the source
    addon ships sparse data or uses non-standard tags.

    - ``resolution``: one of ``4k``, ``1080p``, ``720p``, ``480p`` if
      present in the blob; otherwise ``None``.
    - ``codec``: one of ``x265``, ``x264``, ``av1``, ``hevc`` if
      present; otherwise ``None``.
    - ``language``: currently ``"English"`` if ``"english"`` appears
      in the blob, otherwise ``None``. Not a full language detector.
    - ``size_gb``: not currently extracted (always ``None`` in v1);
      reserved for a future size-parser pass.
    - ``group``: not currently extracted (always ``None`` in v1).
    - ``source_addon``: the addon family the stream originated from;
      currently always ``"aiostreams"`` since that's the only
      upstream the composer consults.
    """

    resolution: str | None = None
    codec: str | None = None
    language: str | None = None
    size_gb: float | None = None
    group: str | None = None
    source_addon: str | None = None


class Attempt(BaseModel):
    """One candidate evaluated during composition; multiple per call.

    The composer iterates through ranked candidates and appends an
    ``Attempt`` for each one inspected. The final ``Attempt`` with
    ``status="success"`` (if any) corresponds to the ``StreamResolution.url``
    returned to the caller; preceding attempts diagnose why earlier
    candidates were skipped or failed.

    ``status`` values (the Literal enumeration):

    - ``filter_gate_block``: candidate's filename hit the runtime
      filter-gate heuristic at ``HIGH`` risk and ``fallback_to_uncached``
      was ``False``, so the upstream call was skipped to avoid burning
      RD daily-cap quota on a likely-403 request.
    - ``unrestrict_4xx``: ``rd_unrestrict`` raised a wrapped
      :class:`MaestroException` whose body did not contain
      ``infringing_file``. Distinct from ``unrestrict_403_infringing``
      because the recovery path differs (no filter-gate strike learned).
      Note: the name is narrower than the actual catch-all -- this
      status is also emitted for HTTP 5xx, network errors, timeouts,
      and any other non-infringing ``MaestroException`` raised by
      ``rd_unrestrict``. Read it as "any non-filter-gate upstream
      failure" rather than literal HTTP 4xx. A future split into
      ``unrestrict_4xx`` / ``unrestrict_5xx`` / ``unrestrict_timeout``
      / ``unrestrict_network`` would tighten the taxonomy.
    - ``unrestrict_403_infringing``: ``rd_unrestrict`` raised with
      ``infringing_file`` in the error body. Triggers a side effect:
      :meth:`FilterGateLearner.record_strike_and_persist` learns the
      filename's tokens for future risk prediction.
    - ``timeout``: the composer's ``budget_s`` was exhausted before
      this candidate could be attempted. Appended once and the loop
      breaks; no per-attempt timeout exists in v1.
    - ``success``: candidate yielded a playable ``download`` URL; the
      composer returns immediately, so any ``success`` appears as the
      LAST attempt in ``StreamResolution.attempts``.
    - ``not_cached``: reserved in the Literal but NOT currently emitted
      by the composer (uncached candidates are filtered upstream of
      the per-candidate loop when ``require_cached=True``). Kept in
      the enumeration for future use; recipients should treat the
      absence as "doesn't appear in v1" rather than a hard contract.
    - ``no_url``: candidate had no ``url`` field on the addon response,
      OR ``rd_unrestrict`` returned without a ``download`` field.

    ``hash``, ``title``, ``filename`` are populated when known; absent
    when the upstream addon shipped sparse data or when the attempt
    type pre-dates filename extraction (``timeout``).
    """

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
    """Returned by :func:`find_best_stream`; success XOR structured failure.

    Two shapes, distinguished by whether ``url`` is set:

    - **Success**: ``url`` is the playable RD-unrestricted download
      URL; ``metadata`` is populated with heuristic descriptors;
      ``attempts`` ends with a ``status="success"`` row; ``suggestion``
      is ``None``.
    - **Structured failure**: ``url`` is ``None``; ``metadata`` is
      ``None``; ``attempts`` enumerates every candidate inspected (may
      be empty if Cinemeta returned no matches before any candidates
      existed); ``suggestion`` is a human-readable next-action hint
      naming the most likely cause.

    ``elapsed_ms`` is wall time from composer start to return, in
    integer milliseconds. Always populated (success or failure).

    ``source`` is the addon family the candidates originated from;
    currently always ``"aiostreams"``.

    The :attr:`ok` property is the convenience discriminator -- True
    iff ``url`` is set. Prefer it over ``result.url is not None`` at
    call sites.
    """

    url: str | None = None
    metadata: StreamMetadata | None = None
    source: str = "aiostreams"
    attempts: list[Attempt] = Field(default_factory=list)
    elapsed_ms: int = 0
    suggestion: str | None = None

    @property
    def ok(self) -> bool:
        """``True`` iff the composer resolved a playable URL.

        Use this discriminator at call sites rather than checking
        ``url is not None`` directly -- the contract is "success XOR
        structured failure," and the property name makes the intent
        explicit.
        """
        return self.url is not None
