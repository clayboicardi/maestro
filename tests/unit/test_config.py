"""Config-loading tests."""

import pytest
from pydantic import ValidationError

from maestro.config import MaestroSettings


def test_settings_loads_from_env(monkeypatch: object) -> None:
    """All MAESTRO_* env vars populate the settings object."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "rd_test_token")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://aiostreams.elfhosted.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "uuid-1234")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "secret")

    s = MaestroSettings()

    assert s.rd_token.get_secret_value() == "rd_test_token"
    assert str(s.aiostreams_base_url) == "https://aiostreams.elfhosted.com/"
    assert s.aiostreams_uuid == "uuid-1234"
    assert s.aiostreams_password.get_secret_value() == "secret"


def test_settings_defaults(monkeypatch: object) -> None:
    """Optional settings have sane defaults."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    s = MaestroSettings()

    assert s.http_timeout_s == 15.0
    assert s.retry_attempts == 3
    assert s.compose_budget_s == 60.0
    assert s.compose_candidate_timeout_s == 10.0
    assert s.log_format == "json"
    assert str(s.torrentio_base_url) == "https://torrentio.strem.fun/"


def test_settings_missing_required(monkeypatch: object) -> None:
    """Missing required env vars raise validation error."""
    monkeypatch.delenv("MAESTRO_RD_TOKEN", raising=False)
    monkeypatch.delenv("MAESTRO_AIOSTREAMS_BASE_URL", raising=False)
    monkeypatch.delenv("MAESTRO_AIOSTREAMS_UUID", raising=False)
    monkeypatch.delenv("MAESTRO_AIOSTREAMS_PASSWORD", raising=False)

    with pytest.raises(ValidationError):
        MaestroSettings()


def test_password_redacted_in_repr(monkeypatch: object) -> None:
    """SecretStr ensures the password never appears in repr/str."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "super_secret_pw")

    s = MaestroSettings()

    assert "super_secret_pw" not in repr(s)
    assert "super_secret_pw" not in str(s)


def test_required_fields_locked() -> None:
    """Lock the required-field set for MaestroSettings.

    If a new required field is added, an existing one is given a default,
    or a required field is renamed, this test fails -- forcing intentional
    review of the configuration contract that operators rely on.
    """
    required = {name for name, field in MaestroSettings.model_fields.items() if field.is_required()}
    assert required == {
        "rd_token",
        "aiostreams_base_url",
        "aiostreams_uuid",
        "aiostreams_password",
    }
