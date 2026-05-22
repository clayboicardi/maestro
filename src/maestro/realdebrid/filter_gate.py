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


class RiskLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LearnEvidence(BaseModel):
    count: int = 1
    first_seen: str = Field(default_factory=lambda: _dt.datetime.now(_dt.UTC).isoformat())


class FilterGateLearner:
    """Tracks runtime evidence + predicts risk for a given filename."""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self.state_path: Path | None = Path(state_path).expanduser() if state_path else None
        self.learned_keywords: dict[str, LearnEvidence] = {}

    def predict_risk(self, filename: str | None) -> RiskLevel:
        if not filename:
            return RiskLevel.UNKNOWN
        upper = filename.upper()
        for kw in KNOWN_KEYWORDS:
            if kw.upper() in upper:
                return RiskLevel.HIGH
        for kw in self.learned_keywords:
            if kw.upper() in upper:
                return RiskLevel.HIGH
        return RiskLevel.LOW

    def matched_keywords(self, filename: str | None) -> list[str]:
        if not filename:
            return []
        upper = filename.upper()
        matched: list[str] = []
        for kw in KNOWN_KEYWORDS:
            if kw.upper() in upper:
                matched.append(kw)
        for kw in self.learned_keywords:
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
        return {
            "known_keywords": sorted(KNOWN_KEYWORDS),
            "learned_keywords": {k: v.model_dump() for k, v in self.learned_keywords.items()},
        }
