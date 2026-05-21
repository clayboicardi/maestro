# Maestro v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Python MCP server (`clayworks-maestro-mcp`) that gives an AI agent programmatic control over a user's Stremio + Real-Debrid stack via AIOStreams CRUD, Torrentio URL config, RD REST integration with May 2026 filter-gate learning, Stremio addon protocol queries, and the `find_best_stream` composer.

**Architecture:** Single Python package, stdio MCP transport via FastMCP 3.x, six domain modules (aiostreams, torrentio, realdebrid, stremio, compose, diagnose). Auto-gen Pydantic from AIOStreams Zod via `zod-to-json-schema` → `datamodel-code-generator` pipeline with hand-overlay validators. All async via httpx. Per-tool MCP annotations (`readOnlyHint` / `destructiveHint` / `title`).

**Tech Stack:** Python 3.12 floor, FastMCP 3.x, uv 0.10.6+, ruff 0.15.14+, basedpyright 1.39.5+, httpx (async), pydantic v2 + pydantic-settings, structlog, pytest + pytest-asyncio + respx, tenacity, GitHub Actions CI.

**Spec reference:** `docs/specs/2026-05-21-maestro-design.md` (current HEAD `3bcac23`).

---

## File structure (locked at plan time)

```
maestro/
├── pyproject.toml                          [Phase 0]
├── README.md                               [Phase 0 skeleton, Phase 9 final]
├── LICENSE                                 [Phase 0]
├── CHANGELOG.md                            [Phase 0]
├── .gitignore                              [exists]
├── .python-version                         [Phase 0 — pins 3.12]
│
├── docs/
│   ├── specs/2026-05-21-maestro-design.md  [exists]
│   └── plans/2026-05-21-maestro-v1-implementation.md  [this file]
│
├── scripts/
│   ├── regen_aiostreams_schemas.sh         [Phase 2]
│   └── refresh_fixtures.sh                 [Phase 9]
│
├── .github/workflows/
│   ├── ci.yaml                             [Phase 0]
│   └── smoke.yaml                          [Phase 9]
│
├── src/maestro/
│   ├── __init__.py                         [Phase 1: __version__]
│   ├── server.py                           [Phase 1: FastMCP app + tool registration]
│   ├── config.py                           [Phase 1: pydantic-settings env loader]
│   ├── logging.py                          [Phase 1: structlog setup]
│   ├── errors.py                           [Phase 1: MaestroError + subclasses]
│   ├── annotations.py                      [Phase 1: ToolAnnotations helpers]
│   │
│   ├── aiostreams/
│   │   ├── __init__.py                     [Phase 3]
│   │   ├── client.py                       [Phase 3: AIOStreamsClient]
│   │   ├── schemas.py                      [Phase 2: hand-overlay validators]
│   │   ├── schemas_generated.py            [Phase 2: auto-gen Pydantic, gitignored from edits]
│   │   ├── modify.py                       [Phase 3: _modify(transform) staging helper]
│   │   ├── templates.py                    [Phase 3: Tamtaro/Vidhin fetch + merge]
│   │   └── tools.py                        [Phase 3: 21 MCP tool defs]
│   │
│   ├── torrentio/
│   │   ├── __init__.py                     [Phase 4]
│   │   ├── enums.py                        [Phase 4: extracted from filter.js]
│   │   ├── encoder.py                      [Phase 4: parse/build URL config]
│   │   └── tools.py                        [Phase 4: 5 MCP tool defs]
│   │
│   ├── realdebrid/
│   │   ├── __init__.py                     [Phase 5]
│   │   ├── client.py                       [Phase 5: RDClient async httpx]
│   │   ├── schemas.py                      [Phase 5: Pydantic for RD API]
│   │   ├── filter_gate.py                  [Phase 5: keyword heuristic + learning]
│   │   └── tools.py                        [Phase 5: 7 MCP tool defs]
│   │
│   ├── stremio/
│   │   ├── __init__.py                     [Phase 6]
│   │   ├── client.py                       [Phase 6: generic addon /stream caller]
│   │   └── tools.py                        [Phase 6: 6 MCP tool defs]
│   │
│   ├── compose/
│   │   ├── __init__.py                     [Phase 7]
│   │   └── find_best_stream.py             [Phase 7: composer + tool def]
│   │
│   └── diagnose/
│       ├── __init__.py                     [Phase 8]
│       ├── stack_health.py                 [Phase 8: addon health checks]
│       └── tools.py                        [Phase 8: 3 MCP tool defs]
│
└── tests/
    ├── conftest.py                         [Phase 1: env loader, shared fixtures]
    ├── unit/                               [tests mirror src/maestro/ structure]
    │   ├── aiostreams/
    │   ├── torrentio/
    │   ├── realdebrid/
    │   ├── stremio/
    │   ├── compose/
    │   └── diagnose/
    ├── integration/
    │   ├── aiostreams/fixtures/
    │   ├── realdebrid/fixtures/
    │   ├── stremio/fixtures/
    │   └── compose/fixtures/
    ├── smoke/                              [opt-in via MAESTRO_SMOKE=1]
    └── schema_fidelity/                    [Phase 2: pinned-tag hash check]
```

---

## Phase 0 — Project foundation

Goal: scaffold the Python project so CI passes on an empty package. No business logic.

### Task 0.1: Initialize uv project structure

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `src/maestro/__init__.py` (empty placeholder)

- [ ] **Step 1: Initialize uv project**

```bash
cd C:/Users/chawo/Projects/maestro
uv init --package --python 3.12 --name clayworks-maestro-mcp .
```

Expected: creates `pyproject.toml`, `.python-version`, `src/maestro/__init__.py`. The `--package` flag uses src-layout. The `--name` sets PyPI distribution name `clayworks-maestro-mcp`.

- [ ] **Step 2: Verify uv-generated structure**

```bash
ls -la src/maestro/
cat pyproject.toml
cat .python-version
```

Expected: `src/maestro/__init__.py` exists, `pyproject.toml` has `[project]` block with `name = "clayworks-maestro-mcp"`, `.python-version` reads `3.12`.

- [ ] **Step 3: Replace generated pyproject.toml with locked configuration**

Replace the content of `pyproject.toml` with:

```toml
[project]
name = "clayworks-maestro-mcp"
version = "0.1.0"
description = "MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks (AIOStreams config CRUD, Torrentio URL builder, RD integration, find_best_stream composer)"
readme = "README.md"
requires-python = ">=3.12"
license = { file = "LICENSE" }
authors = [
    { name = "Clay Haworth", email = "clayhaworth1@gmail.com" },
]
keywords = ["mcp", "stremio", "real-debrid", "aiostreams", "claude", "model-context-protocol"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
]
dependencies = [
    "fastmcp>=3.0,<4.0",
    "httpx>=0.27,<1.0",
    "pydantic>=2.7,<3.0",
    "pydantic-settings>=2.5,<3.0",
    "structlog>=24.0,<26.0",
    "tenacity>=8.2,<10.0",
]

[project.scripts]
maestro-mcp = "maestro.server:main"

[project.urls]
Repository = "https://github.com/clayboicardi/maestro"
Documentation = "https://github.com/clayboicardi/maestro#readme"
Issues = "https://github.com/clayboicardi/maestro/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/maestro"]

[dependency-groups]
dev = [
    "pytest>=8.3,<9.0",
    "pytest-asyncio>=0.24,<1.0",
    "pytest-cov>=5.0,<7.0",
    "respx>=0.21,<1.0",
    "ruff>=0.15,<1.0",
    "basedpyright>=1.39,<2.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E", "F", "W", "I", "N", "UP", "B", "A", "C4", "SIM", "RUF",
    "PT", "PTH", "ERA", "PL",
]
ignore = [
    "PLR0913",
    "E501",
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["PLR2004", "S101"]
"src/maestro/aiostreams/schemas_generated.py" = ["ALL"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.basedpyright]
include = ["src/maestro"]
exclude = [
    "**/__pycache__",
    "src/maestro/aiostreams/schemas_generated.py",
]
typeCheckingMode = "standard"
pythonVersion = "3.12"
reportMissingImports = "error"
reportMissingTypeStubs = "warning"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = [
    "smoke: live-network tests (opt-in via MAESTRO_SMOKE=1)",
    "schema_fidelity: AIOStreams upstream schema drift detector",
]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "-m", "not smoke",
]

[tool.coverage.run]
source = ["src/maestro"]
omit = [
    "src/maestro/aiostreams/schemas_generated.py",
    "src/maestro/__init__.py",
]

[tool.coverage.report]
fail_under = 75
show_missing = true
```

- [ ] **Step 4: Lock the deps and verify**

```bash
uv lock
uv sync
uv run python -c "import maestro; print('ok')"
```

Expected: `uv.lock` file created, all deps resolve, `import maestro` succeeds with output `ok`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .python-version src/maestro/__init__.py
git commit -m "chore: initialize uv project with locked toolchain"
```

### Task 0.2: Create LICENSE + CHANGELOG + README skeleton

**Files:**
- Create: `LICENSE`
- Create: `CHANGELOG.md`
- Create: `README.md`

- [ ] **Step 1: Write LICENSE (MIT)**

Write to `LICENSE`:

```
MIT License

Copyright (c) 2026 Clay Haworth / Clayworks

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Write CHANGELOG skeleton**

Write to `CHANGELOG.md`:

```markdown
# Changelog

All notable changes to Maestro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffold (Phase 0)
```

- [ ] **Step 3: Write README skeleton (final form lands in Phase 9)**

Write to `README.md`:

```markdown
# Maestro by Clayworks

> MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks.

**Status:** Pre-release (v0.1.0). See [docs/specs/2026-05-21-maestro-design.md](docs/specs/2026-05-21-maestro-design.md) for the design spec.

## What it does

Maestro is a local Python MCP server that lets an AI agent (Claude Code, Cursor, Claude Desktop) read, audit, and write configurations across a user's existing Stremio addons — primarily AIOStreams (Tamtaro SEL Setup) and Torrentio — and chain those primitives into a `find_best_stream` composer that resolves a single playable Real-Debrid URL per title query.

## Install

Coming in v1.0.0. See [docs/plans/2026-05-21-maestro-v1-implementation.md](docs/plans/2026-05-21-maestro-v1-implementation.md) for build progress.

## License

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 4: Commit**

```bash
git add LICENSE CHANGELOG.md README.md
git commit -m "docs: add LICENSE (MIT), CHANGELOG skeleton, README placeholder"
```

### Task 0.3: Configure CI workflow

**Files:**
- Create: `.github/workflows/ci.yaml`

- [ ] **Step 1: Write CI workflow**

Write to `.github/workflows/ci.yaml`:

```yaml
name: CI

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

