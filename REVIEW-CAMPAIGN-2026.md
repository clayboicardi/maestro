# Maestro Review Campaign — 2026

I'm running a systematic code-review campaign on this repository using Gemini Code Assist plus a triangulating second opinion from `/octo:review` and an independent project-scoped review session. This document is the public-facing roadmap for that work.

The campaign opened on 2026-05-22, the same day the Gemini configuration landed (commit `57a5103`) and the same day `v0.1.0` was tagged and released. The repository went public on 2026-05-22 immediately after the v0.1.0 lock, so the review surface has buyer-grade scrutiny from PR 1 forward rather than maintenance-cycle scrutiny.

## Methodology

Per review PR:

1. Open a targeted, single-subsystem PR.
2. Wait for the Gemini Code Assist auto-review.
3. Run `/octo:review` (Claude + Gemini providers) for triangulation.
4. An independent project-scoped session produces a third read against the same diff.
5. Synthesize a three-bucket punch list: must-fix, should-consider, skip with rationale.
6. Implement approved fixes on a separate fix branch, one atomic commit per fix.
7. Merge the fix PR with a merge commit; close the review PR as an audit record (review PRs never merge).

Review PRs target a 200-500 line scope. One subsystem per PR. Test files are reviewed alongside the code they cover. No auto-formatter runs bundle into a review PR; no generated files bundle into a review PR.

A finding qualifies as **Must-fix** when at least two of the three reviewers flag it and at least one tags severity HIGH or higher, or when a single reviewer tags CRITICAL. **Should-consider** covers anything two reviewers flag at any severity, plus single-reviewer HIGH findings that hold up on inspection. **Skip-with-rationale** covers single-reviewer findings at MEDIUM or below that inspection shows don't apply.

## Audit Findings (compressed)

- **Repo snapshot:** HEAD `baffba9` (the v0.1.0 lock commit), 77 commits in the last six months — which is the entire repo history; the project shipped all nine implementation phases plus release readiness in ~30 hours across 2026-05-21 and 2026-05-22.
- **Top subsystems by source file count:** `aiostreams/` (7), `torrentio/` (4), `realdebrid/` (4), `stremio/` (3), `compose/` (3), `diagnose/` (3), plus seven cross-cutting top-level modules (`server.py`, `errors.py`, `middleware.py`, `annotations.py`, `config.py`, `logging.py`, `__init__.py`).
- **Per-domain handwritten LoC:** `aiostreams/` ~765 (plus 2266 LoC of auto-generated schemas excluded from review), `realdebrid/` 594, `compose/` 521, `stremio/` 421, `torrentio/` 325, `diagnose/` 200. Cross-cutting top-level modules total ~370 LoC.
- **Recent hotspots:** `src/maestro/server.py` (12 commits), `src/maestro/aiostreams/tools.py` (10), `README.md` (8), `pyproject.toml` (7), `src/maestro/annotations.py` (4). Hotspot pattern matches phase progression — `server.py` evolves every phase as new domains wire in, `aiostreams/tools.py` reflects the 21-tool build-out.
- **Existing audit artifacts:** none in-repo. The pre-v0.1.0 audit trail lived in working sessions; this is the first formal post-release audit.
- **Test coverage signal:** 34 test files against 31 handwritten source files. Tests cover every domain; the breakdown is 32 unit, 7 integration (one tool-registration test per domain), 3 schema-fidelity, and 2 smoke (smoke is opt-in via `MAESTRO_SMOKE=1`). Coverage measured locally at ~92%.
- **CI gates currently enforced:** ruff lint, ruff format check, basedpyright type check, pytest across Python 3.12, 3.13, and 3.14. A nightly smoke workflow runs the same opt-in live-upstream tests against pinned Action secrets; the first manual dispatch ran SUCCESS on 2026-05-22 in 19 seconds.
- **CI gap surfaced by the audit:** `pyproject.toml` declares `[tool.coverage.report] fail_under = 75`, but the CI workflow runs `pytest` without `--cov`, so the threshold is declared but not enforced. The ~92% coverage figure in README and CHANGELOG is a local-run artifact, not a CI guarantee. A one-line CI fix to gate this is on the post-release follow-up tracker; review PR 8 may surface it independently.
- **TODO/FIXME density:** one marker total, and inspection shows it's a false positive — the implementation-plan document itself asserts "no TODO patterns" in its own text. True in-code TODO debt is zero. Deferred items are tracked in the post-release follow-up document rather than as in-code markers.

