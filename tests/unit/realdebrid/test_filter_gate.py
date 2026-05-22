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
    learner.record_strike("y.NOVELKW.mkv", "infringing_file")  # threshold = 2
    assert learner.predict_risk("z.NOVELKW.mkv") == RiskLevel.HIGH


def test_predict_risk_does_not_promote_below_threshold() -> None:
    """Single strike records evidence but does not actuate predict_risk."""
    learner = FilterGateLearner()
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")
    assert "NOVELKW" in learner.learned_keywords  # evidence recorded
    assert learner.learned_keywords["NOVELKW"].count == 1
    assert learner.predict_risk("y.NOVELKW.mkv") == RiskLevel.LOW  # but not promoted yet


def test_record_strike_skips_non_infringing_codes() -> None:
    """record_strike is a no-op for non-infringing_file error codes."""
    learner = FilterGateLearner()
    result = learner.record_strike("x.NOVELKW.mkv", "rate_limit")
    assert result == []
    assert "NOVELKW" not in learner.learned_keywords


def test_record_strike_skips_keywords_in_known() -> None:
    """Tokens already in KNOWN_KEYWORDS aren't re-promoted to learned."""
    learner = FilterGateLearner()
    result = learner.record_strike("file.WEB-DL.mkv", "infringing_file")
    assert result == []
    assert "WEB-DL" not in learner.learned_keywords


def test_matched_keywords_returns_all_substring_hits() -> None:
    """matched_keywords returns every KNOWN_KEYWORDS hit, not just the first."""
    learner = FilterGateLearner()
    matched = learner.matched_keywords("S01E03.WEB-DL.AMZN.mkv")
    assert set(matched) == {"WEB-DL", "AMZN"}


def test_record_strike_and_persist_writes_state_on_promotion(tmp_path: Path) -> None:
    """CF10 wrapper: a fresh strike on a novel token both records AND persists."""
    state_path = tmp_path / "state.json"
    learner = FilterGateLearner(state_path=state_path)
    promoted = learner.record_strike_and_persist("x.BUNDLEKW.mkv", "infringing_file")
    assert promoted == ["BUNDLEKW"]
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "BUNDLEKW" in data["learned_keywords"]


def test_record_strike_and_persist_skips_save_when_no_promotion(tmp_path: Path) -> None:
    """CF10 wrapper: non-infringing codes return [] and skip the disk write entirely."""
    state_path = tmp_path / "state.json"
    learner = FilterGateLearner(state_path=state_path)
    promoted = learner.record_strike_and_persist("x.NOVELKW.mkv", "rate_limit")
    assert promoted == []
    assert not state_path.exists()  # no I/O when nothing was promoted


def test_export_state_includes_known_and_learned() -> None:
    """export_state surfaces both the static baseline and runtime-learned keywords."""
    learner = FilterGateLearner()
    learner.record_strike("a.TESTKW.mkv", "infringing_file")
    learner.record_strike("b.TESTKW.mkv", "infringing_file")  # above threshold
    state = learner.export_state()
    assert "known_keywords" in state
    assert state["known_keywords"] == sorted(KNOWN_KEYWORDS)
    assert "learned_keywords" in state
    assert "TESTKW" in state["learned_keywords"]
    assert state["learned_keywords"]["TESTKW"]["count"] == 2
