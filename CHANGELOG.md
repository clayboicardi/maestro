# Changelog

All notable changes to Maestro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `REVIEW-CAMPAIGN-2026.md` at the repo root — public-facing roadmap for the systematic code-review campaign on this repository (Gemini Code Assist auto-review plus `/octo:review` triangulation plus independent project-scoped review session, eight subsystem-scoped review PRs targeting `master`)

## [Unreleased]

### Changed

- `diagnose_stack_health`, `diagnose_rd_health`, `diagnose_dud_rate` now declare `idempotentHint=false`. They sample changing upstream state (RD account, addon reachability, filter-gate strikes), so repeated invocations are not equivalent and MCP clients should not memoize their results.
- `SchemaError.suggestion` default is now `None`. The previous default text was AIOStreams-specific ("Run scripts/regen_aiostreams_schemas.sh..."), but `SchemaError` is generic across domains. Each raise site now passes a domain-appropriate suggestion explicitly.

## [0.1.0] — 2026-05-22

### Added

- 43 MCP tools across 6 domains: 21 AIOStreams config CRUD, 5 Torrentio URL builder, 7 Real-Debrid integration, 6 Stremio addon protocol, 1 `find_best_stream` composer, 3 diagnostics health probes
- AIOStreams Zod → Pydantic auto-gen pipeline pinned to v2.29.6 with schema-fidelity drift detector
- May 2026 Real-Debrid filter-gate runtime learning loop with persistent state at `~/.config/maestro/filter_gate_state.json`
- Staged-write commit pattern for AIOStreams (PUT-full-replace semantics handled transparently via `aiostreams_save`)
- Per-tool MCP annotations (`readOnlyHint` / `destructiveHint` / `title`) declared per spec
- `find_best_stream` composer with retry-on-fail across cached candidates and structured failure carrying `attempts[]` + `suggestion`
- `MaestroErrorMiddleware` at the MCP boundary translating `MaestroException` payloads to structured client errors
- CI: lint + multi-Python (3.12/3.13/3.14) matrix
- Smoke CI: nightly cron + manual-dispatch live-upstream verification (opt-in via `MAESTRO_SMOKE=1` and GitHub Actions secrets)
- `scripts/refresh_fixtures.sh` for re-pulling live JSON into integration-test fixtures

### Stats at lock

- 181 default-suite tests + 1 opt-in smoke test
- Coverage: ~92% (threshold: 75%)
- All quality gates clean: `ruff check`, `ruff format --check`, `basedpyright`
- 9 implementation phases locked across 2 days (2026-05-21 → 2026-05-22)

[0.1.0]: https://github.com/clayboicardi/maestro/releases/tag/v0.1.0