## Locked Subsystem Inventory

The campaign covers eight review PRs. Each maps to a subsystem chunked to fit Gemini's review window plus the triangulating reviewers' attention. Five candidate seed items from the master plan (Python conventions, MCP protocol compliance, secret management, test coverage on public tool surface, and standalone error-handling) fold into the per-domain PRs rather than getting standalone PRs, since ruff plus basedpyright already gate the cross-cutting concerns and test files review alongside the code they cover.

| # | Subsystem | Tier | PR Count | Focus areas |
|---|---|---|---|---|
| 1 | Server + `MaestroErrorMiddleware` + error taxonomy + config + logging + tool annotations | HIGH | 1 | MCP stdio rule, structlog → stderr, pydantic-settings env-var loading, error-payload translation at the wire boundary, per-tool MCP annotations completeness |
| 2 | AIOStreams client + tools + modify + templates + staged-write commit | HIGH | 1 | Staged-write `_modify(fn)` plus `aiostreams_save()` PUT-full-replace contract, 21-tool surface, template fetch and merge, `SecretStr` discipline on basic-auth credentials |
| 3 | Real-Debrid client + filter-gate runtime learner | HIGH | 1 | Persistent state-file safety, learning-loop side effects, bearer-token redaction, async-client lifecycle trade-offs |
| 4 | Composer (`find_best_stream`) + Stremio addon-protocol client (bundled) | HIGH | 1 | Killer-feature chain order (AIOStreams → RD cache → filter-gate heuristic → RD unrestrict → retry), structured failure with `attempts[]` plus `suggestion`, tenacity backoff bounds, generic Stremio addon-protocol client |
| 5 | Torrentio URL codec | MEDIUM | 1 | Pure-compute pipe-delimited encode and decode round-trip correctness, provider and quality and language enum freshness, environment-variable wiring follow-up |
| 6 | Diagnostics health probes | MEDIUM | 1 | Three health-probe tools, idempotency and timeout discipline on probe HTTP, stub-tool semantics |
| 7 | AIOStreams schema-generation pipeline | MEDIUM | 1 | Zod → JSON Schema → Pydantic toolchain integrity, two-file re-pin invariant (script version constant plus schema SHA file), drift detector, generated-code lint exemption |
| 8 | CI workflows + repository scripts | MEDIUM | 1 | CI lint and type and test matrix, smoke workflow secret discipline, fixture-refresh script hardening, coverage threshold gating |

Total review PRs: 8.

## Execution Sequence

### PR 1: Server + middleware + error taxonomy + config + logging + annotations (calibration)

- **Branch:** `review-server-middleware-1`
- **Severity threshold:** `LOW` (calibration PR for this repo; threshold for PR 2 onward is picked from this PR's noise floor)
- **Scope:** The cross-cutting infrastructure that every MCP tool runs through — the FastMCP server entry point, the wire-boundary error middleware that translates project exceptions into structured client errors, the typed exception taxonomy, the pydantic-settings env-var loader, the structlog logger, and the per-tool MCP annotations registry. This PR opens the campaign because findings here ripple to every subsequent PR.
- **Focus areas (priority order):**
  1. The MCP stdio invariant: stdout must stay empty because it carries the JSON-RPC frame, so no `print()` and no untyped library calls that could emit to stdout. All logging goes through structlog to stderr.
  2. Error-payload translation contract: every `MaestroException` raised inside a tool must become a structured MCP error payload at the wire boundary via the middleware. Subclass coverage in the error taxonomy.
  3. Per-tool annotations completeness: every registered MCP tool declares its `ToolAnnotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`). The MCP wire format mandates camelCase here; the ruff `N815` rule is intentionally suppressed for `annotations.py` and that suppression must hold.
  4. `SecretStr` discipline: every credential field uses `SecretStr`, and comparisons use `.get_secret_value()`. Pydantic v2's `SecretStr.__eq__` does not compare to plain strings, so equality checks against raw strings are a silent bug.
- **Files in scope:** `src/maestro/server.py`, `src/maestro/middleware.py`, `src/maestro/errors.py`, `src/maestro/config.py`, `src/maestro/logging.py`, `src/maestro/annotations.py`, and the tests covering each (`tests/unit/test_server.py`, `test_middleware.py`, `test_errors.py`, `test_config.py`, `test_logging.py`, `test_annotations.py`).
- **Non-goals:** the per-domain tool registrations referenced from `server.py` (those are exercised in their respective domain PRs), and the FastMCP framework internals (out of repo scope; the project pins `fastmcp>=3.0,<4.0`).

