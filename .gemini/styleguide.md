# maestro Style & Review Guide

Tells Gemini Code Assist what matters when reviewing changes to this Python MCP server.

## Python Conventions

- Python 3.12+. Modern syntax (`match`, walrus where it actually helps, structural pattern matching for parsers).
- Type hints on every public function. `from __future__ import annotations` where forward refs help.
- Async/await discipline: no blocking I/O in coroutines without `asyncio.to_thread`.
- Error class hierarchy: domain exceptions inherit from a single project base.
- No bare `except:`. Always name the exception or use `except Exception:` with re-raise discipline.

## MCP Protocol Compliance

- Request / response shapes match the MCP spec strictly.
- Error codes within the documented set.
- Capability negotiation handles missing capabilities gracefully.
- Tool registration metadata complete and accurate.

## External Client Correctness

This server proxies several upstream APIs.

- Rate limiting respected on every external call.
- Auth refresh handled before token expiry, not after rejection.
- Timeouts on every external request. No bare `await session.get(...)` without timeout.
- Retries with exponential backoff + jitter; cap retries to avoid amplification.
- Idempotent operations where the upstream supports it.

## Secret Management

- API keys, tokens, debrid credentials: environment variables only.
- No secrets in logs at any level.
- Redact tokens in debug output (last 4 chars suffix pattern).
- `.env` files in `.gitignore` and never committed.

## Test Coverage Expectations

- Public tool surface: tested.
- Failure paths on each external client: tested with mocked HTTP.
- Schema generation pipeline: golden-file tested.
- Mocks at the network boundary only — not inside server logic.

## CI Workflow Integrity

- Tests run on every PR.
- Lint (ruff or equivalent) gates merge.
- Type-check (mypy strict) gates merge.
- Coverage threshold enforced.

## Schema Generation

- Output schemas validate against the MCP capability spec.
- Schema changes generate a versioned artifact.
- Backwards compatibility intentional: breaking changes call it out explicitly.

## Brand Separation

- No internal-only project terms, hook names, daemon names, or `C:\` paths in any file that ships.
- No references to the paid-bundle internals.

## Non-Goals

- Module structure of the existing codebase (already locked).
- Linter style nits (ruff handles).
- Type-annotation completeness in test fixtures.