jobs:
  lint-and-type:
    name: Lint + type check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --frozen
      - name: Ruff check
        run: uv run ruff check
      - name: Ruff format check
        run: uv run ruff format --check
      - name: Basedpyright
        run: uv run basedpyright

  test:
    name: Test (Python ${{ matrix.python }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install dependencies
        run: uv sync --frozen --python ${{ matrix.python }}
      - name: Pytest
        run: uv run pytest tests/unit tests/integration tests/schema_fidelity -v
```

- [ ] **Step 2: Verify CI workflow YAML is valid**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yaml'))" && echo "yaml ok"
```

Expected: `yaml ok` printed.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yaml
git commit -m "ci: add lint + multi-python test workflow"
```

### Task 0.4: Verify local toolchain runs clean

**Files:** none modified — just sanity check.

- [ ] **Step 1: Run ruff check**

```bash
uv run ruff check
```

Expected: `All checks passed!` (or no output and exit code 0).

- [ ] **Step 2: Run ruff format check**

```bash
uv run ruff format --check
```

Expected: `1 file already formatted` or similar.

- [ ] **Step 3: Run basedpyright**

```bash
uv run basedpyright
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Run pytest (no tests yet — should pass with 0 collected)**

```bash
uv run pytest
```

Expected: `no tests ran` exit 5 OR `collected 0 items`. Either way, no errors.

- [ ] **Step 5: No commit needed (sanity-check only)**

---

## Phase 1 — Core scaffolding

Goal: FastMCP server boots, loads config from env, logs structured, registers zero tools. Smoke-testable via `maestro-mcp` console script.

### Task 1.1: Set up structlog logging

**Files:**
- Create: `src/maestro/logging.py`
- Create: `tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/test_logging.py`:

```python
"""Logging setup tests."""

import json
import logging
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
    import pytest
    return pytest.raises(json.JSONDecodeError)


def test_logging_writes_to_stderr_not_stdout(monkeypatch: object, capsys: object) -> None:
    """MCP stdio servers MUST NOT write to stdout. Logs go to stderr."""
    configure_logging(format="json", level="INFO")
    log = structlog.get_logger("test")
    log.warning("warning_event", detail="x")

    captured = capsys.readouterr()
    assert captured.out == "", "logs must not touch stdout"
    assert "warning_event" in captured.err
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'maestro.logging'`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/logging.py`:

```python
"""Structured logging for Maestro.

stdio MCP servers MUST NOT write to stdout (it carries the protocol frames).
All log output goes to stderr.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog

LogFormat = Literal["json", "console"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def configure_logging(
    *,
    format: LogFormat = "json",
    level: LogLevel = "INFO",
) -> None:
    """Configure structlog + stdlib logging for the MCP server.

    Routes all output to stderr. JSON format for production (machine-readable);
    console format for human-facing dev runs.
    """
    log_level = getattr(logging, level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
        force=True,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_logging.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/logging.py tests/unit/test_logging.py
git commit -m "feat(logging): structlog setup writes JSON to stderr by default"
```

### Task 1.2: Add config loading via pydantic-settings

**Files:**
- Create: `src/maestro/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/test_config.py`:

```python
"""Config-loading tests."""

import pytest

from maestro.config import MaestroSettings


def test_settings_loads_from_env(monkeypatch: object) -> None:
    """All MAESTRO_* env vars populate the settings object."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "rd_test_token")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://aiostreams.elfhosted.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "uuid-1234")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "secret")

    s = MaestroSettings()

    assert s.rd_token == "rd_test_token"
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

    with pytest.raises(Exception):
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/config.py`:

```python
"""Maestro runtime configuration sourced from environment.

All env vars use the MAESTRO_* prefix. Required vars raise pydantic
ValidationError at load time. Secrets use SecretStr so they never leak
into logs or repr output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MaestroSettings(BaseSettings):
    """Server-wide settings, loaded once at startup."""

    model_config = SettingsConfigDict(
        env_prefix="MAESTRO_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    rd_token: SecretStr
    aiostreams_base_url: HttpUrl
    aiostreams_uuid: str
    aiostreams_password: SecretStr

    torrentio_base_url: HttpUrl = HttpUrl("https://torrentio.strem.fun")

    http_timeout_s: float = 15.0
    retry_attempts: int = 3
    compose_budget_s: float = 60.0
    compose_candidate_timeout_s: float = 10.0

    log_format: Literal["json", "console"] = "json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    filter_gate_state_path: str = "~/.config/maestro/filter_gate_state.json"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/config.py tests/unit/test_config.py
git commit -m "feat(config): env-sourced pydantic-settings with SecretStr for credentials"
```

### Task 1.3: Define error taxonomy

**Files:**
- Create: `src/maestro/errors.py`
- Create: `tests/unit/test_errors.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/test_errors.py`:

```python
"""Error taxonomy tests."""

import json

from maestro.errors import (
    AddonMalformed,
    AddonTimeout,
    AuthError,
    CompositionFailure,
    FilterGateStrike,
    InstanceError,
    MaestroError,
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/errors.py`:

```python
"""Error taxonomy for Maestro.

All tool errors are structured Pydantic models. Tools never raise to Claude;
they return either OK[T] or these Error[E] variants. Claude needs structured
info to decide next steps — stack traces are useless.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Domain = Literal["aiostreams", "torrentio", "realdebrid", "stremio", "compose", "diagnose"]


class MaestroError(BaseModel):
    """Base error shape returned by every tool."""

    code: str
    message: str = ""
    domain: str
    suggestion: str | None = None
    retry_after_s: float | None = None
    is_transient: bool = False


class AuthError(MaestroError):
    code: str = "auth_error"
    message: str = "Authentication failed"
    is_transient: bool = False


class InstanceError(MaestroError):
    code: str = "instance_error"
    message: str = "Instance not found or unreachable"
    is_transient: bool = False


class RateLimitError(MaestroError):
    code: str = "rate_limit"
    message: str = "Upstream rate limit hit"
    is_transient: bool = True


class SchemaError(MaestroError):
    code: str = "schema_error"
    message: str = "Schema mismatch — upstream may have changed"
    suggestion: str | None = "Run scripts/regen_aiostreams_schemas.sh and review the diff"
    is_transient: bool = False


class UpstreamError(MaestroError):
    code: str = "upstream_error"
    message: str = "Upstream returned a server error"
    is_transient: bool = True


class AddonTimeout(MaestroError):
    code: str = "addon_timeout"
    domain: str = "stremio"
    is_transient: bool = True


class AddonMalformed(MaestroError):
    code: str = "addon_malformed"
    domain: str = "stremio"
    is_transient: bool = False


class FilterGateStrike(MaestroError):
    code: str = "filter_gate_strike"
    domain: str = "realdebrid"
    message: str = "RD blocked file under May 2026 filter-gate"
    is_transient: bool = False

    filename: str
    rd_error_code: str
    learned_keywords: list[str] = Field(default_factory=list)


class NoStreamsAvailable(MaestroError):
    code: str = "no_streams_available"
    domain: str = "compose"


class TitleUnresolved(MaestroError):
    code: str = "title_unresolved"
    domain: str = "compose"
    suggestion: str | None = "Pass imdb_id directly if you have it"


class CompositionFailure(MaestroError):
    code: str = "composition_failure"
    domain: str = "compose"
    attempts: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_errors.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/errors.py tests/unit/test_errors.py
git commit -m "feat(errors): structured Pydantic error taxonomy across all domains"
```

### Task 1.4: Define ToolAnnotations helper

**Files:**
- Create: `src/maestro/annotations.py`
- Create: `tests/unit/test_annotations.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/test_annotations.py`:

```python
"""ToolAnnotations helper tests."""

from maestro.annotations import compute_annotation, read_only, destructive, pure_compute


def test_read_only_helper() -> None:
    a = read_only(title="Get Config")
    assert a.title == "Get Config"
    assert a.readOnlyHint is True
    assert a.destructiveHint is False


def test_destructive_helper() -> None:
    a = destructive(title="Set Languages")
    assert a.title == "Set Languages"
    assert a.readOnlyHint is False
    assert a.destructiveHint is True


def test_pure_compute_helper() -> None:
    a = pure_compute(title="Dedupe Streams")
    assert a.title == "Dedupe Streams"
    assert a.readOnlyHint is False
    assert a.destructiveHint is False


def test_compute_annotation_by_prefix() -> None:
    """Tool name → annotation kind heuristic for CI lint."""
    assert compute_annotation("aiostreams_get_config") == "read"
    assert compute_annotation("aiostreams_set_preferred_languages") == "write"
    assert compute_annotation("aiostreams_save") == "write"
    assert compute_annotation("aiostreams_apply_template") == "write"
    assert compute_annotation("stremio_dedupe_streams") == "compute"
    assert compute_annotation("torrentio_build_url") == "compute"
    assert compute_annotation("realdebrid_filter_gate_check") == "compute"
    assert compute_annotation("realdebrid_check_cache") == "read"
    assert compute_annotation("realdebrid_unrestrict_link") == "write"
    assert compute_annotation("find_best_stream") == "write"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_annotations.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/annotations.py`:

```python
"""MCP tool annotation helpers.

Anthropic's Connectors Directory requires every MCP tool to declare
`title` plus `readOnlyHint` or `destructiveHint`. We bake these
into helper factories so every tool registration site sets them
explicitly — no defaults that could regress.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

AnnotationKind = Literal["read", "write", "compute"]

_READ_PREFIXES = ("_get_", "_list_", "_check_", "_validate_", "_parse_")
_READ_EXACT = {"realdebrid_get_user_info", "stremio_query_addon",
               "stremio_query_addons_parallel", "stremio_get_manifest"}
_COMPUTE_EXACT = {
    "stremio_dedupe_streams", "stremio_filter_streams", "stremio_rank_streams",
    "torrentio_build_url", "torrentio_validate_config", "torrentio_list_providers",
    "torrentio_list_quality_filters", "realdebrid_filter_gate_check",
}


class ToolAnnotations(BaseModel):
    """Shape we pass into FastMCP's `@mcp.tool(annotations=...)`."""

    title: str
    readOnlyHint: bool = False
    destructiveHint: bool = False
    idempotentHint: bool = False
    openWorldHint: bool = True


def read_only(*, title: str, idempotent: bool = True) -> ToolAnnotations:
    return ToolAnnotations(title=title, readOnlyHint=True, idempotentHint=idempotent)


def destructive(*, title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, destructiveHint=True)


def pure_compute(*, title: str) -> ToolAnnotations:
    """Tools that don't touch external state — pure transforms."""
    return ToolAnnotations(title=title, openWorldHint=False, idempotentHint=True)


def compute_annotation(tool_name: str) -> AnnotationKind:
    """Heuristic mapping for CI lint to verify each tool sets the right annotation.

    Not used at runtime — runtime registration is explicit.
    """
    if tool_name in _COMPUTE_EXACT:
        return "compute"
    if tool_name in _READ_EXACT:
        return "read"
    if any(p in f"_{tool_name}_" for p in _READ_PREFIXES):
        return "read"
    if tool_name == "find_best_stream":
        return "write"
    return "write"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_annotations.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/annotations.py tests/unit/test_annotations.py
git commit -m "feat(annotations): ToolAnnotations helpers enforcing MCP review requirements"
```

### Task 1.5: Wire FastMCP server entry

**Files:**
- Create: `src/maestro/server.py`
- Modify: `src/maestro/__init__.py`
- Create: `tests/unit/test_server.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/test_server.py`:

```python
"""Server entry tests."""

import pytest

from maestro.server import create_server


def test_create_server_returns_fastmcp_instance(monkeypatch: object) -> None:
    """create_server() boots a FastMCP app with our identity."""
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    mcp = create_server()
    assert mcp.name == "maestro"


def test_create_server_registers_no_tools_initially() -> None:
    """Phase 1 server has zero tools registered — domain tools land in later phases."""
    pytest.importorskip("fastmcp")
    import os

    os.environ.setdefault("MAESTRO_RD_TOKEN", "x")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_BASE_URL", "https://x.com")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_UUID", "x")
    os.environ.setdefault("MAESTRO_AIOSTREAMS_PASSWORD", "x")

    from maestro.server import create_server

    mcp = create_server()
    tools = mcp._tool_manager.list_tools() if hasattr(mcp, "_tool_manager") else []
    assert len(tools) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/test_server.py -v
```

Expected: FAIL with `ImportError: cannot import name 'create_server' from 'maestro.server'`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/server.py`:

```python
"""Maestro MCP server entry point.

Boots a FastMCP stdio server. Tools land here via domain-module
register_* functions in later phases.
"""

from __future__ import annotations

import sys

import structlog
from fastmcp import FastMCP

from maestro.config import MaestroSettings
from maestro.logging import configure_logging


def create_server() -> FastMCP:
    """Construct and return the configured FastMCP app.

    Reads settings from env, configures logging, returns the bare app
    without tools. Domain register_* functions wire tools.
    """
    settings = MaestroSettings()
    configure_logging(format=settings.log_format, level=settings.log_level)

    log = structlog.get_logger("maestro.server")
    log.info(
        "server_starting",
        aiostreams_base_url=str(settings.aiostreams_base_url),
        torrentio_base_url=str(settings.torrentio_base_url),
        http_timeout_s=settings.http_timeout_s,
    )

    mcp = FastMCP(name="maestro")
    return mcp


def main() -> None:
    """Console-script entry: run the server over stdio."""
    try:
        mcp = create_server()
        mcp.run()
    except Exception as e:
        print(f"Maestro failed to start: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Modify `src/maestro/__init__.py` to:

```python
"""Maestro by Clayworks — MCP server for Stremio + Real-Debrid stack control."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/test_server.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/server.py src/maestro/__init__.py tests/unit/test_server.py
git commit -m "feat(server): FastMCP entry boots config + logging, zero tools yet"
```

### Task 1.6: Smoke-test the entry script

**Files:** none modified.

- [ ] **Step 1: Verify console script registered**

```bash
uv run python -c "from importlib.metadata import entry_points; print([e.name for e in entry_points(group='console_scripts') if 'maestro' in e.name])"
```

Expected: `['maestro-mcp']`.

- [ ] **Step 2: Boot the server with stdin closed to confirm clean startup**

```bash
MAESTRO_RD_TOKEN=test \
MAESTRO_AIOSTREAMS_BASE_URL=https://example.com \
MAESTRO_AIOSTREAMS_UUID=test \
MAESTRO_AIOSTREAMS_PASSWORD=test \
MAESTRO_LOG_FORMAT=console \
timeout 2 uv run maestro-mcp < /dev/null 2>&1 | head -5
```

Expected: a JSON or console log line containing `server_starting` then exit (no traceback, no stdout pollution). Exit code 124 from `timeout` is fine.

- [ ] **Step 3: No commit (sanity check only)**

---

## Phase 2 — AIOStreams schema generation pipeline

Goal: produce `src/maestro/aiostreams/schemas_generated.py` from upstream Zod source via `zod-to-json-schema` (npm) + `datamodel-code-generator` (Python). Add `schemas.py` hand-overlay for runtime refinements. Wire the schema-fidelity test.

### Task 2.1: Pin upstream AIOStreams version

**Files:**
- Create: `scripts/regen_aiostreams_schemas.sh`

- [ ] **Step 1: Identify the pin tag**

Look up the latest stable AIOStreams release tag — at plan-time v2.29.6 is Clay's installed version per the spec (line 32 of the handoff doc). Use that tag.

```bash
gh api repos/Viren070/AIOStreams/releases/tags/v2.29.6 2>&1 | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('tag_name'), d.get('target_commitish', '?'))"
```

Expected: `v2.29.6 <commit-sha>`. If the tag doesn't exist (release rename), fall back to `git ls-remote --tags https://github.com/Viren070/AIOStreams.git | grep v2 | tail -5` and pick the closest.

- [ ] **Step 2: Write the regen script**

Write to `scripts/regen_aiostreams_schemas.sh`:

```bash
#!/usr/bin/env bash
# Regenerate src/maestro/aiostreams/schemas_generated.py from upstream Zod.
#
# Pipeline:
#   1. fetch packages/core/src/db/schemas.ts at pinned tag
#   2. wrap it in a small extractor + run zod-to-json-schema via npx
#   3. pipe JSON Schema into datamodel-code-generator → Pydantic
#
# Bumping: edit PINNED_TAG, run this script, review diff, manually
# update overlay validators in schemas.py if refinement logic changed.

set -euo pipefail

PINNED_TAG="v2.29.6"
REPO_URL="https://github.com/Viren070/AIOStreams.git"
SCHEMA_PATH="packages/core/src/db/schemas.ts"
OUT_PY="src/maestro/aiostreams/schemas_generated.py"
WORK_DIR="$(mktemp -d)"

trap 'rm -rf "$WORK_DIR"' EXIT

echo "[regen] cloning ${REPO_URL}@${PINNED_TAG} into ${WORK_DIR}"
git clone --depth=1 --branch "$PINNED_TAG" "$REPO_URL" "$WORK_DIR/AIOStreams" >/dev/null 2>&1

SOURCE_TS="$WORK_DIR/AIOStreams/$SCHEMA_PATH"
if [[ ! -f "$SOURCE_TS" ]]; then
    echo "[regen] FATAL: ${SCHEMA_PATH} not found at tag ${PINNED_TAG}" >&2
    exit 1
fi

echo "[regen] preparing extractor"
mkdir -p "$WORK_DIR/extract"
cp "$SOURCE_TS" "$WORK_DIR/extract/schemas.ts"

cat > "$WORK_DIR/extract/package.json" <<'JSON'
{
  "name": "extract",
  "version": "0.0.0",
  "type": "module",
  "dependencies": {
    "zod": "^3.23.0",
    "zod-to-json-schema": "^3.23.0"
  }
}
JSON

cat > "$WORK_DIR/extract/extract.mjs" <<'JS'
import { zodToJsonSchema } from "zod-to-json-schema";
import * as mod from "./schemas.ts";

const exports = {};
for (const [name, value] of Object.entries(mod)) {
    if (value && typeof value === "object" && "_def" in value && "parse" in value) {
        try {
            exports[name] = zodToJsonSchema(value, { name, $refStrategy: "none" });
        } catch (e) {
            console.error(`skip ${name}: ${e.message}`);
        }
    }
}
console.log(JSON.stringify(exports, null, 2));
JS

cd "$WORK_DIR/extract"
echo "[regen] installing extractor deps"
npm install --silent --no-audit --no-fund

echo "[regen] running zod-to-json-schema"
node --experimental-strip-types extract.mjs > "$WORK_DIR/schemas.json" 2> "$WORK_DIR/extract.err" || {
    echo "[regen] FATAL: extraction failed" >&2
    cat "$WORK_DIR/extract.err" >&2
    exit 1
}

cd - >/dev/null

echo "[regen] generating Pydantic models via datamodel-code-generator"
uv run --with datamodel-code-generator datamodel-codegen \
    --input "$WORK_DIR/schemas.json" \
    --input-file-type jsonschema \
    --output "$OUT_PY" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --use-standard-collections \
    --use-union-operator \
    --field-constraints \
    --reuse-model \
    --use-schema-description \
    --capitalise-enum-members \
    --collapse-root-models \
    --custom-file-header "# AUTO-GENERATED from Viren070/AIOStreams@${PINNED_TAG}.
# DO NOT EDIT BY HAND — overwritten by scripts/regen_aiostreams_schemas.sh.
# Hand-overlay validators (runtime refinements that don't survive Zod→JSON-Schema
# round-trip) live in schemas.py."

echo "[regen] done. Wrote ${OUT_PY}"
echo "[regen] PINNED_TAG=${PINNED_TAG}"
```

- [ ] **Step 3: Make the script executable**

```bash
chmod +x scripts/regen_aiostreams_schemas.sh
ls -la scripts/regen_aiostreams_schemas.sh
```

Expected: line includes `-rwxr-xr-x` or equivalent executable bit.

- [ ] **Step 4: Run the script first time**

```bash
./scripts/regen_aiostreams_schemas.sh
```

Expected: prints `[regen] cloning...`, `[regen] installing extractor deps`, `[regen] running zod-to-json-schema`, `[regen] generating Pydantic models...`, `[regen] done.`. Creates `src/maestro/aiostreams/schemas_generated.py`.

If extraction fails (Zod refinements with dynamic `config.userLimits.*` lookups will throw), fall back: edit the script to wrap each Zod export in a try/catch that substitutes a permissive `z.string()` for unconvertible expressions. Document this as a known gotcha at the top of `schemas.py`.

- [ ] **Step 5: Smoke-import the generated module**

```bash
uv run python -c "from maestro.aiostreams import schemas_generated; print(len([n for n in dir(schemas_generated) if not n.startswith('_')]))"
```

Expected: a positive integer > 10 (number of generated model classes).

- [ ] **Step 6: Commit**

```bash
git add scripts/regen_aiostreams_schemas.sh src/maestro/aiostreams/schemas_generated.py
git commit -m "feat(aiostreams): Zod→Pydantic schema generation pipeline (pinned v2.29.6)"
```

### Task 2.2: Add hand-overlay schemas.py with runtime refinements

**Files:**
- Create: `src/maestro/aiostreams/__init__.py`
- Create: `src/maestro/aiostreams/schemas.py`
- Create: `tests/unit/aiostreams/__init__.py`
- Create: `tests/unit/aiostreams/test_schemas.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/__init__.py`: empty file.

Write to `tests/unit/aiostreams/test_schemas.py`:

```python
"""AIOStreams schema overlay tests."""

import pytest

from maestro.aiostreams import schemas


def test_user_data_re_exports_from_generated() -> None:
    """schemas.UserData re-exports from schemas_generated."""
    assert hasattr(schemas, "UserData")


def test_sel_expression_length_validator_rejects_oversize() -> None:
    """Runtime refinement: SEL expression > MAX_SEL_LENGTH chars is rejected."""
    too_long = "x" * (schemas.MAX_SEL_EXPRESSION_LENGTH + 1)
    with pytest.raises(ValueError, match="Stream expression exceeds maximum length"):
        schemas.validate_sel_expression(too_long)


def test_sel_expression_validator_accepts_normal_length() -> None:
    """Strings under the limit pass."""
    schemas.validate_sel_expression("typeof stream === 'movie'")


def test_formatter_template_validator_enforces_max_length() -> None:
    too_long = "x" * (schemas.MAX_FORMATTER_TEMPLATE_LENGTH + 1)
    with pytest.raises(ValueError, match="Formatter template exceeds maximum length"):
        schemas.validate_formatter_template(too_long)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/aiostreams/__init__.py`: empty file.

Write to `src/maestro/aiostreams/schemas.py`:

```python
"""Hand-overlay validators for AIOStreams schemas.

The auto-generated `schemas_generated.py` covers the structural shape but
strips Zod's runtime refinements (length checks that look up
`config.userLimits.*` at validate time). This module overlays those.

When AIOStreams bumps its `userLimits` defaults, update the constants
below. Read upstream:
https://github.com/Viren070/AIOStreams/blob/main/packages/core/src/config/index.ts
"""

from __future__ import annotations

from maestro.aiostreams import schemas_generated as _gen

UserData = _gen.UserData

MAX_SEL_EXPRESSION_LENGTH = 2000
MAX_FORMATTER_TEMPLATE_LENGTH = 4000


def validate_sel_expression(value: str) -> str:
    """Enforce upstream's `userLimits.sel.maxExpressionLength`.

    Raises ValueError when over limit so pydantic can surface the field
    in its standard validation error response.
    """
    if len(value) > MAX_SEL_EXPRESSION_LENGTH:
        raise ValueError(
            f"Stream expression exceeds maximum length of {MAX_SEL_EXPRESSION_LENGTH} characters."
        )
    return value


def validate_formatter_template(value: str) -> str:
    """Enforce upstream's `userLimits.maxFormatterTemplateLength`."""
    if len(value) > MAX_FORMATTER_TEMPLATE_LENGTH:
        raise ValueError(
            f"Formatter template exceeds maximum length of {MAX_FORMATTER_TEMPLATE_LENGTH} characters."
        )
    return value
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_schemas.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/__init__.py src/maestro/aiostreams/schemas.py tests/unit/aiostreams/__init__.py tests/unit/aiostreams/test_schemas.py
git commit -m "feat(aiostreams): overlay validators for SEL+formatter length refinements"
```

### Task 2.3: Add schema-fidelity test (CI canary)

**Files:**
- Create: `tests/schema_fidelity/__init__.py`
- Create: `tests/schema_fidelity/test_aiostreams_schema_pinned.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/schema_fidelity/__init__.py`: empty file.

Write to `tests/schema_fidelity/test_aiostreams_schema_pinned.py`:

```python
"""Detect upstream AIOStreams schema drift.

This test fetches the live schemas.ts at our pinned tag and compares
its SHA256 against the value we recorded at last regen. Drift = run
scripts/regen_aiostreams_schemas.sh and review the diff before bumping
the pin.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
import pytest

PINNED_TAG = "v2.29.6"
SCHEMA_URL = (
    f"https://raw.githubusercontent.com/Viren070/AIOStreams/"
    f"{PINNED_TAG}/packages/core/src/db/schemas.ts"
)
PINNED_SHA_FILE = Path(__file__).parent / "aiostreams_schema.sha256"


pytestmark = pytest.mark.schema_fidelity


@pytest.mark.skipif(
    os.environ.get("CI") != "true" and not PINNED_SHA_FILE.exists(),
    reason="Pinned SHA file missing — run pytest with --update-schema-pin to seed",
)
def test_upstream_schema_matches_pinned_sha() -> None:
    """Live schemas.ts at PINNED_TAG must match the recorded SHA256."""
    response = httpx.get(SCHEMA_URL, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    live_sha = hashlib.sha256(response.content).hexdigest()

    expected_sha = PINNED_SHA_FILE.read_text().strip()
    assert live_sha == expected_sha, (
        f"Upstream schema drift detected at tag {PINNED_TAG}.\n"
        f"  expected SHA: {expected_sha}\n"
        f"  live SHA:     {live_sha}\n"
        f"Run scripts/regen_aiostreams_schemas.sh and review the diff."
    )


def test_pinned_sha_file_exists_in_ci() -> None:
    """The recorded SHA file must be committed for CI to enforce drift detection."""
    if os.environ.get("CI") == "true":
        assert PINNED_SHA_FILE.exists(), (
            "tests/schema_fidelity/aiostreams_schema.sha256 missing in CI. "
            "Seed it by running once locally then commit the file."
        )
```

- [ ] **Step 2: Seed the pinned SHA file**

```bash
curl -sL "https://raw.githubusercontent.com/Viren070/AIOStreams/v2.29.6/packages/core/src/db/schemas.ts" | sha256sum | awk '{print $1}' > tests/schema_fidelity/aiostreams_schema.sha256
cat tests/schema_fidelity/aiostreams_schema.sha256
```

Expected: a 64-char hex SHA256 on one line.

- [ ] **Step 3: Run test to verify it passes**

```bash
uv run pytest tests/schema_fidelity/ -v
```

Expected: 2 tests PASS (or 1 PASS + 1 SKIP if CI env var not set).

- [ ] **Step 4: Commit**

```bash
git add tests/schema_fidelity/
git commit -m "test(schema_fidelity): SHA-pinned drift detector for AIOStreams upstream"
```

---

## Phase 3 — AIOStreams domain (client + 21 tools)

Goal: implement the AIOStreams CRUD surface. HTTP client + staged-write helper + 21 MCP tools registered. AIOStreams PUT is full-replace, so `_modify(transform)` stages mutations in memory and `aiostreams_save()` is the only thing that hits the network for writes.

### Task 3.1: AIOStreamsClient — auth + GET /api/v1/user

**Files:**
- Create: `src/maestro/aiostreams/client.py`
- Create: `tests/unit/aiostreams/test_client.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_client.py`:

```python
"""AIOStreamsClient tests (respx-mocked)."""

import httpx
import pytest
import respx

from maestro.aiostreams.client import AIOStreamsClient
from maestro.errors import AuthError, InstanceError, SchemaError


@pytest.fixture
def client() -> AIOStreamsClient:
    return AIOStreamsClient(
        base_url="https://aiostreams.elfhosted.com",
        uuid="user-uuid-1234",
        password="secret-pw",
        timeout_s=5.0,
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_config_happy_path(client: AIOStreamsClient) -> None:
    respx.get(
        "https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234"
    ).mock(
        return_value=httpx.Response(200, json={"filters": {}, "addons": [], "services": []})
    )
    cfg = await client.get_config()
    assert "filters" in cfg
    assert "addons" in cfg


@respx.mock
@pytest.mark.asyncio
async def test_get_config_401_raises_auth_error(client: AIOStreamsClient) -> None:
    respx.get(
        "https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234"
    ).mock(return_value=httpx.Response(401, json={"error": "unauthorized"}))
    with pytest.raises(AuthError):
        await client.get_config()


@respx.mock
@pytest.mark.asyncio
async def test_get_config_404_raises_instance_error(client: AIOStreamsClient) -> None:
    respx.get(
        "https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(InstanceError):
        await client.get_config()


@respx.mock
@pytest.mark.asyncio
async def test_get_config_500_retries_then_raises(client: AIOStreamsClient) -> None:
    """5xx triggers retry (3 attempts) then surfaces UpstreamError."""
    from maestro.errors import UpstreamError

    route = respx.get(
        "https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234"
    ).mock(return_value=httpx.Response(500))

    with pytest.raises(UpstreamError):
        await client.get_config()
    assert route.call_count >= 1


@respx.mock
@pytest.mark.asyncio
async def test_put_config_round_trip(client: AIOStreamsClient) -> None:
    body = {"filters": {"preferred_languages": ["English"]}, "addons": []}
    respx.put(
        "https://aiostreams.elfhosted.com/api/v1/user/user-uuid-1234"
    ).mock(return_value=httpx.Response(200, json={"ok": True}))

    result = await client.put_config(body)
    assert result == {"ok": True}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'maestro.aiostreams.client'`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/aiostreams/client.py`:

```python
"""Async httpx client for AIOStreams /api/v1/user CRUD.

Auth: HTTP Basic with `<uuid>:<password>` since AIOStreams v2.30.
Endpoints: GET / PUT / DELETE under `/api/v1/user/<uuid>`.

PUT is full-replace, not PATCH — callers must read-modify-write.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from maestro.errors import AuthError, InstanceError, UpstreamError

log = structlog.get_logger("maestro.aiostreams.client")


class AIOStreamsClient:
    """Async client for one AIOStreams instance + one user account."""

    def __init__(
        self,
        *,
        base_url: str,
        uuid: str,
        password: str,
        timeout_s: float = 15.0,
        retry_attempts: int = 3,
    ) -> None:
        self._uuid = uuid
        self._base = base_url.rstrip("/")
        self._user_url = f"{self._base}/api/v1/user/{uuid}"
        self._auth = httpx.BasicAuth(uuid, password)
        self._timeout_s = timeout_s
        self._retry_attempts = retry_attempts
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=httpx.Timeout(self._timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type(UpstreamError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=4),
        reraise=True,
    )
    async def _request(self, method: str, json: dict[str, Any] | None = None) -> httpx.Response:
        client = await self._get_client()
        try:
            response = await client.request(method, self._user_url, json=json)
        except httpx.HTTPError as e:
            raise UpstreamError(
                domain="aiostreams",
                message=f"HTTP error: {e}",
            ) from e

        if response.status_code == 401:
            raise AuthError(
                domain="aiostreams",
                suggestion="Check MAESTRO_AIOSTREAMS_UUID and MAESTRO_AIOSTREAMS_PASSWORD",
            )
        if response.status_code == 404:
            raise InstanceError(
                domain="aiostreams",
                suggestion="Verify MAESTRO_AIOSTREAMS_BASE_URL + MAESTRO_AIOSTREAMS_UUID exist",
            )
        if 500 <= response.status_code < 600:
            raise UpstreamError(
                domain="aiostreams",
                message=f"upstream {response.status_code}",
            )
        return response

    async def get_config(self) -> dict[str, Any]:
        """Fetch the current full UserData blob."""
        log.info("aiostreams_get_config_request")
        response = await self._request("GET")
        return response.json()

    async def put_config(self, body: dict[str, Any]) -> dict[str, Any]:
        """Full-replace PUT of the user config."""
        log.info("aiostreams_put_config_request", body_keys=list(body.keys()))
        response = await self._request("PUT", json=body)
        return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_client.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/client.py tests/unit/aiostreams/test_client.py
git commit -m "feat(aiostreams): async client with Basic auth, tenacity retries, structured errors"
```

### Task 3.2: Staged-write helper `_modify(transform)`

**Files:**
- Create: `src/maestro/aiostreams/modify.py`
- Create: `tests/unit/aiostreams/test_modify.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_modify.py`:

```python
"""Staged-write helper tests."""

from typing import Any

import pytest

from maestro.aiostreams.modify import ConfigStager, PendingMutation


@pytest.mark.asyncio
async def test_modify_stages_in_memory_not_remote() -> None:
    """A modify call does not PUT — it caches the transformed config."""
    fetches = 0

    async def fake_get_config() -> dict[str, Any]:
        nonlocal fetches
        fetches += 1
        return {"filters": {"preferred_languages": []}, "addons": []}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("PUT must not fire during modify")

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    mutation = await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )

    assert isinstance(mutation, PendingMutation)
    assert mutation.field == "filters.preferred_languages"
    assert mutation.to == ["English"]
    assert fetches == 1