### PR 2: AIOStreams client + tools + modify + templates + staged-write

- **Branch:** `review-aiostreams-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The largest domain by both file count and tool surface: the async AIOStreams client, the 21 MCP tools that operate on it, the staged-write commit pattern that handles AIOStreams' PUT-full-replace semantics transparently, and the Tamtaro template fetch and merge logic.
- **Focus areas (priority order):**
  1. Staged-write contract: `_modify(transform_fn)` fetches the current `UserData`, applies the transform, and stages it in memory; only `aiostreams_save()` mutates remote state via PUT to `/api/v1/user`. No partial PATCH calls. Writes are not retried on error because the staging buffer is the safety net.
  2. The 21-tool surface coverage: every tool emits the correct annotations, accepts the right input shape per the generated schemas, and handles the credential-redaction default on read tools.
  3. Template fetch and merge: Tamtaro template fetch, merge against the staged buffer, conflict semantics, and the apply-template tool's DESTRUCTIVE annotation plus confirmation gate.
  4. Basic-auth credential handling: `SecretStr` for `MAESTRO_AIOSTREAMS_PASSWORD`, `.get_secret_value()` discipline on the auth header construction.
- **Files in scope:** `src/maestro/aiostreams/client.py`, `tools.py`, `modify.py`, `templates.py`, `schemas.py` (hand-overlay validators), and the nine `tests/unit/aiostreams/*` files.
- **Non-goals:** `schemas_generated.py` (auto-generated and lint-exempt; reviewed in PR 7 as part of the schema-generation pipeline), schema-fidelity drift detection (also PR 7).

### PR 3: Real-Debrid + filter-gate runtime learner

- **Branch:** `review-realdebrid-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The async Real-Debrid client, the seven RD tools, and the May 2026 filter-gate runtime learning loop with persistent state at `~/.config/maestro/filter_gate_state.json`.
- **Focus areas (priority order):**
  1. Persistent state-file safety: atomic write semantics (write to temp file then rename), corruption recovery on read failure, schema versioning for future filter-gate format changes, file-permission handling.
  2. Bearer-token redaction across the logging surface: the `MAESTRO_RD_TOKEN` is loaded as `SecretStr`, never logged at any level, and any debug output redacts to the last-four-chars pattern.
  3. Learning-loop side effects: `record_strike_and_persist` writes through to disk on every recorded strike; the bounded-retry decision logic respects the persisted state across process restarts.
  4. Async-client lifecycle trade-off: `RDClient.aclose` is intentionally never invoked at shutdown because the stdio-MCP process exit closes sockets; this is documented as an acceptable trade-off and the choice should be re-affirmed during review.
- **Files in scope:** `src/maestro/realdebrid/client.py`, `tools.py`, `filter_gate.py`, and `tests/unit/realdebrid/test_client.py`, `test_filter_gate.py`, `test_tools.py`.
- **Non-goals:** RD API specification drift (upstream concern), `find_best_stream` consumption of the filter-gate (covered in PR 4).

### PR 4: Composer (`find_best_stream`) + Stremio addon-protocol client

- **Branch:** `review-composer-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The killer composer that chains AIOStreams → RD cache check → filter-gate heuristic → RD unrestrict → retry, plus the generic Stremio addon-protocol client it depends on. Bundled because the Stremio client's only v1.0 consumer is the composer; reviewing them together gives Gemini the full dependency context.
- **Focus areas (priority order):**
  1. Chain-order correctness: the composer queries AIOStreams once, trusts the user's already-configured aggregation, and then walks candidates in order against the RD cache check + filter-gate heuristic + unrestrict + retry sequence. No parallel fan-out across aggregators.
  2. Structured failure: when no candidate resolves, the composer returns a structured `attempts[]` payload plus a `suggestion` string. The result types live in `compose/types.py`; the `StreamResolution`, `Attempt`, and `StreamMetadata` shapes must round-trip cleanly through the MCP wire format.
  3. Tenacity backoff bounds: retry attempts have an explicit budget (`MAESTRO_COMPOSE_BUDGET_S` default 60 seconds) and the per-attempt timeout (`MAESTRO_HTTP_TIMEOUT_S` default 15). Bounded retries with exponential backoff plus jitter; cap retries to avoid amplification against upstream.
  4. Stremio addon-protocol client: generic manifest fetch plus `/stream/` query against any Stremio-compatible addon, used by the composer as the underlying retrieval mechanism. URL normalization, timeout discipline, error mapping to project exceptions.
- **Files in scope:** `src/maestro/compose/find_best_stream.py`, `types.py`, `__init__.py`, `src/maestro/stremio/client.py`, `tools.py`, `__init__.py`, and the matching `tests/unit/compose/*` and `tests/unit/stremio/*` files.
- **Non-goals:** the AIOStreams client this composer queries (covered in PR 2), the RD client and filter-gate this composer chains through (covered in PR 3).

### PR 5: Torrentio URL codec

- **Branch:** `review-torrentio-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The Torrentio domain: the pipe-delimited URL configuration encode and decode pipeline, the provider, quality, and language enums sourced from upstream `filter.js`, and the five MCP tools that build and parse Torrentio install URLs. This is pure compute — no I/O — so the blast radius is the smallest of any subsystem.
- **Focus areas (priority order):**
  1. `parse_url` round-trip correctness: given a Torrentio install URL, decode it to a config struct and re-encode; round-trip equality must hold for the full grammar.
  2. Enum freshness: the provider, quality, language, and limit enums match upstream Torrentio's `filter.js` as of the pinned reference. Drift detection on enum mismatch is acceptable; silent provider drops are not.
  3. Known follow-ups from the post-release tracker that are in scope to verify-not-re-audit: an environment-variable override for the base URL that is currently loaded but not propagated through the encoder; a silent drop behavior on invalid `limit=` values in `parse_url`; the 24-provider error message verbosity; a dead helper function. These four have documented dispositions and this PR's review confirms those dispositions hold rather than re-deriving them.
- **Files in scope:** `src/maestro/torrentio/encoder.py`, `enums.py`, `tools.py`, `__init__.py`, and `tests/unit/torrentio/test_encoder.py`, `test_enums.py`, `test_tools.py`.
- **Non-goals:** Torrentio upstream API changes (out of repo scope), composition with `find_best_stream` (which currently does not use Torrentio in v1.0; covered in PR 4).

### PR 6: Diagnostics health probes

- **Branch:** `review-diagnose-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The three diagnostic health-probe tools: `stack_health` (probes the full configured stack), `rd_health` (RD-only health), and `dud_rate` (a v1.x stub whose stated behavior should match its actual delivery).
- **Focus areas (priority order):**
  1. Idempotency and timeout discipline on probe HTTP: every probe respects the configured per-request timeout and is safe to invoke repeatedly without side effects.
  2. `dud_rate` v1.x stub semantics: the stub should be honest about what it currently returns versus what its docstring suggests; under-promise rather than over-promise.
  3. Probe-error catch path coverage: `probe_addon`'s exception handling for `HTTPError` and `ValueError` should be exercised by tests.
- **Files in scope:** `src/maestro/diagnose/stack_health.py`, `tools.py`, `__init__.py`, and `tests/unit/diagnose/test_tools.py`.
- **Non-goals:** the underlying domain clients these probes call (covered in their respective PRs), production observability stack design (out of scope for v0.1.0).

### PR 7: AIOStreams schema-generation pipeline

- **Branch:** `review-schema-gen-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The Zod → JSON Schema → Pydantic toolchain that auto-generates `schemas_generated.py` from upstream AIOStreams' `schemas.ts` at a pinned version, plus the schema-fidelity drift detector that fails CI when upstream changes the schema without a corresponding re-pin.
- **Focus areas (priority order):**
  1. Two-file re-pin invariant: re-pinning to a new AIOStreams version means updating **both** the version constant inside `scripts/regen_aiostreams_schemas.sh` **and** `tests/schema_fidelity/aiostreams_schema.sha256` (the SHA file is exactly 65 bytes, LF-terminated). The drift detector compares live `schemas.ts` against the pinned SHA. Either file out of sync produces a confusing failure mode.
  2. Generated-code lint-exemption coverage: `schemas_generated.py` is generated and ships unmodified; ruff's per-file `ALL` ignore rule covers it; basedpyright's exclude list covers it. Both ignores must hold so a future formatter run can't accidentally rewrite the file.
  3. Pipeline integrity: the Bash script's `npx zod-to-json-schema` plus `uvx datamodel-code-generator` chain produces a stable file across runs at the same pinned version; the output is deterministic enough that re-running on a clean checkout produces a byte-identical file.
- **Files in scope:** `scripts/regen_aiostreams_schemas.sh`, `tests/schema_fidelity/aiostreams_schema.sha256`, `tests/schema_fidelity/test_aiostreams_schema_pinned.py`, and the per-file-ignore configuration in `pyproject.toml`.
- **Non-goals:** the runtime use of the generated schemas (covered in PR 2 as part of the AIOStreams client and tools), upstream AIOStreams schema design (out of repo scope).

### PR 8: CI workflows + repository scripts

- **Branch:** `review-ci-scripts-1`
- **Severity threshold:** TBD per PR 1 outcome
- **Scope:** The two GitHub Actions workflows (`ci.yaml` plus `smoke.yaml`), the fixture-refresh helper script, and any cross-cutting CI hardening surfaced during review.
- **Focus areas (priority order):**
  1. CI matrix integrity: `ci.yaml` runs ruff check, ruff format check, basedpyright, and pytest across Python 3.12, 3.13, and 3.14. The lint, format check, and type check are documented as distinct steps because `ruff check` is not the same as `ruff format --check`. Both must run on every PR.
  2. Smoke workflow secret discipline: `smoke.yaml` reads four secrets from the repository settings, never logs them, and the workflow's manual-dispatch plus nightly-cron schedule combination is intentional. Action-secret-leak surface holds.
  3. Fixture-refresh helper hardening: the `scripts/refresh_fixtures.sh` helper currently has three known nits — environment-variable defaulting under `set -u`, write-then-rename atomicity for fixture files, and `curl --fail` to reject HTTP error responses as fixtures. These three have documented fixes pending in the post-release follow-up tracker.
  4. Coverage threshold gating: the audit found that `pyproject.toml` declares `[tool.coverage.report] fail_under = 75` but the CI workflow runs `pytest` without `--cov`, so the threshold is not enforced. A one-line CI fix is on the post-release tracker; this PR's review may surface it independently as a consistency-with-README finding.
- **Files in scope:** `.github/workflows/ci.yaml`, `.github/workflows/smoke.yaml`, `scripts/refresh_fixtures.sh`. The sibling `scripts/regen_aiostreams_schemas.sh` is reviewed in PR 7.
- **Non-goals:** GitHub Actions runner internals (out of scope), the smoke-test test bodies (covered as part of PR 3's RD client review where the smoke test lives).

## Repo-Specific Notes

- **Default branch:** `master` (not `main`). Every review PR and every fix PR targets `master`.
- **Verification per PR (Phase 1 Step 13):** the project's standard quality gate, which mirrors `.github/workflows/ci.yaml` exactly with the addition of `ruff format --check` per the developer-notes hard invariant that `ruff check` and `ruff format --check` are distinct.

  ```bash
  uv run pytest tests/unit tests/schema_fidelity tests/integration \
    && uv run ruff check . \
    && uv run ruff format --check . \
    && uv run basedpyright
  ```

- **CI gates currently enforced:** ruff lint, ruff format check, basedpyright type check, pytest matrix on Python 3.12, 3.13, and 3.14. Smoke workflow runs nightly at 06:00 UTC and on manual dispatch; the smoke run is opt-in via `MAESTRO_SMOKE=1` and gated on four repository secrets that are now configured.
- **Coverage threshold:** declared at 75% in `pyproject.toml`, but the CI workflow does not currently invoke pytest with `--cov`, so the threshold is not yet enforced in CI. The README's ~92% figure is a local-run measurement. This is on the post-release tracker as a one-line CI step addition; PR 8 may surface it independently.
- **`CHANGELOG.md` is in `.gemini/ignore_patterns`.** Gemini will not review CHANGELOG entries directly; their accuracy surfaces through `/octo:review` and the project-scoped session.
- **Hard invariants** that every review verifies regardless of which subsystem the PR scopes to: stdout must stay empty (no `print()`, no untyped libraries that warn to stdout), `SecretStr` fields use `.get_secret_value()` for any comparison or auth-header construction, and the schema-regeneration script and SHA file must stay in sync as a two-file pin.
- **Release context:** `v0.1.0` was tagged and a GitHub Release published on 2026-05-22. The repository went public the same day. The PyPI package has not yet been published; that step is deferred pending separate authorization.

## End-of-Campaign Synthesis

This section fills out at the end of the campaign with: subsystems reviewed, must-fix items shipped, should-consider items deferred with rationale, skip-rationale categories, and patterns observed for the cross-repo synthesis after all five campaign repos complete.
