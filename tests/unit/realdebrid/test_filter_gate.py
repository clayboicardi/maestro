"""Filter-gate learner tests."""

import json
from pathlib import Path

from maestro.realdebrid.filter_gate import (
    KNOWN_KEYWORDS,
    FilterGateLearner,
    RiskLevel,
)


def test_known_keywords_includes_may_2026_set() -> None:
    expected = {"WEB-DL", "WEBRip", "AMZN", "NF", "CR", "YTS", "RARBG", "[eztv]"}
    assert expected.issubset(KNOWN_KEYWORDS)


def test_predict_risk_high_when_known_keyword_present() -> None:
    learner = FilterGateLearner()
    assert learner.predict_risk("S01E03.WEB-DL.AMZN.mkv") == RiskLevel.HIGH


def test_predict_risk_low_when_no_keywords() -> None:
    learner = FilterGateLearner()
    assert learner.predict_risk("S01E03.BluRay.1080p.x264.mkv") == RiskLevel.LOW


def test_predict_risk_unknown_when_no_filename() -> None:
    learner = FilterGateLearner()
    assert learner.predict_risk("") == RiskLevel.UNKNOWN
    assert learner.predict_risk(None) == RiskLevel.UNKNOWN


def test_record_strike_promotes_keyword_to_learned() -> None:
    learner = FilterGateLearner()
    learner.record_strike(
        filename="weird.NEWCAM.2026.mkv",
        rd_error_code="infringing_file",
    )
    assert "NEWCAM" in learner.learned_keywords
    assert learner.learned_keywords["NEWCAM"].count >= 1


def test_record_strike_increments_evidence_count() -> None:
    learner = FilterGateLearner()
    learner.record_strike(filename="x.WEIRD.mkv", rd_error_code="infringing_file")
    learner.record_strike(filename="y.WEIRD.mkv", rd_error_code="infringing_file")
    assert learner.learned_keywords["WEIRD"].count == 2


def test_learner_persists_to_disk(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    learner = FilterGateLearner(state_path=state_path)
    learner.record_strike("x.NOVELTAG.mkv", "infringing_file")
    learner.save_state()
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "learned_keywords" in data
    assert "NOVELTAG" in data["learned_keywords"]


def test_learner_loads_from_disk(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {"learned_keywords": {"PRELOADED": {"count": 5, "first_seen": "2026-05-01T00:00:00Z"}}}
        )
    )
    learner = FilterGateLearner(state_path=state_path)
    learner.load_state()
    assert "PRELOADED" in learner.learned_keywords
    assert learner.learned_keywords["PRELOADED"].count == 5


def test_predict_risk_high_after_learning() -> None:
    learner = FilterGateLearner()
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")
    assert learner.predict_risk("y.NOVELKW.mkv") == RiskLevel.HIGH