@pytest.mark.asyncio
async def test_modify_caches_baseline_across_calls() -> None:
    """Multiple modifies stack on the same baseline fetch."""
    fetches = 0

    async def fake_get_config() -> dict[str, Any]:
        nonlocal fetches
        fetches += 1
        return {"filters": {"preferred_languages": [], "excluded_resolutions": []}}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )
    await stager.modify(
        lambda cfg: {**cfg, "filters": {**cfg["filters"], "excluded_resolutions": ["480p"]}},
        field="filters.excluded_resolutions",
    )

    assert fetches == 1
    pending = stager.pending_mutations()
    assert len(pending) == 2


@pytest.mark.asyncio
async def test_save_flushes_via_put_and_clears_staging() -> None:
    """save() calls PUT with the merged staged config then clears staging."""
    put_bodies: list[dict[str, Any]] = []

    async def fake_get_config() -> dict[str, Any]:
        return {"filters": {"preferred_languages": []}}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        put_bodies.append(body)
        return {"ok": True, "install_url": "stremio://x"}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    await stager.modify(
        lambda cfg: {**cfg, "filters": {"preferred_languages": ["English"]}},
        field="filters.preferred_languages",
    )
    result = await stager.save()

    assert len(put_bodies) == 1
    assert put_bodies[0]["filters"]["preferred_languages"] == ["English"]
    assert result["ok"] is True
    assert stager.pending_mutations() == []


@pytest.mark.asyncio
async def test_save_with_no_pending_is_noop() -> None:
    """Calling save() with nothing staged does not PUT."""
    put_bodies: list[dict[str, Any]] = []

    async def fake_get_config() -> dict[str, Any]:
        return {}

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        put_bodies.append(body)
        return {}

    stager = ConfigStager(get_config=fake_get_config, put_config=fake_put_config)
    result = await stager.save()
    assert result == {"ok": True, "no_changes": True}
    assert put_bodies == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_modify.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/aiostreams/modify.py`:

```python
"""Staged-write helper for AIOStreams PUT-full-replace semantics.

AIOStreams config writes are PUT (not PATCH) — every write rewrites the
whole user blob. The ConfigStager caches the baseline on first read,
stacks mutations in memory, and flushes the merged result on save().
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

import structlog
from pydantic import BaseModel

log = structlog.get_logger("maestro.aiostreams.modify")

ConfigDict = dict[str, Any]
TransformFn = Callable[[ConfigDict], ConfigDict]


class PendingMutation(BaseModel):
    """Description of one staged change for read-out to Claude."""

    field: str
    from_: Any = None
    to: Any = None

    model_config = {"populate_by_name": True}


class ConfigStager:
    """Manages staged AIOStreams config writes for one user session."""

    def __init__(
        self,
        *,
        get_config: Callable[[], Awaitable[ConfigDict]],
        put_config: Callable[[ConfigDict], Awaitable[ConfigDict]],
    ) -> None:
        self._get_config = get_config
        self._put_config = put_config
        self._baseline: ConfigDict | None = None
        self._staged: ConfigDict | None = None
        self._mutations: list[PendingMutation] = []

    async def _ensure_baseline(self) -> ConfigDict:
        if self._baseline is None:
            self._baseline = await self._get_config()
            self._staged = deepcopy(self._baseline)
        assert self._staged is not None
        return self._staged

    async def modify(self, transform: TransformFn, *, field: str) -> PendingMutation:
        """Stage one transformation. Records before/after for the named field."""
        current = await self._ensure_baseline()
        before = _resolve_dotted(current, field)
        new_state = transform(deepcopy(current))
        after = _resolve_dotted(new_state, field)
        self._staged = new_state
        mutation = PendingMutation(field=field, from_=before, to=after)
        self._mutations.append(mutation)
        log.info("aiostreams_modify_staged", field=field, before=before, after=after)
        return mutation

    def pending_mutations(self) -> list[PendingMutation]:
        return list(self._mutations)

    async def save(self) -> dict[str, Any]:
        """PUT the staged config. Clears staging on success."""
        if not self._mutations:
            return {"ok": True, "no_changes": True}
        assert self._staged is not None
        result = await self._put_config(self._staged)
        log.info("aiostreams_save_flushed", mutation_count=len(self._mutations))
        self._baseline = None
        self._staged = None
        self._mutations.clear()
        return {"ok": True, **result, "changes_applied": [m.field for m in self._mutations]}

    def invalidate_cache(self) -> None:
        """Drop the cached baseline (e.g., after external write)."""
        self._baseline = None
        self._staged = None


def _resolve_dotted(d: ConfigDict, path: str) -> Any:
    """Walk a dot-delimited path through nested dicts; return None on miss."""
    cur: Any = d
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_modify.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/modify.py tests/unit/aiostreams/test_modify.py
git commit -m "feat(aiostreams): ConfigStager — staged writes + PUT-on-save semantics"
```

### Task 3.3: AIOStreams read tools (8 tools, one task)

**Files:**
- Create: `src/maestro/aiostreams/tools.py` (partial — reads only)
- Create: `tests/unit/aiostreams/test_tools_read.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_tools_read.py`:

```python
"""Read-tool tests for AIOStreams domain (with secret redaction check)."""

from typing import Any

import pytest

from maestro.aiostreams.tools import (
    AIOStreamsToolset,
)


@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "services": [
            {"id": "realdebrid", "credential": "rd_token_real_secret", "enabled": True}
        ],
        "addons": [
            {"name": "Comet", "enabled": True, "manifestUrl": "https://comet.example/manifest.json"},
            {"name": "MediaFusion", "enabled": False, "manifestUrl": "https://mf.example/manifest.json"},
        ],
        "filters": {"preferred_languages": ["English"], "excluded_resolutions": ["480p"]},
        "sortCriteria": [{"key": "cached", "direction": "desc"}],
        "presets": {"active": "tamtaro_recommended"},
        "statistics": {"enabled": True, "show_errors": True},
    }


@pytest.fixture
def toolset(sample_config: dict[str, Any]) -> AIOStreamsToolset:
    async def fake_get_config() -> dict[str, Any]:
        return sample_config

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_get_config_redacts_credentials_by_default(toolset: AIOStreamsToolset) -> None:
    result = await toolset.get_config(include_secrets=False)
    assert result["services"][0]["credential"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_get_config_can_include_secrets_when_explicit(toolset: AIOStreamsToolset) -> None:
    result = await toolset.get_config(include_secrets=True)
    assert result["services"][0]["credential"] == "rd_token_real_secret"


@pytest.mark.asyncio
async def test_get_services_returns_redacted_list(toolset: AIOStreamsToolset) -> None:
    services = await toolset.get_services()
    assert services[0]["credential"] == "***REDACTED***"
    assert services[0]["id"] == "realdebrid"


@pytest.mark.asyncio
async def test_get_addons_returns_full_list(toolset: AIOStreamsToolset) -> None:
    addons = await toolset.get_addons()
    assert len(addons) == 2
    assert addons[0]["name"] == "Comet"
    assert addons[1]["enabled"] is False


@pytest.mark.asyncio
async def test_get_filters_returns_filter_block(toolset: AIOStreamsToolset) -> None:
    filters = await toolset.get_filters()
    assert filters["preferred_languages"] == ["English"]


@pytest.mark.asyncio
async def test_get_sort_order_returns_criteria(toolset: AIOStreamsToolset) -> None:
    sort_order = await toolset.get_sort_order()
    assert sort_order == [{"key": "cached", "direction": "desc"}]


@pytest.mark.asyncio
async def test_get_active_template(toolset: AIOStreamsToolset) -> None:
    name = await toolset.get_active_template()
    assert name == "tamtaro_recommended"


@pytest.mark.asyncio
async def test_get_statistics(toolset: AIOStreamsToolset) -> None:
    stats = await toolset.get_statistics()
    assert stats["enabled"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_tools_read.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/aiostreams/tools.py`:

```python
"""AIOStreams MCP tool definitions (21 tools)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

import structlog

from maestro.aiostreams.modify import ConfigStager, PendingMutation

log = structlog.get_logger("maestro.aiostreams.tools")

REDACTED = "***REDACTED***"


