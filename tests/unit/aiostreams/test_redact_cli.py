"""Tests for the public redact surface: `redact_config` + the redact CLI.

The fixture-refresh script (scripts/refresh_fixtures.sh) depends on these instead
of reaching into the private `_redact_secrets`.
"""

import json
from pathlib import Path

from maestro.aiostreams.redact import main
from maestro.aiostreams.tools import redact_config


def test_redact_config_public_wrapper_redacts() -> None:
    """redact_config is the documented public entry to the redactor."""
    out = redact_config({"tmdbApiKey": "leak_me", "presets": []})
    assert out["tmdbApiKey"] == "***REDACTED***"
    assert out["presets"] == []


def test_cli_redacts_file_to_file(tmp_path: Path) -> None:
    """`python -m maestro.aiostreams.redact <in> <out>` writes a redacted copy."""
    src = tmp_path / "in.json"
    dst = tmp_path / "out.json"
    src.write_text(
        json.dumps(
            {
                "tmdbApiKey": "secret_token",
                "services": [{"id": "rd", "credentials": {"apiKey": "rd_secret"}}],
                "presets": [],
            }
        )
    )
    rc = main([str(src), str(dst)])
    assert rc == 0
    result = json.loads(dst.read_text())
    assert result["tmdbApiKey"] == "***REDACTED***"
    assert result["services"][0]["credentials"] == {"apiKey": "***REDACTED***"}


def test_cli_wrong_arg_count_returns_2(tmp_path: Path) -> None:
    """Usage error (not 2 args) exits non-zero without writing output."""
    assert main([]) == 2
    assert main([str(tmp_path / "only_one.json")]) == 2
