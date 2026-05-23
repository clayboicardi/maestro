"""May 2026 Real-Debrid filter-gate heuristic + runtime learning loop.

RD's parent company XT Network restructured in early May 2026 and began
blanket-blocking torrent filenames containing certain release-group tags
under EU DSA Article 16. The block applies post-cache-check:
``/torrents/instantAvailability`` reports the file cached, but
``/unrestrict/link`` returns 403 with error code ``infringing_file``.

We maintain:

- ``KNOWN_KEYWORDS``: static baseline from observed May 2026 behavior.
- ``LEARNED_KEYWORDS``: promoted at runtime when unrestrict 403s with
  ``infringing_file``.

State is persisted to ``~/.config/maestro/filter_gate_state.json`` so
learning survives server restarts.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger("maestro.realdebrid.filter_gate")


KNOWN_KEYWORDS: set[str] = {
    "WEB-DL",
    "WEBRip",
    "AMZN",
    "NF",
    "CR",
    "YTS",
    "RARBG",
    "[eztv]",
}

# Learned keywords influence predict_risk only after this many strikes.
# Guards against false-positive promotion of episode tags / codec markers
# (S01E03, DDP5, etc.) that share the regex shape but aren't filter-gate
# keywords. The threshold is intentionally low (2 strikes) because RD
# filter-gate keywords pattern as release-group tags that recur across
# many filenames -- a true filter-gate keyword should hit the threshold
# within a few candidate runs, while episode/codec markers stay below it
# because they don't repeat across different content. Tune upward only if
# false-positive rate climbs in production; tune downward only if real
# filter-gate keywords are taking too many strikes to surface.
LEARNED_PROMOTION_THRESHOLD: int = 2


class RiskLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LearnEvidence(BaseModel):
    count: int = 1
    first_seen: str = Field(default_factory=lambda: _dt.datetime.now(_dt.UTC).isoformat())


class FilterGateLearner:
    """Tracks runtime evidence + predicts risk for a given filename.

    Three-piece state:

    1. ``KNOWN_KEYWORDS`` (module-level constant) -- static baseline
       from observed May 2026 filter-gate behavior. Read-only after
       import; mutating this set is not the supported extension path.
    2. ``self.learned_keywords`` -- runtime-promoted candidates with
       per-keyword evidence (strike count + first-seen timestamp).
       Mutated via :meth:`record_strike` / :meth:`record_strike_and_persist`.
    3. ``self.state_path`` -- optional persistence target. When
       ``None`` (test wiring), the learner operates entirely in
       memory; :meth:`save_state` and :meth:`load_state` are silent
       no-ops.

    Side-effect contract:

    - :meth:`predict_risk` and :meth:`matched_keywords` are pure
      reads against the current ``learned_keywords`` state -- no
      mutation, no I/O, safe to call from any context.
    - :meth:`record_strike` mutates ``learned_keywords`` in memory.
      No persistence -- caller must invoke :meth:`save_state`
      explicitly OR use :meth:`record_strike_and_persist` to bundle.
    - :meth:`save_state` writes via atomic-replace (sibling ``.tmp``
      then ``Path.replace``) to avoid torn writes if the process
      dies mid-flush. Failure raises -- caller's choice whether to
      retry or proceed with in-memory state.
    - :meth:`load_state` is best-effort: corrupt JSON is logged and
      the in-memory state is left as-initialized (empty learned
      keywords). Caller will re-learn from subsequent strikes.

    Persistence guarantees:

    - **Atomic write**: yes (via ``Path.replace`` after writing the
      sibling ``.tmp`` file).
    - **Schema versioning**: NOT IMPLEMENTED in v1. The on-disk JSON
      shape is ``{"learned_keywords": {<keyword>: {<LearnEvidence>}}}``
      with no version field. State is recoverable from
      ``KNOWN_KEYWORDS`` + future strikes if the file is ever
      discarded due to a schema mismatch on a future maestro version.
    - **Concurrency**: single-process, single-writer assumed. There
      is no file lock; concurrent writers from two maestro instances
      sharing one ``filter_gate_state_path`` would race on the
      ``.tmp`` file and could lose strikes. Not a concern in
      stdio-MCP deployment but worth documenting for future HTTP/SSE
      transport migration.

    Concurrency within a single process is single-coroutine: FastMCP
    serializes tool invocations per session, and the learner is owned
    by one :class:`.tools.RDToolset` per server lifetime.
    """

    def __init__(self, state_path: Path | str | None = None) -> None:
        """Construct an in-memory learner; pass ``state_path`` to enable persistence.

        ``state_path`` accepts a :class:`pathlib.Path`, a string path
        (``~`` expanded), or ``None`` for memory-only mode. The path
        is normalized once at construction; subsequent ``save_state``/
        ``load_state`` calls reuse the stored value.
        """
        self.state_path: Path | None = Path(state_path).expanduser() if state_path else None
        self.learned_keywords: dict[str, LearnEvidence] = {}

    def predict_risk(self, filename: str | None) -> RiskLevel:
        """Return the predicted filter-gate risk for ``filename``.

        - ``None`` or empty filename -> :attr:`RiskLevel.UNKNOWN`
        - Any :data:`KNOWN_KEYWORDS` substring match (case-insensitive)
          -> :attr:`RiskLevel.HIGH`
        - Any promoted learned keyword (evidence count >=
          :data:`LEARNED_PROMOTION_THRESHOLD`) substring match ->
          :attr:`RiskLevel.HIGH`
        - Otherwise -> :attr:`RiskLevel.LOW`

        Note: :attr:`RiskLevel.MEDIUM` is reserved for future
        gradient-based heuristics; today the classifier is binary
        below the UNKNOWN guard. Pure read; no mutation.
        """
        if not filename:
            return RiskLevel.UNKNOWN
        upper = filename.upper()
        for kw in KNOWN_KEYWORDS:
            if kw.upper() in upper:
                return RiskLevel.HIGH
        for kw, evidence in self.learned_keywords.items():
            if evidence.count < LEARNED_PROMOTION_THRESHOLD:
                continue
            if kw.upper() in upper:
                return RiskLevel.HIGH
        return RiskLevel.LOW

    def matched_keywords(self, filename: str | None) -> list[str]:
        """Return the list of keywords matched against ``filename``.

        Mirrors :meth:`predict_risk` but enumerates all hits rather
        than stopping at the first. Useful for diagnostics in the
        MCP cache-check response (surfaces WHICH keywords triggered
        the risk classification). Promoted learned keywords appear
        AFTER the known keywords in match order. Pure read; no
        mutation.
        """
        if not filename:
            return []
        upper = filename.upper()
        matched: list[str] = []
        for kw in KNOWN_KEYWORDS:
            if kw.upper() in upper:
                matched.append(kw)
        for kw, evidence in self.learned_keywords.items():
            if evidence.count < LEARNED_PROMOTION_THRESHOLD:
                continue
            if kw.upper() in upper:
                matched.append(kw)
        return matched

    def record_strike(
        self,
        filename: str,
        rd_error_code: str,
        candidate_extractor: re.Pattern[str] | None = None,
    ) -> list[str]:
        """Promote likely keyword(s) from a 403 to ``LEARNED_KEYWORDS``.

        Extracts UPPERCASE alphanumeric tokens (4+ chars) from the
        filename that aren't already in ``KNOWN_KEYWORDS``, and records
        evidence for each as a possible new filter-gate keyword.

        Returns the list of newly-recorded keywords (for caller diagnostics).
        """
        if rd_error_code != "infringing_file":
            return []
        pattern = candidate_extractor or re.compile(r"\b([A-Z][A-Z0-9-]{3,})\b")
        promoted: list[str] = []
        for token in pattern.findall(filename):
            normalized = token.strip(".-_")
            if not normalized or normalized in KNOWN_KEYWORDS:
                continue
            evidence = self.learned_keywords.get(normalized)
            if evidence is None:
                self.learned_keywords[normalized] = LearnEvidence()
                promoted.append(normalized)
                log.info(
                    "filter_gate_keyword_learned",
                    keyword=normalized,
                    filename=filename,
                )
            else:
                evidence.count += 1
        return promoted

    def record_strike_and_persist(
        self,
        filename: str,
        rd_error_code: str,
    ) -> list[str]:
        """Convenience: ``record_strike`` then ``save_state`` in one call.

        Use this from production callers (Phase 7 composer onward) to avoid
        silent state loss when only the strike half of the pair is wired
        up. ``save_state`` is a no-op when ``state_path`` is None, so this
        is safe for both production and test wiring.

        Persistence semantics: persists whenever the underlying
        ``record_strike`` could have mutated state (i.e., ``rd_error_code
        == "infringing_file"``), regardless of whether a NEW keyword was
        promoted or an existing keyword's count was incremented. This
        matters for :data:`LEARNED_PROMOTION_THRESHOLD` transitions: a
        count-2 keyword that just became active in memory would otherwise
        regress to count-1 (below threshold, LOW-risk) on process restart,
        making the runtime-learning loop volatile across restarts.

        Returns the same value as ``record_strike`` -- the list of newly
        promoted keywords -- so callers can still log the diagnostics.
        """
        promoted = self.record_strike(filename, rd_error_code)
        if rd_error_code == "infringing_file":
            self.save_state()
        return promoted

    def save_state(self) -> None:
        """Persist learned keywords to ``state_path`` via atomic replace.

        Writes to a sibling ``.tmp`` file then ``os.replace``s to avoid
        torn writes if the process dies mid-flush. v1 omits schema_version
        and entry caps -- state is recoverable from KNOWN_KEYWORDS + future
        strikes if the file is ever discarded.
        """
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "learned_keywords": {k: v.model_dump() for k, v in self.learned_keywords.items()}
        }
        tmp_path = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2))
        tmp_path.replace(self.state_path)

    def load_state(self) -> None:
        """Best-effort load of persisted learned keywords.

        No-op if ``state_path`` is ``None`` (memory-only mode) or the
        file doesn't exist (first run, or state was discarded). On
        corrupt JSON, logs ``filter_gate_state_corrupt`` and leaves
        ``learned_keywords`` as initialized (empty). The learner will
        re-populate from future :meth:`record_strike` calls; no
        explicit reset or quarantine of the corrupt file (the next
        successful :meth:`save_state` overwrites it).

        Note: pydantic ``LearnEvidence.model_validate`` will raise on
        a schema mismatch (e.g., a future maestro version adds a
        required field). v1 has no schema_version handshake; if
        upstream maestro changes the on-disk shape, the load may
        raise -- callers (currently :func:`.tools.register_tools`)
        should treat the load as recoverable and fall back to an
        empty in-memory state.
        """
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text())
        except json.JSONDecodeError:
            log.warning("filter_gate_state_corrupt", path=str(self.state_path))
            return
        raw = data.get("learned_keywords", {})
        self.learned_keywords = {k: LearnEvidence.model_validate(v) for k, v in raw.items()}

    def export_state(self) -> dict[str, Any]:
        """Return a serializable snapshot of the current state.

        Returns ``{"known_keywords": <sorted_list>, "learned_keywords":
        {<keyword>: {<LearnEvidence>}}}``. Intended for diagnostic /
        introspection tools (Phase 6 diagnostics suite) -- NOT used by
        :meth:`save_state` (which writes only the ``learned_keywords``
        slice, since ``KNOWN_KEYWORDS`` is a static constant). Pure
        read; no I/O.
        """
        return {
            "known_keywords": sorted(KNOWN_KEYWORDS),
            "learned_keywords": {k: v.model_dump() for k, v in self.learned_keywords.items()},
        }
