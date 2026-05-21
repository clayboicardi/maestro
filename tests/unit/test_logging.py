"""Logging setup tests."""

import json
import logging  # noqa: F401 - retained from spec; future tests may exercise stdlib bridge
import sys
from io import StringIO

import structlog

from maestro.logging import configure_logging


def test_configure_logging_defaults_to_json(monkeypatch: object) -> None:
    """Default format is JSON; output goes to stderr."""
    buf = StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    configure_logging(format="json", level="INFO")

    log = structlog.get_logger("test")
    log.info("event_name", key="value")

    output = buf.getvalue()
    parsed = json.loads(output.strip().splitlines()[-1])
    assert parsed["event"] == "event_name"
    assert parsed["key"] == "value"
    assert parsed["level"] == "info"


def test_configure_logging_console_format(monkeypatch: object) -> None:
    """Console format renders non-JSON, human-readable output."""
    buf = StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    configure_logging(format="console", level="DEBUG")

    log = structlog.get_logger("test")
    log.info("hello", who="world")

    output = buf.getvalue()
    assert "hello" in output
    assert "world" in output
    with pytest_raises_json():
        json.loads(output.strip().splitlines()[-1])


def pytest_raises_json():
    """Helper: assert text is NOT valid JSON."""
    import pytest  # noqa: PLC0415 - local import keeps helper self-contained

    return pytest.raises(json.JSONDecodeError)


def test_logging_writes_to_stderr_not_stdout(monkeypatch: object, capsys: object) -> None:
    """MCP stdio servers MUST NOT write to stdout. Logs go to stderr."""
    configure_logging(format="json", level="INFO")
    log = structlog.get_logger("test")
    log.warning("warning_event", detail="x")

    captured = capsys.readouterr()
    assert captured.out == "", "logs must not touch stdout"
    assert "warning_event" in captured.err
