# Changelog

All notable changes to Maestro will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-05-29

A post-v0.1.0 systematic code-review campaign (eight subsystem-scoped PRs) plus a
polish pass: two new discovery tools, a batch of security fixes, and CI/supply-chain
hardening. No tool *names* were removed or renamed; `aiostreams_get_active_template`
and `aiostreams_apply_template` change where the active-template marker is stored.

### Added

- Two Torrentio discovery tools — `torrentio_list_sort_options` and `torrentio_list_debrid_providers` (snapshot of the upstream enums; pure-compute, no network). The catalog is now 45 MCP tools.
- Public redaction surface for the fixture-refresh path: a `redact_config()` wrapper and a `python -m maestro.aiostreams.redact <in> <out>` CLI, replacing a heredoc that imported the private `_redact_secrets`.
- `compose_addon_url` promoted to package-public in `maestro.stremio` (alongside `normalize_addon_base_url`) so the diagnose health probe composes addon URLs without reaching into a private symbol.
- CI/supply-chain hardening: SHA-pinned actions + Dependabot (github-actions), pinned `uv` version, top-level least-privilege `permissions: contents: read`, `concurrency` (cancel-in-progress per ref) + `timeout-minutes` on every job, `persist-credentials: false` on checkout, and the coverage gate scoped to the 3.12 matrix entry.
- The live-upstream smoke workflow opens/updates a `smoke-canary` tracking issue on failure, in an isolated job so the `issues:write` token never coexists with the provider secrets.
- schema-fidelity tests pin the codegen OUTPUT (catches `constants.ts` + toolchain drift, not just the input schema) and enforce pin-sync between the regen script and the recorded hash.
- `REVIEW-CAMPAIGN-2026.md` — public-facing roadmap for the review campaign.

### Changed

- **`aiostreams_get_active_template` / `aiostreams_apply_template`**: the active-template marker now lives in the schema's `appliedTemplates` list (`{id, version}`), not the fictional `presets.active`. AIOStreams v2.29.6 declares `presets: list[Preset3]` (required, `extra="forbid"`), so the old dict-shaped write was invalid; `get` returns the most-recent `appliedTemplates` entry that is a known maestro template (ignoring AIOStreams-native entries), and `apply` de-dupes by id while preserving foreign entries.
- Torrentio config mirrors upstream wire semantics: singular `language=` key, lowercased `sort` / `debrid_provider`, refreshed `QUALITY_FILTERS` + `SORT_OPTIONS` (dead constants removed), and `extra="forbid"` on `TorrentioConfig`.
- `diagnose_stack_health`, `diagnose_rd_health`, `diagnose_dud_rate` declare `idempotentHint=false` — they sample changing upstream state (RD account, addon reachability, filter-gate strikes), so MCP clients should not memoize their results.
- `SchemaError.suggestion` default is now `None` (it is generic across domains); each raise site passes a domain-appropriate suggestion explicitly.
- `scripts/refresh_fixtures.sh` hardened: guards all `MAESTRO_AIOSTREAMS_*` vars, `curl --fail-with-body` + atomic rename + cleanup trap, and routes JSON through `uv run python`.

### Fixed

- **aiostreams**: `get_active_template` / `apply_template` no longer crash on real configs — the old `presets.active` access raised `AttributeError` / `TypeError` because `presets` is a populated list (see Changed).
- **stremio**: URL handling rewritten via `urlparse` / `urlunparse` to preserve query strings (e.g. authenticated `?token=` manifests) through normalization + path composition; non-dict JSON roots in `query_stream` / `cinemeta_search` are caught; cinemeta title slashes are escaped.
- **composer**: `find_best_stream` respects an explicit empty candidate list; language-token matching drops 3-letter codes + audio markers that caused false matches.
- **diagnose**: `stack_health` / `rd_health` probes are crash-proof (non-dict guard, query-safe URL composition, sanitized + collision-free probe keys, tiered error catching) — one bad addon degrades to a per-addon `status="error"` instead of sinking the probe.
- **realdebrid**: filter-gate state persists only when `learned_keywords` actually mutated, and `load_state` recovers from `UnicodeDecodeError` as well as `JSONDecodeError`.
- **torrentio**: URL handling hardened (anchored `re.sub` + `removesuffix` + regex boundary); query strings / fragments stripped before key-value extraction.
- **composer errors**: `NoStreamsAvailable`, `TitleUnresolved`, `CompositionFailure` now carry class-level `message` defaults (previously surfaced as e.g. `"CompositionFailure: "` with an empty message).

### Security

- **`aiostreams._redact_secrets` now actually redacts.** It checked a singular `credential` key while the schema declares `credentials` (plural dict), so `aiostreams_get_config` / `aiostreams_get_services` returned debrid bearer tokens + API keys raw. Now iterates `services[].credentials`, nine top-level sensitive fields (`encryptedPassword`, `addonPassword`, `rpdbApiKey`, `topPosterApiKey`, `aioratingsApiKey`, `openposterdbApiKey`, `tmdbAccessToken`, `tmdbApiKey`, `tvdbApiKey`), the optional `proxy.credentials` surface, the nested `parentConfig.password`, and dynamic `presets[].options` secret keys. (Bug present since v0.1.0.)
- **stremio**: exception messages + logs no longer leak secrets — URLs are sanitized (drop query / fragment / userinfo) before surfacing, and logs use `parsed.hostname` not `parsed.netloc` (SECURITY-HIGH: removed a `netloc` fallback that could echo `user:pass@`).
- **torrentio**: `debrid_key` + `extra` config values are wrapped in `SecretStr`; error previews are truncated.
- **realdebrid**: the bearer token is scrubbed from the 4xx response-body excerpt at the client layer, so it can't leak through the exception → MCP-logging path.

### Stats

- 252 default-suite tests + 1 opt-in smoke test; coverage gate 75% (current ~93%).
- All gates clean: `ruff check`, `ruff format --check`, `basedpyright`.

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

[0.2.0]: https://github.com/clayboicardi/maestro/releases/tag/v0.2.0
[0.1.0]: https://github.com/clayboicardi/maestro/releases/tag/v0.1.0
