"""Error taxonomy tests."""

import pytest

from maestro.errors import (
    AddonMalformed,
    AddonTimeout,
    AuthError,
    CompositionFailure,
    FilterGateStrike,
    InstanceError,
    MaestroError,
    MaestroException,
    NoStreamsAvailable,
    RateLimitError,
    SchemaError,
    TitleUnresolved,
    UpstreamError,
)


def test_maestro_error_has_required_shape() -> None:
    e = MaestroError(
        code="test_error",
        message="test",
        domain="test",
        suggestion=None,
        retry_after_s=None,
        is_transient=False,
    )
    assert e.code == "test_error"
    assert e.domain == "test"
    assert e.is_transient is False


def test_error_serializes_to_dict() -> None:
    e = AuthError(domain="aiostreams", suggestion="check creds")
    d = e.model_dump()
    assert d["code"] == "auth_error"
    assert d["domain"] == "aiostreams"
    assert d["suggestion"] == "check creds"
    assert d["is_transient"] is False


def test_rate_limit_error_carries_retry_after() -> None:
    e = RateLimitError(domain="realdebrid", retry_after_s=30.0)
    assert e.retry_after_s == 30.0
    assert e.is_transient is True


def test_filter_gate_strike_carries_keyword_evidence() -> None:
    e = FilterGateStrike(
        filename="S01E03.WEB-DL.AMZN.mkv",
        rd_error_code="infringing_file",
        learned_keywords=["WEB-DL", "AMZN"],
    )
    assert e.code == "filter_gate_strike"
    assert e.domain == "realdebrid"
    assert e.learned_keywords == ["WEB-DL", "AMZN"]


def test_composition_failure_carries_attempts() -> None:
    e = CompositionFailure(
        attempts=[
            {"hash": "abc", "status": "filter_gate_block", "filename": "x.mkv"},
            {"hash": "def", "status": "unrestrict_4xx", "error": "403"},
        ],
        suggestion="try fallback_to_uncached=True",
    )
    assert len(e.attempts) == 2
    assert e.suggestion == "try fallback_to_uncached=True"


def test_all_subclasses_set_their_own_code() -> None:
    """Each subclass must set its own code so consumers can switch on it."""
    assert AuthError(domain="x").code == "auth_error"
    assert InstanceError(domain="x").code == "instance_error"
    assert RateLimitError(domain="x").code == "rate_limit"
    assert SchemaError(domain="x").code == "schema_error"
    assert UpstreamError(domain="x").code == "upstream_error"
    assert AddonTimeout(domain="stremio").code == "addon_timeout"
    assert AddonMalformed(domain="stremio").code == "addon_malformed"
    assert FilterGateStrike(filename="x", rd_error_code="y").code == "filter_gate_strike"
    assert NoStreamsAvailable(domain="compose").code == "no_streams_available"
    assert TitleUnresolved(domain="compose").code == "title_unresolved"
    assert CompositionFailure(attempts=[]).code == "composition_failure"


def test_maestro_exception_wraps_error_payload() -> None:
    """MaestroException carries a MaestroError subclass for boundary unwrap."""
    err = AuthError(domain="aiostreams", suggestion="check creds")
    with pytest.raises(MaestroException) as exc_info:
        raise MaestroException(err)

    assert isinstance(exc_info.value.error, AuthError)
    assert exc_info.value.error.code == "auth_error"
    assert str(exc_info.value) == "Authentication failed"  # Exception.__str__ from message