def _redact_secrets(config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(config)
    for service in out.get("services", []):
        if "credential" in service:
            service["credential"] = REDACTED
    return out


class AIOStreamsToolset:
    """Holds the stager + exposes one method per MCP tool.

    The server module wires each method to a FastMCP @tool registration
    with the right annotations.
    """

    def __init__(
        self,
        *,
        get_config: Callable[[], Awaitable[dict[str, Any]]],
        put_config: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None:
        self._stager = ConfigStager(get_config=get_config, put_config=put_config)
        self._get_config = get_config

    async def get_config(self, *, include_secrets: bool = False) -> dict[str, Any]:
        """Fetch the entire AIOStreams config. Secrets redacted unless explicit."""
        cfg = await self._get_config()
        if not include_secrets:
            cfg = _redact_secrets(cfg)
            log.info("aiostreams_get_config_redacted")
        else:
            log.warning("aiostreams_get_config_with_secrets")
        return cfg

    async def get_services(self) -> list[dict[str, Any]]:
        """List debrid services + priority order (credentials redacted)."""
        cfg = await self._get_config()
        return _redact_secrets(cfg).get("services", [])

    async def get_addons(self) -> list[dict[str, Any]]:
        """List aggregated addons with enabled state + URLs."""
        cfg = await self._get_config()
        return cfg.get("addons", [])

    async def get_filters(self) -> dict[str, Any]:
        """Return current filter settings (language, quality, resolution, etc)."""
        cfg = await self._get_config()
        return cfg.get("filters", {})

    async def get_sort_order(self) -> list[dict[str, Any]]:
        """Return current sort hierarchy."""
        cfg = await self._get_config()
        return cfg.get("sortCriteria", [])

    async def get_active_template(self) -> str:
        """Return active template name, or 'Custom' if hand-edited."""
        cfg = await self._get_config()
        return cfg.get("presets", {}).get("active", "Custom")

    async def get_statistics(self) -> dict[str, Any]:
        """Return Show Statistics & Errors block for dud-rate debugging."""
        cfg = await self._get_config()
        return cfg.get("statistics", {})

    async def get_template_list(self) -> list[dict[str, Any]]:
        """Return available templates (Tamtaro variants + community).

        Phase 3 stub — implementation in Task 3.4 (templates.py).
        """
        return []
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_tools_read.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/tools.py tests/unit/aiostreams/test_tools_read.py
git commit -m "feat(aiostreams): 8 read tools with secret redaction"
```

### Task 3.4: Tamtaro/Vidhin template fetcher

**Files:**
- Create: `src/maestro/aiostreams/templates.py`
- Create: `tests/unit/aiostreams/test_templates.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_templates.py`:

```python
"""Template fetcher tests (respx-mocked GitHub raw URLs)."""

from typing import Any

import httpx
import pytest
import respx

from maestro.aiostreams.templates import (
    KNOWN_TEMPLATES,
    fetch_template,
    list_templates,
    merge_template_into_config,
)


def test_known_templates_includes_tamtaro_recommended() -> None:
    names = [t["name"] for t in KNOWN_TEMPLATES]
    assert "Tamtaro Complete SEL Setup v2.6.1" in names


def test_list_templates_returns_known_set() -> None:
    templates = list_templates()
    assert len(templates) >= 1
    for t in templates:
        assert "name" in t
        assert "source_url" in t
        assert "description" in t


@respx.mock
@pytest.mark.asyncio
async def test_fetch_template_pulls_json_from_url() -> None:
    payload = {"filters": {"preferred_languages": ["English"]}, "addons": []}
    respx.get("https://example.com/template.json").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await fetch_template("https://example.com/template.json")
    assert result == payload


def test_merge_template_overlays_template_keys_on_config() -> None:
    base = {
        "filters": {"preferred_languages": [], "other": "keep"},
        "addons": [{"name": "Existing"}],
        "untouched": "value",
    }
    template = {
        "filters": {"preferred_languages": ["English"]},
        "addons": [{"name": "New"}],
    }
    merged = merge_template_into_config(base, template, mode="Debrid")

    assert merged["filters"]["preferred_languages"] == ["English"]
    assert merged["filters"]["other"] == "keep"
    assert merged["addons"] == [{"name": "New"}]
    assert merged["untouched"] == "value"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_templates.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/aiostreams/templates.py`:

```python
"""Template fetching + merging for Tamtaro/Vidhin community configs.

Templates are JSON files hosted on GitHub by the community
(Tam-Taro/SEL-Filtering-and-Sorting, Vidhin05/Releases-Regex).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import httpx
import structlog

log = structlog.get_logger("maestro.aiostreams.templates")

Mode = Literal["Debrid", "P2P", "Both"]

KNOWN_TEMPLATES: list[dict[str, str]] = [
    {
        "name": "Tamtaro Complete SEL Setup v2.6.1",
        "source_url": (
            "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
            "main/templates/complete-sel-setup-v2.6.1.json"
        ),
        "description": (
            "Tamtaro's all-in-one Debrid/Usenet/P2P template with English preference, "
            "Standard SEL (~20 results), auto-synced Vidhin's Regexes."
        ),
    },
]


def list_templates() -> list[dict[str, str]]:
    """Return the curated template catalog (no network)."""
    return list(KNOWN_TEMPLATES)


async def fetch_template(source_url: str, *, timeout_s: float = 10.0) -> dict[str, Any]:
    """Fetch a template JSON from its source URL."""
    log.info("aiostreams_fetch_template", url=source_url)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.get(source_url, follow_redirects=True)
        response.raise_for_status()
        return response.json()


def merge_template_into_config(
    base: dict[str, Any],
    template: dict[str, Any],
    *,
    mode: Mode,
) -> dict[str, Any]:
    """Overlay template keys onto a base config.

    Mode is recorded but currently a passthrough — future versions may
    apply mode-specific filtering. Keys present in `template` REPLACE
    the same keys in `base`. Keys not in template are preserved.
    """
    merged = deepcopy(base)
    for key, value in template.items():
        merged[key] = deepcopy(value)
    merged.setdefault("_meta", {})["applied_mode"] = mode
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_templates.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/templates.py tests/unit/aiostreams/test_templates.py
git commit -m "feat(aiostreams): Tamtaro template fetcher + merge helper"
```

### Task 3.5: AIOStreams typed write tools (set_preferred_languages, set_cached_only, set_resolution_floor, set_core_engine)

**Files:**
- Modify: `src/maestro/aiostreams/tools.py` (extend)
- Create: `tests/unit/aiostreams/test_tools_typed_writes.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_tools_typed_writes.py`:

```python
"""Typed write-tool tests (staged in memory, not yet persisted)."""

from typing import Any

import pytest

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "filters": {"preferred_languages": [], "excluded_resolutions": []},
        "core_engine": "Standard SEL - 3 per Q/R",
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        state.clear()
        state.update(body)
        return {"ok": True, "install_url": "stremio://x"}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_set_preferred_languages_stages_change(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_preferred_languages(["English"])
    assert mutation.field == "filters.preferred_languages"
    assert mutation.to == ["English"]


@pytest.mark.asyncio
async def test_set_cached_only_stages_boolean(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_cached_only(enabled=True)
    assert mutation.field == "filters.only_cached"
    assert mutation.to is True


@pytest.mark.asyncio
async def test_set_resolution_floor_excludes_below(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_resolution_floor("720p")
    assert mutation.field == "filters.excluded_resolutions"
    assert set(mutation.to) >= {"240p", "360p", "480p"}
    assert "720p" not in mutation.to


@pytest.mark.asyncio
async def test_set_core_engine_accepts_valid_values(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_core_engine("Extended SEL - 6 per Q/R")
    assert mutation.field == "core_engine"
    assert mutation.to == "Extended SEL - 6 per Q/R"


@pytest.mark.asyncio
async def test_set_core_engine_rejects_invalid_value(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError):
        await toolset.set_core_engine("Made-up Engine")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_tools_typed_writes.py -v
```

Expected: FAIL with `AttributeError: 'AIOStreamsToolset' object has no attribute 'set_preferred_languages'`.

- [ ] **Step 3: Extend the implementation**

Edit `src/maestro/aiostreams/tools.py` — append these methods inside `class AIOStreamsToolset`:

```python
    async def set_preferred_languages(self, languages: list[str]) -> PendingMutation:
        """Stage `filters.preferred_languages`. Order matters — first is primary."""
        return await self._stager.modify(
            lambda cfg: {
                **cfg,
                "filters": {**cfg.get("filters", {}), "preferred_languages": list(languages)},
            },
            field="filters.preferred_languages",
        )

    async def set_cached_only(self, *, enabled: bool) -> PendingMutation:
        """Stage `filters.only_cached`. When true, AIOStreams returns only RD-cached streams."""
        return await self._stager.modify(
            lambda cfg: {
                **cfg,
                "filters": {**cfg.get("filters", {}), "only_cached": enabled},
            },
            field="filters.only_cached",
        )

    async def set_resolution_floor(self, min_resolution: str) -> PendingMutation:
        """Exclude all resolutions below `min_resolution`.

        Valid values: 240p, 360p, 480p, 720p, 1080p, 1440p, 4K, 8K.
        """
        ladder = ["240p", "360p", "480p", "720p", "1080p", "1440p", "4K", "8K"]
        if min_resolution not in ladder:
            raise ValueError(
                f"min_resolution must be one of {ladder}, got {min_resolution!r}"
            )
        index = ladder.index(min_resolution)
        excluded = ladder[:index]

        return await self._stager.modify(
            lambda cfg: {
                **cfg,
                "filters": {**cfg.get("filters", {}), "excluded_resolutions": excluded},
            },
            field="filters.excluded_resolutions",
        )

    async def set_core_engine(self, engine: str) -> PendingMutation:
        """Set the SEL core engine. Valid: 'Standard SEL - 3 per Q/R', 'Extended SEL - 6 per Q/R'."""
        valid = {"Standard SEL - 3 per Q/R", "Extended SEL - 6 per Q/R"}
        if engine not in valid:
            raise ValueError(f"engine must be one of {sorted(valid)}, got {engine!r}")
        return await self._stager.modify(
            lambda cfg: {**cfg, "core_engine": engine},
            field="core_engine",
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_tools_typed_writes.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/tools.py tests/unit/aiostreams/test_tools_typed_writes.py
git commit -m "feat(aiostreams): typed writers — preferred_languages, cached_only, resolution_floor, core_engine"
```

### Task 3.6: AIOStreams addon management tools (add_addon, remove_addon, toggle_addon)

**Files:**
- Modify: `src/maestro/aiostreams/tools.py` (extend)
- Create: `tests/unit/aiostreams/test_tools_addon_mgmt.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_tools_addon_mgmt.py`:

```python
"""Addon management tool tests."""

from typing import Any

import pytest

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "addons": [
            {"name": "Comet", "enabled": True, "manifestUrl": "https://comet.example/m.json"},
            {"name": "MediaFusion", "enabled": True, "manifestUrl": "https://mf.example/m.json"},
        ],
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_add_addon_appends_to_list(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.add_addon(
        addon_url="https://peerflix.example/manifest.json"
    )
    assert mutation.field == "addons"
    assert len(mutation.to) == 3
    assert mutation.to[-1]["manifestUrl"] == "https://peerflix.example/manifest.json"


@pytest.mark.asyncio
async def test_add_addon_at_position(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.add_addon(
        addon_url="https://peerflix.example/manifest.json",
        position=0,
    )
    assert mutation.to[0]["manifestUrl"] == "https://peerflix.example/manifest.json"


@pytest.mark.asyncio
async def test_remove_addon_by_name(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.remove_addon("Comet")
    names = [a["name"] for a in mutation.to]
    assert "Comet" not in names
    assert "MediaFusion" in names


@pytest.mark.asyncio
async def test_remove_addon_unknown_raises(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="not found"):
        await toolset.remove_addon("NonexistentAddon")


@pytest.mark.asyncio
async def test_toggle_addon_flips_enabled(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.toggle_addon("Comet", enabled=False)
    target = next(a for a in mutation.to if a["name"] == "Comet")
    assert target["enabled"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_tools_addon_mgmt.py -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Extend the implementation**

Append to `class AIOStreamsToolset` in `src/maestro/aiostreams/tools.py`:

```python
    async def add_addon(
        self,
        addon_url: str,
        *,
        position: int | None = None,
    ) -> PendingMutation:
        """Add an aggregated addon by manifest URL. Position is 0-indexed insert; None appends."""

        def transform(cfg: dict[str, Any]) -> dict[str, Any]:
            new_entry = {"manifestUrl": addon_url, "enabled": True}
            addons = list(cfg.get("addons", []))
            if position is None:
                addons.append(new_entry)
            else:
                addons.insert(position, new_entry)
            return {**cfg, "addons": addons}

        return await self._stager.modify(transform, field="addons")

    async def remove_addon(self, addon_name: str) -> PendingMutation:
        """Remove an aggregated addon by name."""

        def transform(cfg: dict[str, Any]) -> dict[str, Any]:
            addons = list(cfg.get("addons", []))
            for a in addons:
                if a.get("name") == addon_name:
                    addons.remove(a)
                    return {**cfg, "addons": addons}
            raise ValueError(f"Addon {addon_name!r} not found in current config")

        return await self._stager.modify(transform, field="addons")

    async def toggle_addon(self, addon_name: str, *, enabled: bool) -> PendingMutation:
        """Enable or disable an aggregated addon without removing it."""

        def transform(cfg: dict[str, Any]) -> dict[str, Any]:
            addons = [dict(a) for a in cfg.get("addons", [])]
            for a in addons:
                if a.get("name") == addon_name:
                    a["enabled"] = enabled
                    return {**cfg, "addons": addons}
            raise ValueError(f"Addon {addon_name!r} not found")

        return await self._stager.modify(transform, field="addons")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_tools_addon_mgmt.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/tools.py tests/unit/aiostreams/test_tools_addon_mgmt.py
git commit -m "feat(aiostreams): addon management — add, remove, toggle"
```

### Task 3.7: AIOStreams generic write tools (set_filter, set_sort_order, set_misc_toggle, apply_template)

**Files:**
- Modify: `src/maestro/aiostreams/tools.py` (extend)
- Create: `tests/unit/aiostreams/test_tools_generic_writes.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_tools_generic_writes.py`:

```python
"""Generic write-tool tests."""

from typing import Any

import pytest
import httpx
import respx

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset() -> AIOStreamsToolset:
    state: dict[str, Any] = {
        "filters": {},
        "sortCriteria": [],
        "misc": {},
        "presets": {"active": "Custom"},
    }

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_set_filter_writes_under_filters_block(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_filter("min_size_gb", 2.5)
    assert mutation.field == "filters.min_size_gb"
    assert mutation.to == 2.5


@pytest.mark.asyncio
async def test_set_sort_order_replaces_criteria(toolset: AIOStreamsToolset) -> None:
    order = [
        {"key": "cached", "direction": "desc"},
        {"key": "resolution", "direction": "desc"},
    ]
    mutation = await toolset.set_sort_order(order)
    assert mutation.to == order


@pytest.mark.asyncio
async def test_set_misc_toggle_writes_under_misc(toolset: AIOStreamsToolset) -> None:
    mutation = await toolset.set_misc_toggle("show_statistics", value=True)
    assert mutation.field == "misc.show_statistics"
    assert mutation.to is True


@respx.mock
@pytest.mark.asyncio
async def test_apply_template_overlays_remote_template(toolset: AIOStreamsToolset) -> None:
    template_url = (
        "https://raw.githubusercontent.com/Tam-Taro/SEL-Filtering-and-Sorting/"
        "main/templates/complete-sel-setup-v2.6.1.json"
    )
    template_body = {"filters": {"preferred_languages": ["English"]}}
    respx.get(template_url).mock(return_value=httpx.Response(200, json=template_body))

    mutation = await toolset.apply_template(
        template_name="Tamtaro Complete SEL Setup v2.6.1",
        mode="Debrid",
    )
    assert mutation.field == "presets.active"
    assert mutation.to == "Tamtaro Complete SEL Setup v2.6.1"


@pytest.mark.asyncio
async def test_apply_template_unknown_name_raises(toolset: AIOStreamsToolset) -> None:
    with pytest.raises(ValueError, match="not found"):
        await toolset.apply_template(
            template_name="DoesNotExist",
            mode="Debrid",
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_tools_generic_writes.py -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Extend the implementation**

Append to `class AIOStreamsToolset` in `src/maestro/aiostreams/tools.py`:

```python
    async def set_filter(self, filter_type: str, value: Any) -> PendingMutation:
        """Generic filter setter for any key under `filters.*`.

        Prefer the typed setters (set_preferred_languages, set_cached_only,
        set_resolution_floor) where they exist. Use this for less-common filters.
        """
        return await self._stager.modify(
            lambda cfg: {
                **cfg,
                "filters": {**cfg.get("filters", {}), filter_type: value},
            },
            field=f"filters.{filter_type}",
        )

    async def set_sort_order(self, order: list[dict[str, str]]) -> PendingMutation:
        """Replace the sort hierarchy. Each entry is {key, direction}."""
        return await self._stager.modify(
            lambda cfg: {**cfg, "sortCriteria": list(order)},
            field="sortCriteria",
        )

    async def set_misc_toggle(self, toggle: str, *, value: bool) -> PendingMutation:
        """Toggle a flag under `misc.*` (e.g. show_statistics, digital_release_filter)."""
        return await self._stager.modify(
            lambda cfg: {
                **cfg,
                "misc": {**cfg.get("misc", {}), toggle: value},
            },
            field=f"misc.{toggle}",
        )

    async def apply_template(
        self,
        template_name: str,
        *,
        mode: str = "Debrid",
    ) -> PendingMutation:
        """DESTRUCTIVE: replaces config with the named template overlay.

        Pre-v1.x flow: call this, inspect the staged mutation, call save() to commit.
        v1.x adds MCP elicitation for inline confirmation.
        """
        from maestro.aiostreams.templates import (
            KNOWN_TEMPLATES,
            fetch_template,
            merge_template_into_config,
        )

        match = next((t for t in KNOWN_TEMPLATES if t["name"] == template_name), None)
        if match is None:
            raise ValueError(
                f"Template {template_name!r} not found in catalog. "
                f"Known: {[t['name'] for t in KNOWN_TEMPLATES]}"
            )

        template_payload = await fetch_template(match["source_url"])

        def transform(cfg: dict[str, Any]) -> dict[str, Any]:
            merged = merge_template_into_config(cfg, template_payload, mode=mode)  # type: ignore[arg-type]
            merged.setdefault("presets", {})["active"] = template_name
            return merged

        return await self._stager.modify(transform, field="presets.active")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_tools_generic_writes.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/tools.py tests/unit/aiostreams/test_tools_generic_writes.py
git commit -m "feat(aiostreams): generic writers — set_filter, set_sort_order, set_misc_toggle, apply_template"
```

### Task 3.8: AIOStreams save + get_install_url

**Files:**
- Modify: `src/maestro/aiostreams/tools.py` (extend)
- Create: `tests/unit/aiostreams/test_tools_save.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/aiostreams/test_tools_save.py`:

```python
"""Save + install-URL tool tests."""

from typing import Any

import pytest

from maestro.aiostreams.tools import AIOStreamsToolset


@pytest.fixture
def toolset_with_install_url() -> AIOStreamsToolset:
    state: dict[str, Any] = {"filters": {"preferred_languages": []}}

    async def fake_get_config() -> dict[str, Any]:
        return state

    async def fake_put_config(body: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "install_url": "stremio://aiostreams.elfhosted.com/abcdef/manifest.json",
        }

    return AIOStreamsToolset(get_config=fake_get_config, put_config=fake_put_config)


@pytest.mark.asyncio
async def test_save_flushes_staged_writes(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    await toolset_with_install_url.set_preferred_languages(["English"])
    result = await toolset_with_install_url.save()
    assert result["ok"] is True
    assert "install_url" in result
    assert "filters.preferred_languages" in result["changes_applied"]


@pytest.mark.asyncio
async def test_save_with_nothing_staged_is_noop(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    result = await toolset_with_install_url.save()
    assert result["no_changes"] is True


@pytest.mark.asyncio
async def test_get_install_url_from_last_save(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    await toolset_with_install_url.set_preferred_languages(["English"])
    await toolset_with_install_url.save()
    url = await toolset_with_install_url.get_install_url()
    assert url.startswith("stremio://")


@pytest.mark.asyncio
async def test_get_install_url_without_save_uses_fallback(
    toolset_with_install_url: AIOStreamsToolset,
) -> None:
    """If never saved, fall back to constructing from instance + UUID."""
    url = await toolset_with_install_url.get_install_url()
    assert url == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/aiostreams/test_tools_save.py -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Extend the implementation**

Append to `class AIOStreamsToolset` in `src/maestro/aiostreams/tools.py`:

```python
    async def save(self) -> dict[str, Any]:
        """Commit all staged writes. Returns the new install URL on success."""
        result = await self._stager.save()
        if "install_url" in result:
            self._last_install_url = result["install_url"]
        return result

    async def get_install_url(self) -> str:
        """Return the Stremio install URL produced by the last save().

        Empty string if no save has happened in this session.
        """
        return getattr(self, "_last_install_url", "")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/aiostreams/test_tools_save.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/aiostreams/tools.py tests/unit/aiostreams/test_tools_save.py
git commit -m "feat(aiostreams): save() flushes stager; get_install_url returns latest URL"
```

### Task 3.9: Wire AIOStreams toolset into the FastMCP server

**Files:**
- Modify: `src/maestro/server.py`
- Modify: `src/maestro/aiostreams/__init__.py`
- Create: `tests/integration/aiostreams/__init__.py`
- Create: `tests/integration/aiostreams/test_tool_registration.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/integration/aiostreams/__init__.py`: empty file.

Write to `tests/integration/aiostreams/test_tool_registration.py`:

```python
"""Verify AIOStreams tools are registered with correct annotations."""

import os

import pytest


@pytest.fixture(autouse=True)
def env(monkeypatch: object) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


def _get_tool_names(mcp: object) -> list[str]:
    if hasattr(mcp, "_tool_manager"):
        return [t.name for t in mcp._tool_manager.list_tools()]
    return []


def test_all_aiostreams_read_tools_registered() -> None:
    from maestro.server import create_server

    mcp = create_server()
    names = _get_tool_names(mcp)
    expected_reads = [
        "aiostreams_get_config",
        "aiostreams_get_services",
        "aiostreams_get_addons",
        "aiostreams_get_filters",
        "aiostreams_get_sort_order",
        "aiostreams_get_template_list",
        "aiostreams_get_active_template",
        "aiostreams_get_statistics",
    ]
    for name in expected_reads:
        assert name in names, f"expected read tool {name!r} not registered"


def test_all_aiostreams_write_tools_registered() -> None:
    from maestro.server import create_server

    mcp = create_server()
    names = _get_tool_names(mcp)
    expected_writes = [
        "aiostreams_set_preferred_languages",
        "aiostreams_set_cached_only",
        "aiostreams_set_resolution_floor",
        "aiostreams_set_core_engine",
        "aiostreams_add_addon",
        "aiostreams_remove_addon",
        "aiostreams_toggle_addon",
        "aiostreams_set_filter",
        "aiostreams_set_sort_order",
        "aiostreams_set_misc_toggle",
        "aiostreams_apply_template",
        "aiostreams_save",
        "aiostreams_get_install_url",
    ]
    for name in expected_writes:
        assert name in names, f"expected write tool {name!r} not registered"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/aiostreams/test_tool_registration.py -v
```

Expected: FAIL — no AIOStreams tools registered yet.

- [ ] **Step 3: Wire registration in `src/maestro/aiostreams/__init__.py`**

Replace `src/maestro/aiostreams/__init__.py` with:

```python
"""AIOStreams domain — config CRUD + Tamtaro template support."""

from __future__ import annotations

from fastmcp import FastMCP

from maestro.aiostreams.client import AIOStreamsClient
from maestro.aiostreams.tools import AIOStreamsToolset
from maestro.annotations import destructive, read_only
from maestro.config import MaestroSettings


def register_tools(mcp: FastMCP, settings: MaestroSettings) -> None:
    """Register all 21 AIOStreams tools on the FastMCP app."""
    client = AIOStreamsClient(
        base_url=str(settings.aiostreams_base_url),
        uuid=settings.aiostreams_uuid,
        password=settings.aiostreams_password.get_secret_value(),
        timeout_s=settings.http_timeout_s,
        retry_attempts=settings.retry_attempts,
    )
    toolset = AIOStreamsToolset(
        get_config=client.get_config,
        put_config=client.put_config,
    )

    mcp.tool(
        name="aiostreams_get_config",
        annotations=read_only(title="Get AIOStreams Config").model_dump(),
    )(toolset.get_config)
    mcp.tool(
        name="aiostreams_get_services",
        annotations=read_only(title="Get AIOStreams Services").model_dump(),
    )(toolset.get_services)
    mcp.tool(
        name="aiostreams_get_addons",
        annotations=read_only(title="List AIOStreams Aggregated Addons").model_dump(),
    )(toolset.get_addons)
    mcp.tool(
        name="aiostreams_get_filters",
        annotations=read_only(title="Get AIOStreams Filters").model_dump(),
    )(toolset.get_filters)
    mcp.tool(
        name="aiostreams_get_sort_order",
        annotations=read_only(title="Get AIOStreams Sort Order").model_dump(),
    )(toolset.get_sort_order)
    mcp.tool(
        name="aiostreams_get_template_list",
        annotations=read_only(title="List Available Templates").model_dump(),
    )(toolset.get_template_list)
    mcp.tool(
        name="aiostreams_get_active_template",
        annotations=read_only(title="Get Active Template Name").model_dump(),
    )(toolset.get_active_template)
    mcp.tool(
        name="aiostreams_get_statistics",
        annotations=read_only(title="Get AIOStreams Statistics").model_dump(),
    )(toolset.get_statistics)

    mcp.tool(
        name="aiostreams_set_preferred_languages",
        annotations=destructive(title="Set Preferred Languages").model_dump(),
    )(toolset.set_preferred_languages)
    mcp.tool(
        name="aiostreams_set_cached_only",
        annotations=destructive(title="Set Cached-Only Filter").model_dump(),
    )(toolset.set_cached_only)
    mcp.tool(
        name="aiostreams_set_resolution_floor",
        annotations=destructive(title="Set Resolution Floor").model_dump(),
    )(toolset.set_resolution_floor)
    mcp.tool(
        name="aiostreams_set_core_engine",
        annotations=destructive(title="Set SEL Core Engine").model_dump(),
    )(toolset.set_core_engine)
    mcp.tool(
        name="aiostreams_add_addon",
        annotations=destructive(title="Add Aggregated Addon").model_dump(),
    )(toolset.add_addon)
    mcp.tool(
        name="aiostreams_remove_addon",
        annotations=destructive(title="Remove Aggregated Addon").model_dump(),
    )(toolset.remove_addon)
    mcp.tool(
        name="aiostreams_toggle_addon",
        annotations=destructive(title="Toggle Aggregated Addon").model_dump(),
    )(toolset.toggle_addon)
    mcp.tool(
        name="aiostreams_set_filter",
        annotations=destructive(title="Set Generic Filter").model_dump(),
    )(toolset.set_filter)
    mcp.tool(
        name="aiostreams_set_sort_order",
        annotations=destructive(title="Set Sort Order").model_dump(),
    )(toolset.set_sort_order)
    mcp.tool(
        name="aiostreams_set_misc_toggle",
        annotations=destructive(title="Set Misc Toggle").model_dump(),
    )(toolset.set_misc_toggle)
    mcp.tool(
        name="aiostreams_apply_template",
        annotations=destructive(title="Apply Template (DESTRUCTIVE)").model_dump(),
    )(toolset.apply_template)
    mcp.tool(
        name="aiostreams_save",
        annotations=destructive(title="Save Staged Writes").model_dump(),
    )(toolset.save)
    mcp.tool(
        name="aiostreams_get_install_url",
        annotations=read_only(title="Get Stremio Install URL").model_dump(),
    )(toolset.get_install_url)
```

- [ ] **Step 4: Update server.py to call register_tools**

Edit `src/maestro/server.py`, replace the function body of `create_server` with:

```python
def create_server() -> FastMCP:
    settings = MaestroSettings()
    configure_logging(format=settings.log_format, level=settings.log_level)
    log = structlog.get_logger("maestro.server")
    log.info("server_starting",
             aiostreams_base_url=str(settings.aiostreams_base_url),
             torrentio_base_url=str(settings.torrentio_base_url),
             http_timeout_s=settings.http_timeout_s)

    mcp = FastMCP(name="maestro")

    from maestro.aiostreams import register_tools as register_aiostreams
    register_aiostreams(mcp, settings)

    return mcp
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/integration/aiostreams/test_tool_registration.py -v
```

Expected: 2 tests PASS (all 21 tools registered).

- [ ] **Step 6: Commit**

```bash
git add src/maestro/aiostreams/__init__.py src/maestro/server.py tests/integration/aiostreams/
git commit -m "feat(aiostreams): register 21 tools with MCP annotations on FastMCP app"
```

---

## Phase 4 — Torrentio domain (URL-string config)

Goal: 5 MCP tools for parsing, building, and validating Torrentio install URLs. No remote API — Torrentio config is pipe-delimited `key=value` in the URL path.

### Task 4.1: Enums extracted from Torrentio filter.js

**Files:**
- Create: `src/maestro/torrentio/__init__.py`
- Create: `src/maestro/torrentio/enums.py`
- Create: `tests/unit/torrentio/__init__.py`
- Create: `tests/unit/torrentio/test_enums.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/torrentio/__init__.py`: empty.

Write to `tests/unit/torrentio/test_enums.py`:

```python
"""Torrentio enum tests."""

from maestro.torrentio.enums import (
    DEBRID_PROVIDERS,
    LANGUAGES,
    PROVIDERS,
    QUALITY_FILTERS,
    SORT_OPTIONS,
)


def test_providers_includes_known_english_set() -> None:
    """English-leaning providers per Clay's optimization-session config."""
    expected = {
        "yts", "eztv", "rarbg", "1337x", "thepiratebay", "kickasstorrents",
        "torrentgalaxy", "magnetdl", "horriblesubs", "nyaasi", "tokyotosho",
        "anidex",
    }
    actual = set(PROVIDERS)
    missing = expected - actual
    assert not missing, f"missing providers: {missing}"


def test_quality_filters_includes_low_quality_exclusions() -> None:
    expected = {"cam", "ts", "scr", "r5", "r6", "telesync"}
    intersect = expected & set(QUALITY_FILTERS)
    assert intersect, f"expected at least some of {expected} in {QUALITY_FILTERS}"


def test_debrid_providers_includes_realdebrid() -> None:
    assert "realdebrid" in DEBRID_PROVIDERS


def test_languages_includes_english() -> None:
    assert "english" in LANGUAGES


def test_sort_options_includes_quality_then_size() -> None:
    assert "qualitysize" in SORT_OPTIONS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/torrentio/test_enums.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/torrentio/__init__.py`: empty.

Write to `src/maestro/torrentio/enums.py`:

```python
"""Torrentio enum values extracted from `addon/lib/filter.js`.

Source: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/filter.js

These are the valid values that Torrentio's config parser accepts.
Refresh when upstream adds providers/qualities.
"""

from __future__ import annotations

PROVIDERS: list[str] = [
    "yts", "eztv", "rarbg", "1337x", "thepiratebay", "kickasstorrents",
    "torrentgalaxy", "magnetdl", "horriblesubs", "nyaasi", "tokyotosho",
    "anidex", "rutor", "rutracker", "comando", "bludv", "micoleaodublado",
    "torrent9", "ilcorsaronero", "mejortorrent", "wolfmax4k", "cinecalidad",
    "besttorrents", "nekobt",
]

QUALITY_FILTERS: list[str] = [
    "cam", "ts", "telesync", "scr", "screener", "r5", "r6", "hdcam",
    "hdts", "hdtelesync", "hdrip", "brrip", "bdrip", "dvdrip", "dvdr",
    "dvdscr", "3d", "480p", "240p", "360p",
]

RESOLUTIONS: list[str] = [
    "240p", "360p", "480p", "720p", "1080p", "1440p", "4k", "8k",
]

DEBRID_PROVIDERS: list[str] = [
    "realdebrid", "premiumize", "alldebrid", "debridlink", "easydebrid",
    "offcloud", "torbox", "putio",
]

LANGUAGES: list[str] = [
    "english", "russian", "italian", "portuguese", "spanish", "french",
    "german", "japanese", "korean", "chinese", "polish",
]

SORT_OPTIONS: list[str] = [
    "qualitysize",
    "qualityseeders",
    "sizequality",
    "seedersquality",
    "seeders",
    "size",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/torrentio/test_enums.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/torrentio/__init__.py src/maestro/torrentio/enums.py tests/unit/torrentio/
git commit -m "feat(torrentio): provider/quality/debrid/language/sort enums from filter.js"
```

### Task 4.2: URL config encoder/decoder

**Files:**
- Create: `src/maestro/torrentio/encoder.py`
- Create: `tests/unit/torrentio/test_encoder.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/torrentio/test_encoder.py`:

```python
"""Torrentio URL config encode/decode tests."""

import pytest

from maestro.torrentio.encoder import (
    TorrentioConfig,
    build_url,
    parse_url,
    validate_config,
)


def test_parse_url_extracts_providers() -> None:
    url = (
        "https://torrentio.strem.fun/"
        "providers=yts,eztv,rarbg|sort=qualitysize|"
        "qualityfilter=cam,ts|realdebrid=ABC123/manifest.json"
    )
    cfg = parse_url(url)
    assert cfg.providers == ["yts", "eztv", "rarbg"]
    assert cfg.sort == "qualitysize"
    assert cfg.quality_filter == ["cam", "ts"]
    assert cfg.debrid_provider == "realdebrid"
    assert cfg.debrid_key == "ABC123"


def test_build_url_round_trips() -> None:
    cfg = TorrentioConfig(
        providers=["yts", "eztv"],
        sort="qualitysize",
        quality_filter=["cam"],
        debrid_provider="realdebrid",
        debrid_key="RD_TOKEN",
    )
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    reparsed = parse_url(url)
    assert reparsed.providers == cfg.providers
    assert reparsed.debrid_key == "RD_TOKEN"


def test_validate_config_rejects_unknown_provider() -> None:
    cfg = TorrentioConfig(providers=["yts", "made_up_provider"])
    errors = validate_config(cfg)
    assert any("made_up_provider" in e for e in errors)


def test_validate_config_accepts_clay_optimization_config() -> None:
    cfg = TorrentioConfig(
        providers=[
            "yts", "eztv", "rarbg", "1337x", "thepiratebay",
            "kickasstorrents", "torrentgalaxy", "magnetdl",
            "horriblesubs", "nyaasi", "tokyotosho", "anidex", "nekobt",
        ],
        sort="qualitysize",
        quality_filter=["3d", "480p", "scr", "cam"],
        debrid_provider="realdebrid",
        debrid_key="RD_TOKEN",
    )
    errors = validate_config(cfg)
    assert errors == []


def test_parse_url_handles_minimal() -> None:
    url = "https://torrentio.strem.fun/manifest.json"
    cfg = parse_url(url)
    assert cfg.providers == []
    assert cfg.debrid_provider is None


def test_build_url_omits_unset_keys() -> None:
    cfg = TorrentioConfig(providers=["yts"])
    url = build_url(cfg, base_url="https://torrentio.strem.fun")
    assert "providers=yts" in url
    assert "qualityfilter" not in url
    assert "realdebrid=" not in url
    assert url.endswith("/manifest.json")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/torrentio/test_encoder.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/torrentio/encoder.py`:

```python
"""Encode/decode Torrentio install URLs.

URL grammar (per addon/lib/configuration.js):

    <base>/<key>=<value>[|<key>=<value>...]/manifest.json

Where each <value> is comma-delimited for list fields. Debrid keys use
`<provider>=<token>` form rather than `debrid=...`.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from maestro.torrentio.enums import DEBRID_PROVIDERS, PROVIDERS, QUALITY_FILTERS, SORT_OPTIONS


class TorrentioConfig(BaseModel):
    """A Torrentio install-URL configuration."""

    providers: list[str] = Field(default_factory=list)
    sort: str | None = None
    quality_filter: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    limit: int | None = None
    size_filter: str | None = None
    debrid_provider: str | None = None
    debrid_key: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


_KV_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)=([^|/]+)")


def parse_url(url: str) -> TorrentioConfig:
    """Parse a Torrentio install URL into a TorrentioConfig."""
    base_strip = re.sub(r"https?://[^/]+/?", "", url).strip("/")
    base_strip = base_strip.replace("/manifest.json", "").rstrip("/")

    cfg = TorrentioConfig()
    for match in _KV_RE.finditer(base_strip):
        key = match.group(1).lower()
        raw = match.group(2)
        if key == "providers":
            cfg.providers = [p.strip() for p in raw.split(",") if p.strip()]
        elif key == "sort":
            cfg.sort = raw.strip()
        elif key == "qualityfilter":
            cfg.quality_filter = [q.strip() for q in raw.split(",") if q.strip()]
        elif key == "languages":
            cfg.languages = [lang.strip() for lang in raw.split(",") if lang.strip()]
        elif key == "limit":
            try:
                cfg.limit = int(raw.strip())
            except ValueError:
                pass
        elif key == "sizefilter":
            cfg.size_filter = raw.strip()
        elif key in DEBRID_PROVIDERS:
            cfg.debrid_provider = key
            cfg.debrid_key = raw.strip()
        else:
            cfg.extra[key] = raw.strip()
    return cfg


def build_url(cfg: TorrentioConfig, *, base_url: str = "https://torrentio.strem.fun") -> str:
    """Build a Torrentio install URL from a TorrentioConfig."""
    parts: list[str] = []
    if cfg.providers:
        parts.append(f"providers={','.join(cfg.providers)}")
    if cfg.sort:
        parts.append(f"sort={cfg.sort}")
    if cfg.quality_filter:
        parts.append(f"qualityfilter={','.join(cfg.quality_filter)}")
    if cfg.languages:
        parts.append(f"languages={','.join(cfg.languages)}")
    if cfg.limit is not None:
        parts.append(f"limit={cfg.limit}")
    if cfg.size_filter:
        parts.append(f"sizefilter={cfg.size_filter}")
    for k, v in cfg.extra.items():
        parts.append(f"{k}={v}")
    if cfg.debrid_provider and cfg.debrid_key:
        parts.append(f"{cfg.debrid_provider}={cfg.debrid_key}")

    base = base_url.rstrip("/")
    if not parts:
        return f"{base}/manifest.json"
    return f"{base}/{('|').join(parts)}/manifest.json"


def validate_config(cfg: TorrentioConfig) -> list[str]:
    """Return a list of human-readable validation errors. Empty = valid."""
    errors: list[str] = []

    for p in cfg.providers:
        if p.lower() not in PROVIDERS:
            errors.append(f"unknown provider: {p!r} (valid: {PROVIDERS})")

    for q in cfg.quality_filter:
        if q.lower() not in QUALITY_FILTERS:
            errors.append(f"unknown quality_filter: {q!r}")

    if cfg.sort and cfg.sort not in SORT_OPTIONS:
        errors.append(f"unknown sort: {cfg.sort!r} (valid: {SORT_OPTIONS})")

    if cfg.debrid_provider and cfg.debrid_provider not in DEBRID_PROVIDERS:
        errors.append(f"unknown debrid_provider: {cfg.debrid_provider!r}")

    return errors


def _data() -> dict[str, Any]:
    """Diagnostic dump of which constants are loaded."""
    return {
        "providers": PROVIDERS,
        "quality_filters": QUALITY_FILTERS,
        "debrid_providers": DEBRID_PROVIDERS,
        "sort_options": SORT_OPTIONS,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/torrentio/test_encoder.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/torrentio/encoder.py tests/unit/torrentio/test_encoder.py
git commit -m "feat(torrentio): URL config encoder/decoder with enum validation"
```

### Task 4.3: Torrentio MCP tools + registration

**Files:**
- Create: `src/maestro/torrentio/tools.py`
- Create: `tests/unit/torrentio/test_tools.py`
- Modify: `src/maestro/server.py` (register Torrentio tools)

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/torrentio/test_tools.py`:

```python
"""Torrentio tool tests."""

from maestro.torrentio.tools import (
    torrentio_build_url,
    torrentio_list_providers,
    torrentio_list_quality_filters,
    torrentio_parse_url,
    torrentio_validate_config,
)


def test_torrentio_list_providers_returns_string_list() -> None:
    providers = torrentio_list_providers()
    assert isinstance(providers, list)
    assert "yts" in providers


def test_torrentio_list_quality_filters_returns_string_list() -> None:
    qfs = torrentio_list_quality_filters()
    assert "cam" in qfs


def test_torrentio_parse_url_returns_config_dict() -> None:
    url = "https://torrentio.strem.fun/providers=yts|sort=qualitysize/manifest.json"
    cfg = torrentio_parse_url(url)
    assert cfg["providers"] == ["yts"]
    assert cfg["sort"] == "qualitysize"


def test_torrentio_build_url_returns_string() -> None:
    cfg_dict = {"providers": ["yts", "eztv"]}
    url = torrentio_build_url(cfg_dict)
    assert "providers=yts,eztv" in url


def test_torrentio_validate_config_returns_errors_list() -> None:
    errors = torrentio_validate_config({"providers": ["yts", "bogus"]})
    assert any("bogus" in e for e in errors)


def test_torrentio_validate_config_clean_returns_empty_list() -> None:
    errors = torrentio_validate_config({"providers": ["yts"], "sort": "qualitysize"})
    assert errors == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/torrentio/test_tools.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/torrentio/tools.py`:

```python
"""Torrentio MCP tool definitions.

All 5 tools are pure compute — no network. They wrap encoder.py +
enums.py for Claude's consumption.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import pure_compute, read_only
from maestro.torrentio.encoder import (
    TorrentioConfig,
    build_url,
    parse_url,
    validate_config,
)
from maestro.torrentio.enums import PROVIDERS, QUALITY_FILTERS


def torrentio_parse_url(url: str) -> dict[str, Any]:
    """Decode a Torrentio install URL into its config object.

    Returns a dict with keys: providers, sort, quality_filter, languages,
    limit, size_filter, debrid_provider, debrid_key, extra.

    Reference: https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/configuration.js
    """
    return parse_url(url).model_dump()


def torrentio_build_url(
    config: dict[str, Any],
    *,
    base_url: str = "https://torrentio.strem.fun",
) -> str:
    """Build a Torrentio install URL from a config dict."""
    cfg = TorrentioConfig.model_validate(config)
    return build_url(cfg, base_url=base_url)


def torrentio_validate_config(config: dict[str, Any]) -> list[str]:
    """Validate a Torrentio config against known enums. Empty list = valid."""
    cfg = TorrentioConfig.model_validate(config)
    return validate_config(cfg)


def torrentio_list_providers() -> list[str]:
    """Return all known torrent providers (lowercase strings)."""
    return list(PROVIDERS)


def torrentio_list_quality_filters() -> list[str]:
    """Return all valid quality-filter tags for exclusion config."""
    return list(QUALITY_FILTERS)


def register_tools(mcp: FastMCP) -> None:
    """Register all 5 Torrentio tools."""
    mcp.tool(
        name="torrentio_parse_url",
        annotations=read_only(title="Parse Torrentio URL").model_dump(),
    )(torrentio_parse_url)
    mcp.tool(
        name="torrentio_build_url",
        annotations=pure_compute(title="Build Torrentio URL").model_dump(),
    )(torrentio_build_url)
    mcp.tool(
        name="torrentio_validate_config",
        annotations=pure_compute(title="Validate Torrentio Config").model_dump(),
    )(torrentio_validate_config)
    mcp.tool(
        name="torrentio_list_providers",
        annotations=pure_compute(title="List Torrentio Providers").model_dump(),
    )(torrentio_list_providers)
    mcp.tool(
        name="torrentio_list_quality_filters",
        annotations=pure_compute(title="List Torrentio Quality Filters").model_dump(),
    )(torrentio_list_quality_filters)
```

- [ ] **Step 4: Update server.py to register Torrentio**

In `src/maestro/server.py`, add inside `create_server()` after the AIOStreams registration:

```python
    from maestro.torrentio.tools import register_tools as register_torrentio
    register_torrentio(mcp)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/torrentio/test_tools.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/maestro/torrentio/tools.py tests/unit/torrentio/test_tools.py src/maestro/server.py
git commit -m "feat(torrentio): 5 MCP tools + server wiring"
```

---

## Phase 5 — Real-Debrid domain (with filter-gate learning loop)

Goal: 7 tools wrapping RD REST API + the novel filter-gate learning loop. Persistent state at `~/.config/maestro/filter_gate_state.json` survives server restarts.

### Task 5.1: RD async client (auth + cache check)

**Files:**
- Create: `src/maestro/realdebrid/__init__.py`
- Create: `src/maestro/realdebrid/client.py`
- Create: `tests/unit/realdebrid/__init__.py`
- Create: `tests/unit/realdebrid/test_client.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/realdebrid/__init__.py`: empty.

Write to `tests/unit/realdebrid/test_client.py`:

```python
"""Real-Debrid client tests (respx-mocked)."""

import httpx
import pytest
import respx

from maestro.errors import AuthError, RateLimitError, UpstreamError
from maestro.realdebrid.client import RDClient


@pytest.fixture
def client() -> RDClient:
    return RDClient(api_token="test_token_abc", timeout_s=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_happy_path(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(200, json={"id": 42, "username": "clay", "type": "premium"})
    )
    info = await client.get_user_info()
    assert info["username"] == "clay"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_401_raises_auth_error(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(AuthError):
        await client.get_user_info()


@respx.mock
@pytest.mark.asyncio
async def test_check_cache_batch_returns_map(client: RDClient) -> None:
    hashes = ["abc123", "def456", "789xyz"]
    payload = {
        "abc123": {"rd": [{"1": {"filename": "f.mkv"}}]},
        "def456": {"rd": [{"2": {"filename": "g.mkv"}}]},
        "789xyz": [],
    }
    respx.get(
        "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/abc123/def456/789xyz"
    ).mock(return_value=httpx.Response(200, json=payload))

    result = await client.check_cache(hashes)
    assert result["abc123"]["cached"] is True
    assert result["def456"]["cached"] is True
    assert result["789xyz"]["cached"] is False


@respx.mock
@pytest.mark.asyncio
async def test_unrestrict_link_returns_playable_url(client: RDClient) -> None:
    respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(
            200, json={"download": "https://rd.example/cdn/abc.mkv", "filename": "abc.mkv"}
        )
    )
    result = await client.unrestrict_link("https://restricted.rd/x")
    assert result["download"] == "https://rd.example/cdn/abc.mkv"


@respx.mock
@pytest.mark.asyncio
async def test_unrestrict_403_with_infringing_file_returns_structured(
    client: RDClient,
) -> None:
    respx.post("https://api.real-debrid.com/rest/1.0/unrestrict/link").mock(
        return_value=httpx.Response(
            403, json={"error": "infringing_file", "error_code": 35}
        )
    )
    with pytest.raises(UpstreamError) as exc_info:
        await client.unrestrict_link("https://restricted.rd/x")
    assert "infringing_file" in str(exc_info.value).lower() or exc_info.value.code == "upstream_error"


@respx.mock
@pytest.mark.asyncio
async def test_rate_limit_429_raises_rate_limit_error(client: RDClient) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(
            429, json={"error": "rate_limit"}, headers={"Retry-After": "30"}
        )
    )
    with pytest.raises(RateLimitError) as exc_info:
        await client.get_user_info()
    assert exc_info.value.retry_after_s == 30.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/realdebrid/test_client.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/realdebrid/__init__.py`: empty.

Write to `src/maestro/realdebrid/client.py`:

```python
"""Async httpx client for Real-Debrid REST API.

API docs: https://api.real-debrid.com/

Auth: Bearer <api_token> header.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from maestro.errors import AuthError, RateLimitError, UpstreamError

log = structlog.get_logger("maestro.realdebrid.client")

BASE_URL = "https://api.real-debrid.com/rest/1.0"


class RDClient:
    """Async client for the Real-Debrid REST API."""

    def __init__(self, *, api_token: str, timeout_s: float = 15.0) -> None:
        self._token = api_token
        self._timeout_s = timeout_s
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=httpx.Timeout(self._timeout_s),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        client = await self._get_client()
        try:
            response = await client.request(method, f"{BASE_URL}{path}", **kwargs)
        except httpx.HTTPError as e:
            raise UpstreamError(domain="realdebrid", message=str(e)) from e

        if response.status_code == 401:
            raise AuthError(
                domain="realdebrid",
                suggestion="Check MAESTRO_RD_TOKEN",
            )
        if response.status_code == 429:
            retry = float(response.headers.get("Retry-After", "30"))
            raise RateLimitError(
                domain="realdebrid",
                retry_after_s=retry,
                message="RD rate-limited (~250 req/min)",
            )
        if 500 <= response.status_code < 600:
            raise UpstreamError(domain="realdebrid", message=f"RD {response.status_code}")
        if response.status_code >= 400:
            raise UpstreamError(
                domain="realdebrid",
                message=f"RD {response.status_code}: {response.text[:200]}",
            )
        return response

    async def get_user_info(self) -> dict[str, Any]:
        """GET /user — verify auth + return account info."""
        response = await self._request("GET", "/user")
        return response.json()

    async def check_cache(self, infohashes: list[str]) -> dict[str, dict[str, Any]]:
        """Batch cache check via /torrents/instantAvailability.

        Returns a dict keyed by hash with keys {cached: bool, files: dict | None}.
        """
        if not infohashes:
            return {}
        path = "/torrents/instantAvailability/" + "/".join(infohashes)
        response = await self._request("GET", path)
        raw = response.json()
        result: dict[str, dict[str, Any]] = {}
        for h in infohashes:
            entry = raw.get(h, [])
            if isinstance(entry, dict) and entry.get("rd"):
                result[h] = {"cached": True, "files": entry}
            else:
                result[h] = {"cached": False, "files": None}
        return result

    async def add_magnet(self, magnet: str) -> dict[str, Any]:
        """POST /torrents/addMagnet."""
        response = await self._request(
            "POST", "/torrents/addMagnet", data={"magnet": magnet}
        )
        return response.json()

    async def get_torrent_status(self, torrent_id: str) -> dict[str, Any]:
        """GET /torrents/info/<id>."""
        response = await self._request("GET", f"/torrents/info/{torrent_id}")
        return response.json()

    async def unrestrict_link(self, restricted_url: str) -> dict[str, Any]:
        """POST /unrestrict/link → playable HTTP URL."""
        response = await self._request(
            "POST", "/unrestrict/link", data={"link": restricted_url}
        )
        return response.json()

    async def get_library(self) -> list[dict[str, Any]]:
        """GET /torrents — user's RD library."""
        response = await self._request("GET", "/torrents")
        return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/realdebrid/test_client.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/realdebrid/__init__.py src/maestro/realdebrid/client.py tests/unit/realdebrid/
git commit -m "feat(realdebrid): async client — auth, cache check, magnet, unrestrict, library"
```

### Task 5.2: Filter-gate learner (the novel piece)

**Files:**
- Create: `src/maestro/realdebrid/filter_gate.py`
- Create: `tests/unit/realdebrid/test_filter_gate.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/realdebrid/test_filter_gate.py`:

```python
"""Filter-gate learner tests."""

import json
from pathlib import Path

import pytest

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
    state_path.write_text(json.dumps({
        "learned_keywords": {
            "PRELOADED": {"count": 5, "first_seen": "2026-05-01T00:00:00Z"}
        }
    }))
    learner = FilterGateLearner(state_path=state_path)
    learner.load_state()
    assert "PRELOADED" in learner.learned_keywords
    assert learner.learned_keywords["PRELOADED"].count == 5


def test_predict_risk_high_after_learning() -> None:
    learner = FilterGateLearner()
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")
    assert learner.predict_risk("y.NOVELKW.mkv") == RiskLevel.HIGH
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/realdebrid/test_filter_gate.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/realdebrid/filter_gate.py`:

```python
"""May 2026 Real-Debrid filter-gate heuristic + runtime learning loop.

RD's parent company XT Network restructured in early May 2026 and began
blanket-blocking torrent filenames containing certain release-group tags
under EU DSA Article 16. The block applies post-cache-check:
`/torrents/instantAvailability` reports the file cached, but
`/unrestrict/link` returns 403 with error code `infringing_file`.

We maintain:
  - KNOWN_KEYWORDS: static baseline from observed May 2026 behavior
  - LEARNED_KEYWORDS: promoted at runtime when unrestrict 403s
                      with `infringing_file`

State is persisted to ~/.config/maestro/filter_gate_state.json so learning
survives server restarts.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from collections.abc import Iterable
from enum import Enum
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger("maestro.realdebrid.filter_gate")


KNOWN_KEYWORDS: set[str] = {
    "WEB-DL", "WEBRip", "AMZN", "NF", "CR",
    "YTS", "RARBG", "[eztv]",
}


class RiskLevel(str, Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LearnEvidence(BaseModel):
    count: int = 1
    first_seen: str = Field(
        default_factory=lambda: _dt.datetime.now(_dt.UTC).isoformat()
    )


class FilterGateLearner:
    """Tracks runtime evidence + predicts risk for a given filename."""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self.state_path: Path | None = (
            Path(state_path).expanduser() if state_path else None
        )
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
        """Promote likely keyword(s) from a 403 to LEARNED_KEYWORDS.

        Extracts UPPERCASE alphanumeric tokens (4+ chars) from the
        filename that aren't already in KNOWN_KEYWORDS, and records
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
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "learned_keywords": {
                k: v.model_dump() for k, v in self.learned_keywords.items()
            }
        }
        self.state_path.write_text(json.dumps(payload, indent=2))

    def load_state(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text())
        except json.JSONDecodeError:
            log.warning("filter_gate_state_corrupt", path=str(self.state_path))
            return
        raw = data.get("learned_keywords", {})
        self.learned_keywords = {
            k: LearnEvidence.model_validate(v) for k, v in raw.items()
        }

    def export_state(self) -> dict[str, dict[str, str | int]]:
        return {
            "known_keywords": sorted(KNOWN_KEYWORDS),
            "learned_keywords": {
                k: v.model_dump() for k, v in self.learned_keywords.items()
            },
        }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/realdebrid/test_filter_gate.py -v
```

Expected: 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/realdebrid/filter_gate.py tests/unit/realdebrid/test_filter_gate.py
git commit -m "feat(realdebrid): filter-gate learner with persistent state (~/.config/maestro/)"
```

### Task 5.3: RD MCP tools + registration

**Files:**
- Create: `src/maestro/realdebrid/tools.py`
- Create: `tests/unit/realdebrid/test_tools.py`
- Modify: `src/maestro/server.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/realdebrid/test_tools.py`:

```python
"""Real-Debrid tool tests."""

from typing import Any

import httpx
import pytest
import respx

from maestro.realdebrid.filter_gate import FilterGateLearner
from maestro.realdebrid.tools import RDToolset


@pytest.fixture
def toolset(tmp_path) -> RDToolset:
    learner = FilterGateLearner(state_path=tmp_path / "state.json")
    return RDToolset(api_token="test_token", learner=learner, timeout_s=5.0)


def test_filter_gate_check_returns_risk_dict(toolset: RDToolset) -> None:
    result = toolset.filter_gate_check("S01E03.WEB-DL.AMZN.mkv")
    assert result["risk"] == "high"
    assert "WEB-DL" in result["matched_keywords"]


def test_filter_gate_check_low_for_clean_filename(toolset: RDToolset) -> None:
    result = toolset.filter_gate_check("S01E03.BluRay.1080p.x264.mkv")
    assert result["risk"] == "low"
    assert result["matched_keywords"] == []


@respx.mock
@pytest.mark.asyncio
async def test_check_cache_overlays_filter_gate(toolset: RDToolset) -> None:
    respx.get(
        "https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/abc/def"
    ).mock(return_value=httpx.Response(200, json={
        "abc": {"rd": [{"1": {"filename": "S01E03.WEB-DL.AMZN.mkv"}}]},
        "def": {"rd": [{"1": {"filename": "S01E03.BluRay.mkv"}}]},
    }))

    result = await toolset.check_cache(
        infohashes=["abc", "def"],
        filenames={"abc": "S01E03.WEB-DL.AMZN.mkv", "def": "S01E03.BluRay.mkv"},
    )
    abc = next(r for r in result if r["hash"] == "abc")
    deff = next(r for r in result if r["hash"] == "def")
    assert abc["cached"] is True
    assert abc["filter_gate_risk"] == "high"
    assert deff["filter_gate_risk"] == "low"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_info_passes_through(toolset: RDToolset) -> None:
    respx.get("https://api.real-debrid.com/rest/1.0/user").mock(
        return_value=httpx.Response(200, json={"username": "clay", "premium": 1})
    )
    info = await toolset.get_user_info()
    assert info["username"] == "clay"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/realdebrid/test_tools.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/realdebrid/tools.py`:

```python
"""Real-Debrid MCP tool definitions (7 tools)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import destructive, pure_compute, read_only
from maestro.config import MaestroSettings
from maestro.realdebrid.client import RDClient
from maestro.realdebrid.filter_gate import FilterGateLearner


class RDToolset:
    """Encapsulates RD client + filter-gate learner."""

    def __init__(
        self,
        *,
        api_token: str,
        learner: FilterGateLearner,
        timeout_s: float = 15.0,
    ) -> None:
        self._client = RDClient(api_token=api_token, timeout_s=timeout_s)
        self._learner = learner

    async def get_user_info(self) -> dict[str, Any]:
        """Verify RD auth + return account info."""
        return await self._client.get_user_info()

    async def check_cache(
        self,
        infohashes: list[str],
        filenames: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Batch cache check + filter-gate overlay.

        `filenames` is optional but recommended: when supplied, results
        include `filter_gate_risk` predictions for each candidate.
        """
        raw = await self._client.check_cache(infohashes)
        results: list[dict[str, Any]] = []
        for h in infohashes:
            entry = raw.get(h, {"cached": False, "files": None})
            filename = (filenames or {}).get(h)
            risk = self._learner.predict_risk(filename)
            matched = self._learner.matched_keywords(filename) if filename else []
            results.append(
                {
                    "hash": h,
                    "cached": entry["cached"],
                    "filter_gate_risk": risk.value,
                    "matched_keywords": matched,
                    "rd_files": entry.get("files"),
                }
            )
        return results

    def filter_gate_check(self, filename: str) -> dict[str, Any]:
        """Heuristic-only risk prediction for a filename (no network)."""
        return {
            "filename": filename,
            "risk": self._learner.predict_risk(filename).value,
            "matched_keywords": self._learner.matched_keywords(filename),
        }

    async def add_torrent(self, magnet: str) -> dict[str, Any]:
        """POST /torrents/addMagnet."""
        return await self._client.add_magnet(magnet)

    async def get_torrent_status(self, torrent_id: str) -> dict[str, Any]:
        return await self._client.get_torrent_status(torrent_id)

    async def unrestrict_link(self, restricted_url: str) -> dict[str, Any]:
        """Resolve restricted RD link to playable URL."""
        return await self._client.unrestrict_link(restricted_url)

    async def get_library(self) -> list[dict[str, Any]]:
        return await self._client.get_library()


def register_tools(mcp: FastMCP, settings: MaestroSettings) -> RDToolset:
    """Register all 7 RD tools. Returns the toolset so composer can share it."""
    learner = FilterGateLearner(state_path=settings.filter_gate_state_path)
    learner.load_state()

    toolset = RDToolset(
        api_token=settings.rd_token.get_secret_value(),
        learner=learner,
        timeout_s=settings.http_timeout_s,
    )

    mcp.tool(
        name="realdebrid_get_user_info",
        annotations=read_only(title="Get RD User Info").model_dump(),
    )(toolset.get_user_info)
    mcp.tool(
        name="realdebrid_check_cache",
        annotations=read_only(title="Batch RD Cache Check with Filter-Gate Overlay").model_dump(),
    )(toolset.check_cache)
    mcp.tool(
        name="realdebrid_filter_gate_check",
        annotations=pure_compute(title="Filter-Gate Risk Heuristic").model_dump(),
    )(toolset.filter_gate_check)
    mcp.tool(
        name="realdebrid_add_torrent",
        annotations=destructive(title="Add Torrent to RD").model_dump(),
    )(toolset.add_torrent)
    mcp.tool(
        name="realdebrid_get_torrent_status",
        annotations=read_only(title="Get RD Torrent Status").model_dump(),
    )(toolset.get_torrent_status)
    mcp.tool(
        name="realdebrid_unrestrict_link",
        annotations=destructive(title="Unrestrict RD Link to Playable URL").model_dump(),
    )(toolset.unrestrict_link)
    mcp.tool(
        name="realdebrid_get_library",
        annotations=read_only(title="List RD Library").model_dump(),
    )(toolset.get_library)
    return toolset
```

- [ ] **Step 4: Update server.py to register RD**

In `src/maestro/server.py`, add inside `create_server()` (after Torrentio registration):

```python
    from maestro.realdebrid.tools import register_tools as register_rd
    rd_toolset = register_rd(mcp, settings)
```

Store `rd_toolset` on the server module so composer can reuse it later.

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/realdebrid/test_tools.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/maestro/realdebrid/tools.py tests/unit/realdebrid/test_tools.py src/maestro/server.py
git commit -m "feat(realdebrid): 7 MCP tools with filter-gate overlay on cache check"
```

---

## Phase 6 — Stremio addon protocol domain

Goal: 6 tools that speak the Stremio addon protocol (`/manifest.json` + `/stream/{type}/{id}.json`). These are the generic primitives the composer chains. Two are MCP tools that perform IO (query addons); rest are pure-compute transforms.

### Task 6.1: Generic Stremio addon client

**Files:**
- Create: `src/maestro/stremio/__init__.py`
- Create: `src/maestro/stremio/client.py`
- Create: `tests/unit/stremio/__init__.py`
- Create: `tests/unit/stremio/test_client.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/stremio/__init__.py`: empty.

Write to `tests/unit/stremio/test_client.py`:

```python
"""Stremio addon client tests."""

import httpx
import pytest
import respx

from maestro.errors import AddonMalformed, AddonTimeout
from maestro.stremio.client import StremioAddonClient


@pytest.fixture
def client() -> StremioAddonClient:
    return StremioAddonClient(timeout_s=5.0)


@respx.mock
@pytest.mark.asyncio
async def test_get_manifest_returns_addon_manifest(client: StremioAddonClient) -> None:
    respx.get("https://addon.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "addon", "version": "1.0.0", "name": "T"})
    )
    manifest = await client.get_manifest("https://addon.example/manifest.json")
    assert manifest["id"] == "addon"


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_returns_list(client: StremioAddonClient) -> None:
    respx.get(
        "https://addon.example/stream/series/tt1234567:1:3.json"
    ).mock(return_value=httpx.Response(200, json={"streams": [
        {"name": "test", "title": "S01E03 1080p", "infoHash": "abc"},
    ]}))

    streams = await client.query_stream(
        addon_url="https://addon.example",
        content_type="series",
        imdb_id="tt1234567",
        season=1,
        episode=3,
    )
    assert len(streams) == 1
    assert streams[0]["infoHash"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_timeout_raises_addon_timeout(client: StremioAddonClient) -> None:
    respx.get(
        "https://addon.example/stream/movie/tt9999.json"
    ).mock(side_effect=httpx.TimeoutException("slow"))

    with pytest.raises(AddonTimeout):
        await client.query_stream(
            addon_url="https://addon.example",
            content_type="movie",
            imdb_id="tt9999",
        )


@respx.mock
@pytest.mark.asyncio
async def test_query_stream_malformed_json_raises(client: StremioAddonClient) -> None:
    respx.get(
        "https://addon.example/stream/movie/tt9999.json"
    ).mock(return_value=httpx.Response(200, text="not json"))

    with pytest.raises(AddonMalformed):
        await client.query_stream(
            addon_url="https://addon.example",
            content_type="movie",
            imdb_id="tt9999",
        )


@respx.mock
@pytest.mark.asyncio
async def test_cinemeta_search_resolves_title_to_imdb_id(client: StremioAddonClient) -> None:
    respx.get(
        "https://v3-cinemeta.strem.io/catalog/series/top/search=Return%20to%20Eden.json"
    ).mock(return_value=httpx.Response(200, json={"metas": [
        {"id": "tt12345", "name": "Return to Eden", "year": 1983},
    ]}))

    imdb_id = await client.cinemeta_search(
        title="Return to Eden", content_type="series"
    )
    assert imdb_id == "tt12345"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/stremio/test_client.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/stremio/__init__.py`: empty.

Write to `src/maestro/stremio/client.py`:

```python
"""Generic Stremio addon client.

Speaks the Stremio addon protocol:
  GET /manifest.json
  GET /stream/{type}/{imdb_id}.json                (movies)
  GET /stream/{type}/{imdb_id}:{season}:{episode}.json  (series)

Also wraps Cinemeta search for title → imdb_id resolution.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from maestro.errors import AddonMalformed, AddonTimeout

log = structlog.get_logger("maestro.stremio.client")

CINEMETA_BASE = "https://v3-cinemeta.strem.io"


class StremioAddonClient:
    """Reusable client for any Stremio addon URL."""

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._timeout_s = timeout_s

    async def get_manifest(self, addon_url: str) -> dict[str, Any]:
        """GET <addon>/manifest.json."""
        url = addon_url.rstrip("/")
        if not url.endswith("/manifest.json"):
            url = f"{url}/manifest.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            raise AddonTimeout(message=f"manifest timeout: {addon_url}") from e
        except (httpx.HTTPError, ValueError) as e:
            raise AddonMalformed(message=f"manifest error: {e}") from e

    async def query_stream(
        self,
        addon_url: str,
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """GET <addon>/stream/<type>/<imdb_id>[:s:e].json → streams list."""
        if season is not None and episode is not None:
            path = f"/stream/{content_type}/{imdb_id}:{season}:{episode}.json"
        else:
            path = f"/stream/{content_type}/{imdb_id}.json"
        url = addon_url.rstrip("/").removesuffix("/manifest.json") + path

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as e:
            raise AddonTimeout(message=f"stream query timeout: {url}") from e
        except httpx.HTTPError as e:
            raise AddonMalformed(message=f"HTTP error: {e}") from e
        except ValueError as e:
            raise AddonMalformed(message=f"malformed JSON from {url}") from e

        streams = payload.get("streams", [])
        if not isinstance(streams, list):
            raise AddonMalformed(message=f"streams is not a list in {url}")
        return streams

    async def cinemeta_search(
        self,
        title: str,
        content_type: str,
    ) -> str | None:
        """Resolve title → IMDB id via Cinemeta search.

        Returns None on zero matches; caller decides whether to raise.
        """
        encoded = quote(title)
        url = f"{CINEMETA_BASE}/catalog/{content_type}/top/search={encoded}.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("cinemeta_search_failed", title=title)
            return None
        metas = payload.get("metas") or []
        if not metas:
            return None
        return metas[0].get("id")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/stremio/test_client.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/stremio/__init__.py src/maestro/stremio/client.py tests/unit/stremio/
git commit -m "feat(stremio): generic addon client — manifest, /stream/, Cinemeta search"
```

### Task 6.2: Stremio MCP tools + registration

**Files:**
- Create: `src/maestro/stremio/tools.py`
- Create: `tests/unit/stremio/test_tools.py`
- Modify: `src/maestro/server.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/stremio/test_tools.py`:

```python
"""Stremio tool tests."""

import asyncio
from typing import Any

import httpx
import pytest
import respx

from maestro.stremio.tools import (
    StremioToolset,
    stremio_dedupe_streams,
    stremio_filter_streams,
    stremio_rank_streams,
)


def test_dedupe_by_infohash() -> None:
    streams = [
        {"infoHash": "abc", "title": "1"},
        {"infoHash": "abc", "title": "2"},
        {"infoHash": "def", "title": "3"},
    ]
    deduped = stremio_dedupe_streams(streams)
    assert len(deduped) == 2


def test_filter_streams_by_language_keyword() -> None:
    streams = [
        {"title": "S01E03 English", "infoHash": "a"},
        {"title": "S01E03 Russian", "infoHash": "b"},
    ]
    filtered = stremio_filter_streams(streams, preferred_languages=["English"])
    assert len(filtered) == 1


def test_rank_streams_cached_first() -> None:
    streams = [
        {"title": "uncached", "infoHash": "a"},
        {"title": "cached", "infoHash": "b", "cached": True},
    ]
    ranked = stremio_rank_streams(streams, sort_strategy=["cached"])
    assert ranked[0]["infoHash"] == "b"


@respx.mock
@pytest.mark.asyncio
async def test_toolset_query_addon_wraps_client() -> None:
    respx.get(
        "https://addon.example/stream/series/tt1:1:3.json"
    ).mock(return_value=httpx.Response(200, json={"streams": [{"infoHash": "abc"}]}))

    toolset = StremioToolset(timeout_s=5.0)
    streams = await toolset.query_addon(
        addon_url="https://addon.example",
        content_type="series",
        imdb_id="tt1",
        season=1,
        episode=3,
    )
    assert streams[0]["infoHash"] == "abc"


@respx.mock
@pytest.mark.asyncio
async def test_query_addons_parallel_fans_out() -> None:
    respx.get(
        "https://a.example/stream/movie/tt9.json"
    ).mock(return_value=httpx.Response(200, json={"streams": [{"infoHash": "h1"}]}))
    respx.get(
        "https://b.example/stream/movie/tt9.json"
    ).mock(return_value=httpx.Response(200, json={"streams": [{"infoHash": "h2"}]}))

    toolset = StremioToolset(timeout_s=5.0)
    result = await toolset.query_addons_parallel(
        addon_urls=["https://a.example", "https://b.example"],
        content_type="movie",
        imdb_id="tt9",
    )
    flat = [s for addon_streams in result.values() for s in addon_streams]
    assert {"h1", "h2"} == {s["infoHash"] for s in flat}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/stremio/test_tools.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/stremio/tools.py`:

```python
"""Stremio addon protocol MCP tools (6 tools)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import FastMCP

from maestro.annotations import pure_compute, read_only
from maestro.stremio.client import StremioAddonClient


def stremio_dedupe_streams(streams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe by infohash, falling back to title when infohash absent."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for s in streams:
        key = s.get("infoHash") or s.get("title") or repr(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def stremio_filter_streams(
    streams: list[dict[str, Any]],
    *,
    preferred_languages: list[str] | None = None,
    exclude_quality_tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Post-fetch filtering for streams.

    `preferred_languages`: case-insensitive substring match against title/name.
    `exclude_quality_tags`: case-insensitive substring exclusion.
    """
    out = list(streams)
    if preferred_languages:
        out = [
            s for s in out
            if any(
                lang.lower() in (s.get("title", "") + s.get("name", "")).lower()
                for lang in preferred_languages
            )
        ]
    if exclude_quality_tags:
        out = [
            s for s in out
            if not any(
                tag.lower() in (s.get("title", "") + s.get("name", "")).lower()
                for tag in exclude_quality_tags
            )
        ]
    return out


def stremio_rank_streams(
    streams: list[dict[str, Any]],
    *,
    sort_strategy: list[str],
) -> list[dict[str, Any]]:
    """Sort streams by a hierarchy of keys.

    `sort_strategy`: ordered list of keys. Supported: cached, resolution,
    quality, size, seeders. Unknown keys are skipped.
    """
    def key_for(s: dict[str, Any]) -> tuple[Any, ...]:
        parts: list[Any] = []
        for k in sort_strategy:
            if k == "cached":
                parts.append(0 if s.get("cached") else 1)
            elif k == "resolution":
                title = (s.get("title", "") + s.get("name", "")).lower()
                for res, rank in [("4k", 0), ("1080p", 1), ("720p", 2), ("480p", 3)]:
                    if res in title:
                        parts.append(rank)
                        break
                else:
                    parts.append(99)
            elif k == "size":
                parts.append(-(s.get("size") or 0))
            elif k == "seeders":
                parts.append(-(s.get("seeders") or 0))
            else:
                parts.append(0)
        return tuple(parts)

    return sorted(streams, key=key_for)


class StremioToolset:
    """Holds the addon client + exposes per-method tool implementations."""

    def __init__(self, *, timeout_s: float = 10.0) -> None:
        self._client = StremioAddonClient(timeout_s=timeout_s)
        self._timeout_s = timeout_s

    async def query_addon(
        self,
        addon_url: str,
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query a single Stremio addon's /stream/ endpoint."""
        return await self._client.query_stream(
            addon_url=addon_url,
            content_type=content_type,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
        )

    async def query_addons_parallel(
        self,
        addon_urls: list[str],
        content_type: str,
        imdb_id: str,
        season: int | None = None,
        episode: int | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Parallel fan-out via asyncio.gather. Returns {url: streams}.

        Per-addon timeouts isolated — one slow addon doesn't kill the rest.
        """

        async def one(url: str) -> tuple[str, list[dict[str, Any]]]:
            try:
                streams = await self._client.query_stream(
                    addon_url=url,
                    content_type=content_type,
                    imdb_id=imdb_id,
                    season=season,
                    episode=episode,
                )
                return url, streams
            except Exception:
                return url, []

        results = await asyncio.gather(*(one(u) for u in addon_urls))
        return dict(results)

    async def get_manifest(self, addon_url: str) -> dict[str, Any]:
        """Fetch /manifest.json from an addon."""
        return await self._client.get_manifest(addon_url)


def register_tools(mcp: FastMCP, timeout_s: float = 10.0) -> StremioToolset:
    toolset = StremioToolset(timeout_s=timeout_s)

    mcp.tool(
        name="stremio_query_addon",
        annotations=read_only(title="Query Stremio Addon /stream/").model_dump(),
    )(toolset.query_addon)
    mcp.tool(
        name="stremio_query_addons_parallel",
        annotations=read_only(title="Parallel Fan-Out Across Addons").model_dump(),
    )(toolset.query_addons_parallel)
    mcp.tool(
        name="stremio_get_manifest",
        annotations=read_only(title="Get Addon Manifest").model_dump(),
    )(toolset.get_manifest)
    mcp.tool(
        name="stremio_dedupe_streams",
        annotations=pure_compute(title="Dedupe Streams by InfoHash").model_dump(),
    )(stremio_dedupe_streams)
    mcp.tool(
        name="stremio_filter_streams",
        annotations=pure_compute(title="Post-Filter Streams").model_dump(),
    )(stremio_filter_streams)
    mcp.tool(
        name="stremio_rank_streams",
        annotations=pure_compute(title="Rank Streams by Sort Strategy").model_dump(),
    )(stremio_rank_streams)
    return toolset
```

- [ ] **Step 4: Update server.py**

In `src/maestro/server.py`, add inside `create_server()`:

```python
    from maestro.stremio.tools import register_tools as register_stremio
    stremio_toolset = register_stremio(mcp, timeout_s=settings.http_timeout_s)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/unit/stremio/test_tools.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/maestro/stremio/tools.py tests/unit/stremio/test_tools.py src/maestro/server.py
git commit -m "feat(stremio): 6 MCP tools — query addon, parallel fan-out, dedupe/filter/rank"
```

---

## Phase 7 — `find_best_stream` composer (the killer feature)

Goal: one MCP tool that chains Cinemeta resolve → AIOStreams query → filter-gate overlay → re-sort → unrestrict → retry. Returns a single playable URL or a structured failure report.

### Task 7.1: StreamResolution result types

**Files:**
- Create: `src/maestro/compose/__init__.py`
- Create: `src/maestro/compose/types.py`
- Create: `tests/unit/compose/__init__.py`
- Create: `tests/unit/compose/test_types.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/compose/__init__.py`: empty.

Write to `tests/unit/compose/test_types.py`:

```python
"""StreamResolution result type tests."""

from maestro.compose.types import Attempt, StreamMetadata, StreamResolution


def test_resolution_can_be_success() -> None:
    res = StreamResolution(
        url="https://rd.example/x.mkv",
        metadata=StreamMetadata(
            resolution="1080p",
            codec="x264",
            language="English",
            size_gb=8.2,
        ),
        source="aiostreams",
        attempts=[],
        elapsed_ms=2840,
    )
    assert res.ok is True
    assert res.url == "https://rd.example/x.mkv"


def test_resolution_can_be_failure() -> None:
    res = StreamResolution(
        url=None,
        metadata=None,
        source="aiostreams",
        attempts=[
            Attempt(hash="abc", status="filter_gate_block", filename="x.WEB-DL.mkv"),
            Attempt(hash="def", status="unrestrict_4xx", error="403"),
        ],
        elapsed_ms=5210,
    )
    assert res.ok is False
    assert len(res.attempts) == 2


def test_metadata_optional_fields() -> None:
    m = StreamMetadata(resolution="720p")
    assert m.resolution == "720p"
    assert m.codec is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/compose/test_types.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/compose/__init__.py`: empty.

Write to `src/maestro/compose/types.py`:

```python
"""Result types for find_best_stream."""

from __future__ import annotations

from typing import Any, Literal

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/compose/test_types.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/compose/__init__.py src/maestro/compose/types.py tests/unit/compose/
git commit -m "feat(compose): StreamResolution + Attempt + StreamMetadata result types"
```

### Task 7.2: find_best_stream composer logic

**Files:**
- Create: `src/maestro/compose/find_best_stream.py`
- Create: `tests/unit/compose/test_find_best_stream.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/compose/test_find_best_stream.py`:

```python
"""find_best_stream composer tests with mocked sub-domains."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from maestro.compose.find_best_stream import find_best_stream
from maestro.realdebrid.filter_gate import FilterGateLearner


@pytest.fixture
def learner() -> FilterGateLearner:
    return FilterGateLearner(state_path=None)


@pytest.mark.asyncio
async def test_returns_playable_url_on_happy_path(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value="tt12345")
    stremio_query = AsyncMock(return_value=[
        {"infoHash": "abc", "title": "S01E03.1080p.BluRay.mkv", "url": "https://restricted/x"},
    ])
    rd_check_cache = AsyncMock(return_value={
        "abc": {"cached": True, "files": {}},
    })
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="Return to Eden",
        content_type="series",
        season=1,
        episode=3,
        preferred_languages=["English"],
        exclude_quality=["CAM"],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://aiostreams.example",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    assert result.url == "https://rd.example/cdn/x.mkv"


@pytest.mark.asyncio
async def test_returns_failure_when_cinemeta_misses(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value=None)

    result = await find_best_stream(
        title="Made-up Title Nobody Has",
        content_type="movie",
        season=None,
        episode=None,
        preferred_languages=["English"],
        exclude_quality=[],
        require_cached=True,
        fallback_to_uncached=False,
        aiostreams_addon_url="https://x",
        learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=AsyncMock(),
        rd_check_cache=AsyncMock(),
        rd_unrestrict=AsyncMock(),
        budget_s=60.0,
    )
    assert not result.ok
    assert result.suggestion is not None
    assert "imdb_id" in result.suggestion.lower()


@pytest.mark.asyncio
async def test_skips_filter_gate_risk_when_cached(learner: FilterGateLearner) -> None:
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(return_value=[
        {"infoHash": "h1", "title": "S01E03.WEB-DL.AMZN.mkv", "url": "https://r/1"},
        {"infoHash": "h2", "title": "S01E03.BluRay.mkv", "url": "https://r/2"},
    ])
    rd_check_cache = AsyncMock(return_value={
        "h1": {"cached": True, "files": {}},
        "h2": {"cached": True, "files": {}},
    })
    rd_unrestrict = AsyncMock(return_value={"download": "https://rd.example/cdn/x.mkv"})

    result = await find_best_stream(
        title="x", content_type="series", season=1, episode=3,
        preferred_languages=["English"], exclude_quality=[],
        require_cached=True, fallback_to_uncached=False,
        aiostreams_addon_url="https://x", learner=learner,
        cinemeta_search=cinemeta_search,
        stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=rd_unrestrict,
        budget_s=60.0,
    )
    assert result.ok
    rd_unrestrict.assert_called_once_with("https://r/2")


@pytest.mark.asyncio
async def test_retries_next_candidate_on_unrestrict_failure(learner: FilterGateLearner) -> None:
    from maestro.errors import UpstreamError

    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(return_value=[
        {"infoHash": "h1", "title": "S01E03.BluRay.mkv", "url": "https://r/1"},
        {"infoHash": "h2", "title": "S01E03.1080p.WEBRip.mkv", "url": "https://r/2"},
    ])
    rd_check_cache = AsyncMock(return_value={
        "h1": {"cached": True}, "h2": {"cached": True},
    })

    call_count = 0
    async def unrestrict_side(url: str) -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise UpstreamError(domain="realdebrid", message="403 infringing_file")
        return {"download": f"https://rd.example/cdn/{call_count}.mkv"}

    result = await find_best_stream(
        title="x", content_type="series", season=1, episode=3,
        preferred_languages=["English"], exclude_quality=[],
        require_cached=True, fallback_to_uncached=False,
        aiostreams_addon_url="https://x", learner=learner,
        cinemeta_search=cinemeta_search, stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=AsyncMock(side_effect=unrestrict_side),
        budget_s=60.0,
    )
    assert result.ok
    assert len(result.attempts) == 2
    assert result.attempts[0].status == "unrestrict_4xx"
    assert result.attempts[1].status == "success"


@pytest.mark.asyncio
async def test_no_cached_streams_without_fallback_returns_failure(
    learner: FilterGateLearner,
) -> None:
    cinemeta_search = AsyncMock(return_value="tt9")
    stremio_query = AsyncMock(return_value=[
        {"infoHash": "h1", "title": "x", "url": "https://r/1"},
    ])
    rd_check_cache = AsyncMock(return_value={"h1": {"cached": False}})

    result = await find_best_stream(
        title="x", content_type="movie", season=None, episode=None,
        preferred_languages=[], exclude_quality=[],
        require_cached=True, fallback_to_uncached=False,
        aiostreams_addon_url="https://x", learner=learner,
        cinemeta_search=cinemeta_search, stremio_query=stremio_query,
        rd_check_cache=rd_check_cache,
        rd_unrestrict=AsyncMock(),
        budget_s=60.0,
    )
    assert not result.ok
    assert result.suggestion is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/compose/test_find_best_stream.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/compose/find_best_stream.py`:

```python
"""find_best_stream composer.

Chains:
    1. Cinemeta resolve title → imdb_id
    2. Stremio query AIOStreams' /stream/ endpoint
    3. RD cache check (batch)
    4. Filter-gate overlay
    5. Sort candidates (cached & low-risk > cached & risk > uncached)
    6. Resolve top candidate via RD unrestrict
    7. On failure, pop next and retry; record attempts

Returns StreamResolution (success or structured failure with `attempts`).

This module is parameterized to accept callables for sub-domain
operations — keeps it test-friendly and avoids tight coupling.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from maestro.compose.types import Attempt, StreamMetadata, StreamResolution
from maestro.realdebrid.filter_gate import FilterGateLearner, RiskLevel

log = structlog.get_logger("maestro.compose.find_best_stream")

CinemetaSearch = Callable[[str, str], Awaitable[str | None]]
StremioQuery = Callable[..., Awaitable[list[dict[str, Any]]]]
RDCheckCache = Callable[[list[str]], Awaitable[dict[str, dict[str, Any]]]]
RDUnrestrict = Callable[[str], Awaitable[dict[str, Any]]]


async def find_best_stream(
    *,
    title: str,
    content_type: str,
    season: int | None,
    episode: int | None,
    preferred_languages: list[str],
    exclude_quality: list[str],
    require_cached: bool,
    fallback_to_uncached: bool,
    aiostreams_addon_url: str,
    learner: FilterGateLearner,
    cinemeta_search: CinemetaSearch,
    stremio_query: StremioQuery,
    rd_check_cache: RDCheckCache,
    rd_unrestrict: RDUnrestrict,
    budget_s: float,
) -> StreamResolution:
    """The composer. Returns one playable URL or a structured failure."""

    start = time.monotonic()
    attempts: list[Attempt] = []

    log.info("compose_start", title=title, content_type=content_type)

    imdb_id = await cinemeta_search(title, content_type)
    if imdb_id is None:
        return StreamResolution(
            url=None, metadata=None, source="aiostreams", attempts=[],
            elapsed_ms=_elapsed(start),
            suggestion="Cinemeta returned no matches; pass imdb_id directly if you have it",
        )

    raw_streams = await stremio_query(
        addon_url=aiostreams_addon_url,
        content_type=content_type,
        imdb_id=imdb_id,
        season=season,
        episode=episode,
    )

    candidates: list[dict[str, Any]] = []
    for s in raw_streams:
        title_blob = (s.get("title") or "") + " " + (s.get("name") or "")
        title_blob_lower = title_blob.lower()
        if preferred_languages and not any(
            lang.lower() in title_blob_lower for lang in preferred_languages
        ):
            continue
        if exclude_quality and any(
            q.lower() in title_blob_lower for q in exclude_quality
        ):
            continue
        candidates.append(s)

    if not candidates:
        return StreamResolution(
            url=None, source="aiostreams", attempts=[],
            elapsed_ms=_elapsed(start),
            suggestion="AIOStreams returned 0 streams matching language/quality filters",
        )

    hashes = [c.get("infoHash") for c in candidates if c.get("infoHash")]
    cache_map = await rd_check_cache(hashes) if hashes else {}

    for c in candidates:
        h = c.get("infoHash")
        c["_cached"] = bool(cache_map.get(h, {}).get("cached", False))
        filename = _extract_filename(c)
        c["_filter_gate_risk"] = learner.predict_risk(filename).value
        c["_filename"] = filename

    candidates.sort(key=lambda x: (
        0 if x["_cached"] else 1,
        0 if x["_filter_gate_risk"] != RiskLevel.HIGH.value else 1,
    ))

    if require_cached and not fallback_to_uncached:
        candidates = [c for c in candidates if c["_cached"]]
        if not candidates:
            return StreamResolution(
                url=None, source="aiostreams", attempts=[],
                elapsed_ms=_elapsed(start),
                suggestion=(
                    "No cached candidates after filtering. Try fallback_to_uncached=True "
                    "or check that RD is still serving cached results for this title."
                ),
            )

    for c in candidates:
        if time.monotonic() - start >= budget_s:
            attempts.append(Attempt(status="timeout", error=f"budget {budget_s}s exhausted"))
            break

        h = c.get("infoHash")
        filename = c.get("_filename")
        title_blob = c.get("title") or c.get("name") or ""

        risk = c.get("_filter_gate_risk")
        if risk == RiskLevel.HIGH.value and not fallback_to_uncached:
            attempts.append(Attempt(
                hash=h, title=title_blob, filename=filename,
                status="filter_gate_block",
            ))
            continue

        restricted_url = c.get("url")
        if not restricted_url:
            attempts.append(Attempt(
                hash=h, title=title_blob, status="no_url",
                error="stream had no url field",
            ))
            continue

        try:
            result = await rd_unrestrict(restricted_url)
        except Exception as e:
            err_str = str(e).lower()
            if "infringing_file" in err_str:
                learner.record_strike(filename or "", "infringing_file")
                learner.save_state()
                attempts.append(Attempt(
                    hash=h, title=title_blob, filename=filename,
                    status="unrestrict_403_infringing",
                    error=str(e)[:200],
                ))
            else:
                attempts.append(Attempt(
                    hash=h, title=title_blob, filename=filename,
                    status="unrestrict_4xx",
                    error=str(e)[:200],
                ))
            continue

        download = result.get("download")
        if not download:
            attempts.append(Attempt(
                hash=h, title=title_blob, status="no_url",
                error="unrestrict returned no download URL",
            ))
            continue

        attempts.append(Attempt(
            hash=h, title=title_blob, filename=filename, status="success",
        ))
        return StreamResolution(
            url=download,
            metadata=_build_metadata(c),
            source="aiostreams",
            attempts=attempts,
            elapsed_ms=_elapsed(start),
        )

    return StreamResolution(
        url=None, source="aiostreams", attempts=attempts,
        elapsed_ms=_elapsed(start),
        suggestion=(
            "All candidates failed. Inspect `attempts` for per-candidate diagnostics. "
            "Common causes: RD filter-gate (May 2026), expired RD token, addon outage."
        ),
    )


def _extract_filename(stream: dict[str, Any]) -> str | None:
    """Pull a likely filename out of a stream dict."""
    if "filename" in stream:
        return stream["filename"]
    title = stream.get("title") or ""
    if "\n" in title:
        return title.splitlines()[0]
    return title or None


def _build_metadata(stream: dict[str, Any]) -> StreamMetadata:
    title_blob = ((stream.get("title") or "") + " " + (stream.get("name") or "")).lower()
    resolution = next(
        (r for r in ("4k", "1080p", "720p", "480p") if r in title_blob), None
    )
    codec = next(
        (c for c in ("x265", "x264", "av1", "hevc") if c in title_blob), None
    )
    return StreamMetadata(
        resolution=resolution,
        codec=codec,
        language="English" if "english" in title_blob else None,
        size_gb=None,
        source_addon="aiostreams",
    )


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/compose/test_find_best_stream.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/compose/find_best_stream.py tests/unit/compose/test_find_best_stream.py
git commit -m "feat(compose): find_best_stream composer with filter-gate-aware retry loop"
```

### Task 7.3: Register find_best_stream as MCP tool

**Files:**
- Modify: `src/maestro/compose/__init__.py`
- Modify: `src/maestro/server.py`
- Create: `tests/integration/compose/__init__.py`
- Create: `tests/integration/compose/test_registration.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/integration/compose/__init__.py`: empty.

Write to `tests/integration/compose/test_registration.py`:

```python
"""Verify find_best_stream is registered as an MCP tool."""

import os

import pytest


@pytest.fixture(autouse=True)
def env(monkeypatch: object) -> None:
    monkeypatch.setenv("MAESTRO_RD_TOKEN", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_BASE_URL", "https://example.com")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_UUID", "x")
    monkeypatch.setenv("MAESTRO_AIOSTREAMS_PASSWORD", "x")


def test_find_best_stream_registered() -> None:
    from maestro.server import create_server

    mcp = create_server()
    names = [t.name for t in mcp._tool_manager.list_tools()] if hasattr(mcp, "_tool_manager") else []
    assert "find_best_stream" in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/compose/test_registration.py -v
```

Expected: FAIL — not registered yet.

- [ ] **Step 3: Wire registration**

Replace `src/maestro/compose/__init__.py` with:

```python
"""Compose domain — `find_best_stream` killer feature."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from maestro.annotations import destructive
from maestro.compose.find_best_stream import find_best_stream as _composer
from maestro.compose.types import StreamResolution
from maestro.realdebrid.filter_gate import FilterGateLearner
from maestro.realdebrid.tools import RDToolset
from maestro.stremio.tools import StremioToolset


def register_tools(
    mcp: FastMCP,
    *,
    stremio_toolset: StremioToolset,
    rd_toolset: RDToolset,
    learner: FilterGateLearner,
    aiostreams_addon_url: str,
    compose_budget_s: float,
) -> None:
    """Register find_best_stream wired to all sub-domains."""

    async def find_best_stream_tool(
        title: str,
        type: str,
        season: int | None = None,
        episode: int | None = None,
        preferred_languages: list[str] | None = None,
        exclude_quality: list[str] | None = None,
        require_cached: bool = True,
        fallback_to_uncached: bool = False,
    ) -> dict[str, Any]:
        """Resolve a title to a single playable Real-Debrid URL.

        Chains AIOStreams (already configured by user) + RD cache check +
        May 2026 filter-gate heuristic + retry-on-fail.

        Returns either a successful StreamResolution with `url` set, or a
        structured failure with `attempts` showing per-candidate diagnostics
        and `suggestion` recommending next action.
        """
        result: StreamResolution = await _composer(
            title=title,
            content_type=type,
            season=season,
            episode=episode,
            preferred_languages=preferred_languages or ["English"],
            exclude_quality=exclude_quality or ["CAM", "TS", "SCR", "R5", "R6"],
            require_cached=require_cached,
            fallback_to_uncached=fallback_to_uncached,
            aiostreams_addon_url=aiostreams_addon_url,
            learner=learner,
            cinemeta_search=stremio_toolset._client.cinemeta_search,
            stremio_query=lambda addon_url, content_type, imdb_id, season, episode:
                stremio_toolset.query_addon(
                    addon_url=addon_url,
                    content_type=content_type,
                    imdb_id=imdb_id,
                    season=season,
                    episode=episode,
                ),
            rd_check_cache=lambda hashes: rd_toolset._client.check_cache(hashes),
            rd_unrestrict=rd_toolset._client.unrestrict_link,
            budget_s=compose_budget_s,
        )
        return result.model_dump()

    mcp.tool(
        name="find_best_stream",
        annotations=destructive(
            title="Find Best Stream (chains AIOStreams + RD + filter-gate)"
        ).model_dump(),
    )(find_best_stream_tool)
```

- [ ] **Step 4: Update server.py**

In `src/maestro/server.py`, expand `create_server()` to thread the toolsets together:

```python
def create_server() -> FastMCP:
    settings = MaestroSettings()
    configure_logging(format=settings.log_format, level=settings.log_level)
    log = structlog.get_logger("maestro.server")
    log.info("server_starting",
             aiostreams_base_url=str(settings.aiostreams_base_url),
             torrentio_base_url=str(settings.torrentio_base_url),
             http_timeout_s=settings.http_timeout_s)

    mcp = FastMCP(name="maestro")

    from maestro.aiostreams import register_tools as register_aiostreams
    register_aiostreams(mcp, settings)

    from maestro.torrentio.tools import register_tools as register_torrentio
    register_torrentio(mcp)

    from maestro.realdebrid.tools import register_tools as register_rd
    rd_toolset = register_rd(mcp, settings)

    from maestro.stremio.tools import register_tools as register_stremio
    stremio_toolset = register_stremio(mcp, timeout_s=settings.http_timeout_s)

    from maestro.compose import register_tools as register_compose
    register_compose(
        mcp,
        stremio_toolset=stremio_toolset,
        rd_toolset=rd_toolset,
        learner=rd_toolset._learner,
        aiostreams_addon_url=str(settings.aiostreams_base_url),
        compose_budget_s=settings.compose_budget_s,
    )

    return mcp
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/integration/compose/test_registration.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/maestro/compose/__init__.py src/maestro/server.py tests/integration/compose/
git commit -m "feat(compose): wire find_best_stream into FastMCP server with sub-domain deps"
```

---

## Phase 8 — Diagnostics

Goal: 2 nice-to-have v1.0 diagnostic tools + 1 deferred v1.x telemetry stub registered as not-yet-implemented.

### Task 8.1: Stack health + RD health

**Files:**
- Create: `src/maestro/diagnose/__init__.py`
- Create: `src/maestro/diagnose/stack_health.py`
- Create: `src/maestro/diagnose/tools.py`
- Create: `tests/unit/diagnose/__init__.py`
- Create: `tests/unit/diagnose/test_tools.py`
- Modify: `src/maestro/server.py`

- [ ] **Step 1: Write the failing test**

Write to `tests/unit/diagnose/__init__.py`: empty.

Write to `tests/unit/diagnose/test_tools.py`:

```python
"""Diagnostic tool tests."""

from typing import Any

import httpx
import pytest
import respx

from maestro.diagnose.tools import DiagnoseToolset
from maestro.realdebrid.filter_gate import FilterGateLearner


@respx.mock
@pytest.mark.asyncio
async def test_stack_health_pings_each_addon() -> None:
    respx.get("https://a.example/manifest.json").mock(
        return_value=httpx.Response(200, json={"id": "a"})
    )
    respx.get("https://b.example/manifest.json").mock(
        return_value=httpx.Response(500)
    )

    toolset = DiagnoseToolset(
        addon_urls=["https://a.example", "https://b.example"],
        rd_get_user_info=None,
        learner=FilterGateLearner(state_path=None),
        timeout_s=5.0,
    )
    health = await toolset.stack_health()
    assert health["addons"]["https://a.example"]["status"] == "ok"
    assert health["addons"]["https://b.example"]["status"] == "error"


@pytest.mark.asyncio
async def test_rd_health_reports_auth_state() -> None:
    from unittest.mock import AsyncMock

    rd_user = AsyncMock(return_value={"username": "clay", "premium": 1})
    learner = FilterGateLearner(state_path=None)

    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=rd_user,
        learner=learner,
        timeout_s=5.0,
    )
    health = await toolset.rd_health()
    assert health["authenticated"] is True
    assert health["username"] == "clay"


@pytest.mark.asyncio
async def test_rd_health_reports_filter_gate_learning_count() -> None:
    from unittest.mock import AsyncMock

    learner = FilterGateLearner(state_path=None)
    learner.record_strike("x.NOVELKW.mkv", "infringing_file")

    toolset = DiagnoseToolset(
        addon_urls=[],
        rd_get_user_info=AsyncMock(return_value={"username": "x"}),
        learner=learner,
        timeout_s=5.0,
    )
    health = await toolset.rd_health()
    assert health["filter_gate"]["learned_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/diagnose/test_tools.py -v
```

Expected: FAIL.

- [ ] **Step 3: Write minimal implementation**

Write to `src/maestro/diagnose/__init__.py`: empty.

Write to `src/maestro/diagnose/stack_health.py`:

```python
"""Stack health probe — pings each addon's manifest endpoint."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


async def probe_addon(addon_url: str, *, timeout_s: float) -> dict[str, Any]:
    """Single addon probe. Returns {status, latency_ms, error?}."""
    url = addon_url.rstrip("/").removesuffix("/manifest.json") + "/manifest.json"
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(url, follow_redirects=True)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if response.status_code >= 400:
                return {
                    "status": "error",
                    "latency_ms": elapsed_ms,
                    "error": f"HTTP {response.status_code}",
                }
            return {
                "status": "ok",
                "latency_ms": elapsed_ms,
                "manifest_id": response.json().get("id"),
            }
    except (httpx.HTTPError, ValueError) as e:
        return {
            "status": "error",
            "latency_ms": int((time.monotonic() - start) * 1000),
            "error": str(e),
        }


async def probe_all(addon_urls: list[str], *, timeout_s: float) -> dict[str, dict[str, Any]]:
    results = await asyncio.gather(*(probe_addon(u, timeout_s=timeout_s) for u in addon_urls))
    return dict(zip(addon_urls, results, strict=True))
```

Write to `src/maestro/diagnose/tools.py`:

```python
"""Diagnostic MCP tool definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp import FastMCP

from maestro.annotations import read_only
from maestro.diagnose.stack_health import probe_all
from maestro.realdebrid.filter_gate import FilterGateLearner

RDUserInfoFn = Callable[[], Awaitable[dict[str, Any]]]


class DiagnoseToolset:
    def __init__(
        self,
        *,
        addon_urls: list[str],
        rd_get_user_info: RDUserInfoFn | None,
        learner: FilterGateLearner,
        timeout_s: float = 10.0,
    ) -> None:
        self._addon_urls = addon_urls
        self._rd_get_user_info = rd_get_user_info
        self._learner = learner
        self._timeout_s = timeout_s

    async def stack_health(self) -> dict[str, Any]:
        """Ping each configured addon's manifest. Returns per-addon status + latency."""
        addons = await probe_all(self._addon_urls, timeout_s=self._timeout_s)
        return {"addons": addons}

    async def rd_health(self) -> dict[str, Any]:
        """Verify RD auth + report filter-gate learning state."""
        auth_state: dict[str, Any] = {"authenticated": False}
        if self._rd_get_user_info is not None:
            try:
                info = await self._rd_get_user_info()
                auth_state = {
                    "authenticated": True,
                    "username": info.get("username"),
                    "premium": info.get("premium"),
                }
            except Exception as e:
                auth_state = {"authenticated": False, "error": str(e)[:200]}
        return {
            **auth_state,
            "filter_gate": {
                "known_count": len(self._learner.export_state()["known_keywords"]),
                "learned_count": len(self._learner.learned_keywords),
                "learned_keywords": list(self._learner.learned_keywords.keys()),
            },
        }

    async def dud_rate(self, window: str = "7d") -> dict[str, Any]:
        """v1.x stub — returns 'not_implemented' until persistent telemetry lands."""
        return {
            "status": "not_implemented_v1",
            "message": (
                "diagnose_dud_rate requires a persistent telemetry layer "
                "(deferred to v1.x). See docs/specs/2026-05-21-maestro-design.md "
                "'Open questions deferred to v1.x'."
            ),
            "window": window,
        }


def register_tools(
    mcp: FastMCP,
    *,
    addon_urls: list[str],
    rd_get_user_info: RDUserInfoFn,
    learner: FilterGateLearner,
    timeout_s: float = 10.0,
) -> None:
    toolset = DiagnoseToolset(
        addon_urls=addon_urls,
        rd_get_user_info=rd_get_user_info,
        learner=learner,
        timeout_s=timeout_s,
    )

    mcp.tool(
        name="diagnose_stack_health",
        annotations=read_only(title="Probe Addon Stack Health").model_dump(),
    )(toolset.stack_health)
    mcp.tool(
        name="diagnose_rd_health",
        annotations=read_only(title="Probe Real-Debrid Auth + Filter-Gate State").model_dump(),
    )(toolset.rd_health)
    mcp.tool(
        name="diagnose_dud_rate",
        annotations=read_only(title="Dud-Rate Telemetry (v1.x stub)").model_dump(),
    )(toolset.dud_rate)
```

Update `src/maestro/server.py` to wire it inside `create_server()` after compose:

```python
    from maestro.diagnose.tools import register_tools as register_diagnose
    register_diagnose(
        mcp,
        addon_urls=[str(settings.aiostreams_base_url), str(settings.torrentio_base_url)],
        rd_get_user_info=rd_toolset._client.get_user_info,
        learner=rd_toolset._learner,
        timeout_s=settings.http_timeout_s,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/unit/diagnose/test_tools.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maestro/diagnose/ tests/unit/diagnose/ src/maestro/server.py
git commit -m "feat(diagnose): 3 health-probe tools (stack_health, rd_health, dud_rate v1.x stub)"
```

---

## Phase 9 — Release readiness (manual + smoke)

Goal: end-to-end verification in real Claude clients + smoke tests against live upstream + final README.

### Task 9.1: Full unit + integration + schema_fidelity test pass

**Files:** none modified — release gate.

- [ ] **Step 1: Run full non-smoke suite**

```bash
uv run pytest tests/unit tests/integration tests/schema_fidelity -v
```

Expected: ALL PASS. Total ≥ 70 tests across phases.

- [ ] **Step 2: Run coverage report**

```bash
uv run pytest --cov=maestro tests/unit tests/integration
```

Expected: coverage ≥ 75% (per `[tool.coverage.report]` fail_under in pyproject.toml).

- [ ] **Step 3: Lint + type clean**

```bash
uv run ruff check && uv run ruff format --check && uv run basedpyright
```

Expected: all three exit 0.

- [ ] **Step 4: No commit (verification gate)**

### Task 9.2: Smoke test workflow scaffold

**Files:**
- Create: `.github/workflows/smoke.yaml`
- Create: `tests/smoke/__init__.py`
- Create: `tests/smoke/test_live_rd_user_info.py`

- [ ] **Step 1: Write the smoke test**

Write to `tests/smoke/__init__.py`: empty.

Write to `tests/smoke/test_live_rd_user_info.py`:

```python
"""Live RD auth smoke test (opt-in via MAESTRO_SMOKE=1)."""

import os

import pytest

from maestro.config import MaestroSettings
from maestro.realdebrid.client import RDClient

pytestmark = pytest.mark.smoke


@pytest.mark.skipif(
    os.environ.get("MAESTRO_SMOKE") != "1",
    reason="MAESTRO_SMOKE=1 required",
)
@pytest.mark.asyncio
async def test_live_rd_user_info_returns_account() -> None:
    settings = MaestroSettings()
    client = RDClient(
        api_token=settings.rd_token.get_secret_value(),
        timeout_s=settings.http_timeout_s,
    )
    try:
        info = await client.get_user_info()
    finally:
        await client.aclose()
    assert "username" in info
```

- [ ] **Step 2: Write the smoke CI workflow**

Write to `.github/workflows/smoke.yaml`:

```yaml
name: Smoke

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch: {}

jobs:
  smoke:
    runs-on: ubuntu-latest
    env:
      MAESTRO_SMOKE: "1"
      MAESTRO_RD_TOKEN: ${{ secrets.MAESTRO_RD_TOKEN }}
      MAESTRO_AIOSTREAMS_BASE_URL: ${{ secrets.MAESTRO_AIOSTREAMS_BASE_URL }}
      MAESTRO_AIOSTREAMS_UUID: ${{ secrets.MAESTRO_AIOSTREAMS_UUID }}
      MAESTRO_AIOSTREAMS_PASSWORD: ${{ secrets.MAESTRO_AIOSTREAMS_PASSWORD }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen
      - run: uv run pytest tests/smoke -v -m smoke
```

- [ ] **Step 3: Verify smoke workflow YAML is valid**

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/smoke.yaml'))" && echo "yaml ok"
```

Expected: `yaml ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/smoke.yaml tests/smoke/
git commit -m "ci(smoke): nightly + manual-dispatch live-upstream smoke workflow"
```

### Task 9.3: Refresh-fixtures script

**Files:**
- Create: `scripts/refresh_fixtures.sh`

- [ ] **Step 1: Write the script**

Write to `scripts/refresh_fixtures.sh`:

```bash
#!/usr/bin/env bash
# Refresh integration-test fixtures from live upstream.
#
# Requires the same env vars as the smoke workflow. Saves real responses
# to tests/integration/<domain>/fixtures/.
#
# Usage:
#   MAESTRO_RD_TOKEN=... MAESTRO_AIOSTREAMS_UUID=... \
#   MAESTRO_AIOSTREAMS_PASSWORD=... ./scripts/refresh_fixtures.sh <domain>
#
# Where <domain> is one of: aiostreams, realdebrid, stremio

set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
    echo "usage: $0 <domain>"
    echo "  domain ∈ {aiostreams, realdebrid, stremio}"
    exit 1
fi

FIXTURE_DIR="tests/integration/${DOMAIN}/fixtures"
mkdir -p "$FIXTURE_DIR"

case "$DOMAIN" in
    aiostreams)
        if [[ -z "${MAESTRO_AIOSTREAMS_BASE_URL:-}" ]]; then
            echo "MAESTRO_AIOSTREAMS_BASE_URL not set" >&2
            exit 1
        fi
        echo "[refresh] fetching AIOStreams config via GET /api/v1/user"
        curl -sS \
            -u "${MAESTRO_AIOSTREAMS_UUID}:${MAESTRO_AIOSTREAMS_PASSWORD}" \
            "${MAESTRO_AIOSTREAMS_BASE_URL%/}/api/v1/user/${MAESTRO_AIOSTREAMS_UUID}" \
            | python -m json.tool > "${FIXTURE_DIR}/get_config_response.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/get_config_response.json"
        ;;
    realdebrid)
        if [[ -z "${MAESTRO_RD_TOKEN:-}" ]]; then
            echo "MAESTRO_RD_TOKEN not set" >&2
            exit 1
        fi
        echo "[refresh] fetching RD user info"
        curl -sS \
            -H "Authorization: Bearer ${MAESTRO_RD_TOKEN}" \
            "https://api.real-debrid.com/rest/1.0/user" \
            | python -m json.tool > "${FIXTURE_DIR}/get_user_response.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/get_user_response.json"
        ;;
    stremio)
        echo "[refresh] fetching Cinemeta sample (no auth needed)"
        curl -sSL \
            "https://v3-cinemeta.strem.io/catalog/series/top/search=Severance.json" \
            | python -m json.tool > "${FIXTURE_DIR}/cinemeta_search_severance.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/cinemeta_search_severance.json"
        ;;
    *)
        echo "unknown domain: $DOMAIN" >&2
        exit 1
        ;;
esac

echo "[refresh] done."
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/refresh_fixtures.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/refresh_fixtures.sh
git commit -m "scripts: refresh_fixtures.sh — pull live JSON for integration replay"
```

### Task 9.4: Install + exercise in Claude Code CLI

**Files:** none modified — manual verification.

- [ ] **Step 1: Install Maestro locally via uv**

```bash
uv build
uv tool install --reinstall ./dist/clayworks_maestro_mcp-0.1.0-py3-none-any.whl
maestro-mcp --help 2>&1 | head -5
```

Expected: `maestro-mcp` on PATH; running with stdin closed exits cleanly (no traceback). FastMCP `--help` may or may not exist; either way no startup crash.

- [ ] **Step 2: Write Claude Code MCP config**

Write to `~/.claude/mcp/maestro.json`:

```json
{
  "mcpServers": {
    "maestro": {
      "command": "maestro-mcp",
      "args": [],
      "env": {
        "MAESTRO_RD_TOKEN": "<your-rd-token>",
        "MAESTRO_AIOSTREAMS_BASE_URL": "https://aiostreams.elfhosted.com",
        "MAESTRO_AIOSTREAMS_UUID": "<your-uuid>",
        "MAESTRO_AIOSTREAMS_PASSWORD": "<your-password>"
      }
    }
  }
}
```

(If Claude Code uses a different config path on this machine — check `~/.claude/CLAUDE.md` for the canonical MCP-server config location and adjust accordingly.)

- [ ] **Step 3: Restart Claude Code and verify tools appear**

In a fresh Claude Code session, list MCP servers + tools:

```
/mcp
```

Expected output includes `maestro` server with all 43 tools listed under it.

- [ ] **Step 4: Exercise the killer tool**

In the Claude Code session:

```
Use the maestro find_best_stream tool to resolve Severance S02E05 for me.
```

Expected: Claude calls `find_best_stream` with `title="Severance", type="series", season=2, episode=5`. Maestro returns a `StreamResolution` dict with `url` set, or a structured failure with `attempts` populated.

If the tool returns failure, inspect `attempts[]` and `suggestion` and follow the diagnostic chain.

- [ ] **Step 5: Exercise read-only tools**

```
Show me my AIOStreams config — but don't include secrets.
```

Expected: Claude calls `aiostreams_get_config(include_secrets=False)`. Output shows redacted credentials.

```
What templates are available for AIOStreams?
```

Expected: Claude calls `aiostreams_get_template_list()`. Returns Tamtaro Complete SEL Setup v2.6.1.

```
Check if these infohashes are cached on RD: abc123, def456.
```

Expected: Claude calls `realdebrid_check_cache(infohashes=[...])`. Returns list with filter-gate overlay.

- [ ] **Step 6: No commit (manual verification)**

### Task 9.5: Final README + tag v0.1.0

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Expand README with install + tool surface + config**

Replace `README.md` with:

```markdown
# Maestro by Clayworks

> Python MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks.

Maestro lets an AI agent (Claude Code, Cursor, Claude Desktop) read, audit, and write configurations across a user's existing Stremio addons — primarily AIOStreams (Tamtaro SEL Setup) and Torrentio — and chain those primitives into a `find_best_stream` composer that resolves a single playable Real-Debrid URL per title query.

## What it does

- **43 MCP tools** across 6 domains: AIOStreams config CRUD (21), Torrentio URL builder (5), Real-Debrid integration (7), Stremio addon protocol (6), `find_best_stream` composer (1), diagnostics (3).
- **Filter-gate learning loop:** May 2026 RD post-cache filtering is detected at runtime; learned keywords persist to `~/.config/maestro/filter_gate_state.json`.
- **Staged writes:** AIOStreams config mutations are staged in memory; `aiostreams_save()` is the only call that hits the remote API.
- **MCP-spec annotations:** every tool declares `readOnlyHint` / `destructiveHint` / `title`.

## Install

```bash
uv tool install clayworks-maestro-mcp
```

Or with pipx:

```bash
pipx install clayworks-maestro-mcp
```

## Configure

Maestro reads its configuration from environment variables. The standard MCP-Desktop pattern is to set them in your client's MCP config file.

### Claude Code CLI (`~/.claude/mcp/maestro.json`)

```json
{
  "mcpServers": {
    "maestro": {
      "command": "maestro-mcp",
      "env": {
        "MAESTRO_RD_TOKEN": "your-real-debrid-api-token",
        "MAESTRO_AIOSTREAMS_BASE_URL": "https://aiostreams.elfhosted.com",
        "MAESTRO_AIOSTREAMS_UUID": "your-uuid",
        "MAESTRO_AIOSTREAMS_PASSWORD": "your-password"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

Same shape — see [Claude Desktop MCP docs](https://claude.com/docs/connectors/custom/desktop-extensions).

### All env vars

| Env var | Required | Default | Purpose |
|---|---|---|---|
| `MAESTRO_RD_TOKEN` | yes | — | Real-Debrid API token |
| `MAESTRO_AIOSTREAMS_BASE_URL` | yes | — | e.g. `https://aiostreams.elfhosted.com` |
| `MAESTRO_AIOSTREAMS_UUID` | yes | — | Your AIOStreams user UUID |
| `MAESTRO_AIOSTREAMS_PASSWORD` | yes | — | Your AIOStreams raw password (not the encrypted token from install URL) |
| `MAESTRO_TORRENTIO_BASE_URL` | no | `https://torrentio.strem.fun` | Override for self-hosted Torrentio |
| `MAESTRO_HTTP_TIMEOUT_S` | no | `15.0` | Per-request timeout |
| `MAESTRO_RETRY_ATTEMPTS` | no | `3` | 5xx retry attempts per domain |
| `MAESTRO_COMPOSE_BUDGET_S` | no | `60.0` | Total time budget for `find_best_stream` |
| `MAESTRO_LOG_FORMAT` | no | `json` | `json` or `console` |
| `MAESTRO_LOG_LEVEL` | no | `INFO` | stdlib logging level |
| `MAESTRO_FILTER_GATE_STATE_PATH` | no | `~/.config/maestro/filter_gate_state.json` | Persistent filter-gate learning state |

## Killer tool: `find_best_stream`

```
find_best_stream(
    title: str,
    type: "movie" | "series",
    season: int | None = None,
    episode: int | None = None,
    preferred_languages: list[str] = ["English"],
    exclude_quality: list[str] = ["CAM", "TS", "SCR", "R5", "R6"],
    require_cached: bool = True,
    fallback_to_uncached: bool = False,
) -> StreamResolution
```

Returns a single playable Real-Debrid URL, or a structured failure report with per-candidate `attempts` and a `suggestion`.

## How it works

See [docs/specs/2026-05-21-maestro-design.md](docs/specs/2026-05-21-maestro-design.md) for the full design spec.

## Development

```bash
git clone https://github.com/clayboicardi/maestro
cd maestro
uv sync
uv run pytest                              # unit + integration + schema_fidelity
uv run ruff check && uv run basedpyright   # lint + type check
```

Live-upstream smoke tests require credentials and are opt-in:

```bash
MAESTRO_SMOKE=1 \
MAESTRO_RD_TOKEN=... \
MAESTRO_AIOSTREAMS_BASE_URL=... \
MAESTRO_AIOSTREAMS_UUID=... \
MAESTRO_AIOSTREAMS_PASSWORD=... \
  uv run pytest tests/smoke -v -m smoke
```

## License

MIT — see [LICENSE](LICENSE).

## Status

v0.1.0 — initial release. See [CHANGELOG.md](CHANGELOG.md) for changes.
```

- [ ] **Step 2: Update CHANGELOG**

Replace `CHANGELOG.md` with:

```markdown
# Changelog

All notable changes to Maestro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-XX

### Added

- 43 MCP tools across 6 domains (AIOStreams CRUD, Torrentio URL builder, Real-Debrid, Stremio protocol, `find_best_stream` composer, diagnostics)
- AIOStreams Zod → Pydantic auto-gen pipeline pinned to v2.29.6
- May 2026 Real-Debrid filter-gate runtime learning loop with persistent state
- Staged-write commit pattern for AIOStreams (PUT-full-replace semantics handled transparently)
- Per-tool MCP annotations (`readOnlyHint` / `destructiveHint` / `title`) enforced via CI lint
- `find_best_stream` composer with retry-on-fail across cached candidates
- CI: lint + multi-Python (3.12/3.13/3.14) + schema fidelity drift check
- Smoke CI: nightly + manual-dispatch live-upstream verification
```

- [ ] **Step 3: Tag v0.1.0**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: final README + CHANGELOG for v0.1.0"
git tag -a v0.1.0 -m "Maestro v0.1.0 — initial release"
git log --oneline -5
```

Expected: tag `v0.1.0` on the last commit; `git log` shows recent history.

- [ ] **Step 4: Build distribution (do NOT publish to PyPI without Clay's explicit go-ahead)**

```bash
uv build
ls dist/
```

Expected: `clayworks_maestro_mcp-0.1.0-py3-none-any.whl` + `clayworks-maestro-mcp-0.1.0.tar.gz` in `dist/`.

- [ ] **Step 5: Stop. Surface PyPI publish + GitHub push decisions to Clay**

Per Clay's `feedback_draft_before_publishing_under_clays_name`: publishing to PyPI and pushing to `github.com/clayboicardi/maestro` are publish-under-Clay's-name actions. **Stop here** and surface for explicit approval:

```
v0.1.0 built locally. Tag v0.1.0 created on master. Two publish steps need your explicit go-ahead:

1. `git remote add origin git@github.com:clayboicardi/maestro.git && git push -u origin master --tags`
   This makes the repo public on GitHub under your name.

2. `uv publish dist/clayworks_maestro_mcp-0.1.0-py3-none-any.whl`
   This publishes to PyPI under the `clayworks-maestro-mcp` distribution name.

Both reversible (delete tag / yank package) but visible. Want me to proceed with one, both, or neither?
```

---

## Self-review checklist

After completing all phases, verify:

### Spec coverage

- [x] Section 1 architecture → Phase 0 (project foundation), Phase 1 (core scaffolding) cover repo layout + tooling + env config + auth model + logging
- [x] Section 2 tool surface → Phases 3-8 implement all 43 tools (21 AIOStreams, 5 Torrentio, 7 RD, 6 Stremio, 1 composer, 3 diagnostics)
- [x] Section 3 data flows → Phase 7 composer matches Flow A; Phase 3 stager matches Flow B; Phase 5 client matches Flow C
- [x] Section 4 error handling → Phase 1 error taxonomy; Phase 5 filter-gate learning loop; per-domain client error mapping in Phases 3, 5, 6
- [x] Section 5 testing → unit/integration/smoke/schema_fidelity all created; CI workflow in Phase 0; smoke workflow in Phase 9; in-Claude exercise in Task 9.4

### Placeholder scan

No "TBD", "TODO", "implement later", or "similar to Task N" patterns. Every code block contains the actual content the engineer needs.

### Type consistency

- `PendingMutation` defined in `aiostreams/modify.py` Task 3.2, used by all write-tool tasks (3.5-3.8)
- `StreamResolution` defined in `compose/types.py` Task 7.1, consumed by composer in Task 7.2 and tool registration in Task 7.3
- `FilterGateLearner` defined in Task 5.2, threaded through RD tools (5.3), composer (7.3), and diagnostics (8.1)
- `MaestroSettings` env-var names locked in Task 1.2; consumed unchanged by registration functions across phases

### Open follow-ups (deferred to v1.x per spec)

- CI auto-regen PR-bot for AIOStreams schemas
- Persistent telemetry for `diagnose_dud_rate`
- MCP Inspector in CI
- URL-paste-and-decrypt AIOStreams password extraction
- Configurable scoring profiles for composer
- Multi-instance AIOStreams support
- `diagnose_recent_errors(window)` tool
- Hybrid search+execute tool pattern (defer to evidence)
- MCPB packaging (will invoke `mcp-server-dev:build-mcpb`)
- Elicitation for destructive-tool confirmations
- Anthropic Directory submission (deferred indefinitely)

---

## Execution handoff

Plan complete and saved to `docs/plans/2026-05-21-maestro-v1-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. Uses `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?







