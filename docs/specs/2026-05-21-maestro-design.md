# Maestro by Clayworks — v1 Design Spec

**Date:** 2026-05-21
**Status:** Approved + best-practices-validated (design walkthrough complete; build-mcp-server skill consulted; awaiting Clay's spec review before plan phase)
**Authors:** Clay Haworth + ClaydeClaw (MCP-builder session)
**Co-author input:** parallel CC session ("Stremio + RD optimization") handoff doc, 2026-05-21
**Spec location (durable):** `<repo>/docs/specs/2026-05-21-maestro-design.md`
**Best-practices validation:** Anthropic MCP-server-dev skills consulted (`build-mcp-server` invoked; `build-mcpb` deferred to v1.x packaging). Mandatory tool annotations applied. Directory submission deferred indefinitely.

---

## Executive summary

Maestro is a local-install Python MCP server that gives an AI agent (Claude Code, Cursor, Claude Desktop, etc.) programmatic control over a user's Stremio + Real-Debrid stack. It is not a stream aggregator; it does not replace AIOStreams or Torrentio. Instead, it exposes ~43 tools across six domains so an agent can **read, audit, modify, and apply** configurations across the user's existing addons — and compose those primitives into a single `find_best_stream` resolution tool that returns one playable URL per title-query.

The product targets two outcomes:

1. **End the dud-rate problem at the source.** Users (Clay specifically) currently click 10–20 dud streams in Stremio before hitting one that plays. Maestro lets Claude tune AIOStreams' Tamtaro SEL setup, Torrentio's provider/filter config, and RD's filter-gate-avoidance heuristics — driving dud rate toward zero by *configuration*, not by post-hoc filtering.
2. **Ship the killer composer.** `find_best_stream(title, ...)` chains AIOStreams → RD-cache → filter-gate heuristic → RD-unrestrict → retry into a single tool call. This is the demoable "ask Claude for a stream, get a working URL" workflow.

Maestro is a Clayworks portfolio piece. Public artifact, MIT, PyPI-published, MCP-registry-listed.

---

## Context (the journey + what we ruled out)

This design started inside a different frame — "stream-finder MCP" — and pivoted mid-walkthrough when Clay surfaced his actual pain. Preserving the rejected paths so future readers see why decisions landed where they did:

| Frame | Why rejected |
|-------|-------------|
| **Stream-finder MCP (initial inherited frame)** | Would duplicate what AIOStreams already does. Clay's pain is *configuring* his existing aggregators, not building a parallel one. |
| **Dual-protocol (Cloudflare Worker + npm package)** | Required to serve Stremio addon endpoints AND MCP. Config-manager only frame eliminated the Stremio addon side; reduced to stdio MCP. |
| **TypeScript + Cloudflare Workers** | Adopted then rejected — local stdio MCP is the standard pattern for this surface; Python + FastMCP is more idiomatic for HTTP-shaping work and matches Clay's tooling preferences. |
| **Hand-translate Zod → Pydantic** | Adopted then rejected — AIOStreams `schemas.ts` shows ~1 commit / 2.5 days churn with monthly breaking changes. Auto-gen pipeline pays off ~5 months in. |
| **`find_best_stream` deferred to v1.x** | Adopted then rejected — handoff doc framed it as the killer feature that justifies the MCP existing. Compatible with the config-manager primary frame (composer uses user's *already-configured* AIOStreams). |
| **Multi-addon parallel fan-out inside the composer** | Rejected — AIOStreams *is* the aggregation layer. Maestro queries AIOStreams once and trusts the configured aggregation. No parallel sources in the composer. |

### Locked context (decisions standing as v1 ships)

- **Frame:** Config-manager primary, `find_best_stream` composer included, no Stremio addon side
- **Language:** Python 3.12 floor (also tested on 3.13, 3.14)
- **MCP framework:** FastMCP 3.x
- **Transport:** stdio (local install)
- **Distribution:** PyPI as `clayworks-maestro-mcp`; GitHub at `clayboicardi/maestro` (private until Clay approves publish)
- **License:** MIT
- **Brand:** Maestro by Clayworks
- **Spend:** RD-only ($18/6mo). No TorBox/AllDebrid/Easynews integration in v1 or v1.x.
- **User's target stack:** Tamtaro Complete SEL Setup v2.6.1 on AIOStreams (free public ElfHosted instance) + standalone Torrentio (English-trimmed) + Cinemeta + supporting addons (per 2026-05-21 optimization session)

---

## Section 1 — Architecture

### Stack

| Layer | Choice | Note |
|-------|--------|------|
| Language | Python 3.12 (floor) | matches FastMCP idiom + Clay's tooling |
| MCP framework | FastMCP 3.x | dev clone available at `Projects/fastmcp-3.2.0/` for reference |
| Package mgmt | uv | already installed (0.10.6) |
| Lint + format | ruff | installed (0.15.14) |
| Type check | basedpyright | installed (1.39.5) + LSP-wired to Claude Code |
| HTTP client | httpx (async) | shared AsyncClient per domain |
| Validation | pydantic v2 + pydantic-settings | maps cleanly to AIOStreams' Zod schemas |
| Logging | structlog | JSON to stderr (stdio MCP can't use stdout) |
| Test | pytest + pytest-asyncio + respx | respx for httpx mocking |
| CI | GitHub Actions | matrix on 3.12/3.13/3.14 |

### Repository layout

```
maestro/
├── src/maestro/
│   ├── __init__.py
│   ├── server.py                # FastMCP server entry, tool registration
│   ├── config.py                # pydantic-settings, env-var sourced
│   │
│   ├── aiostreams/              # Domain 1
│   │   ├── client.py            # async httpx client for /api/v1/user
│   │   ├── schemas.py           # hand-overlay validators (runtime refinements)
│   │   ├── schemas_generated.py # auto-produced by regen script; do not edit
│   │   ├── templates.py         # Tamtaro/Vidhin template fetch + merge
│   │   └── tools.py
│   │
│   ├── torrentio/               # Domain 2
│   │   ├── encoder.py           # pipe-delimited URL config encode/decode
│   │   ├── enums.py             # provider/quality/language enums from filter.js
│   │   └── tools.py
│   │
│   ├── realdebrid/              # Domain 3
│   │   ├── client.py
│   │   ├── schemas.py
│   │   ├── filter_gate.py       # May 2026 keyword heuristic + learning loop
│   │   └── tools.py
│   │
│   ├── stremio/                 # Domain 4
│   │   ├── client.py            # /manifest + /stream/ caller (any addon)
│   │   └── tools.py
│   │
│   ├── compose/                 # Domain 5
│   │   └── find_best_stream.py  # the killer composer
│   │
│   └── diagnose/                # Domain 6
│       ├── stack_health.py
│       └── tools.py
│
├── tests/
│   ├── unit/                    # pure logic, no I/O
│   ├── integration/             # replay fixtures via respx
│   ├── smoke/                   # live network, opt-in via MAESTRO_SMOKE=1
│   ├── schema_fidelity/         # CI guard against AIOStreams upstream drift
│   └── conftest.py
│
├── scripts/
│   ├── regen_aiostreams_schemas.sh  # Zod → JSON Schema → Pydantic pipeline
│   └── refresh_fixtures.sh          # manual, requires live creds
│
├── docs/
│   └── specs/2026-05-21-maestro-design.md  # this doc
│
├── .github/workflows/
│   ├── ci.yaml                  # lint + type + unit + integration + schema_fidelity
│   └── smoke.yaml               # manual dispatch + nightly cron
│
├── pyproject.toml               # uv + ruff + basedpyright + pytest config
├── README.md
├── LICENSE                      # MIT
└── CHANGELOG.md
```

### Auth + config

Maestro reads its own configuration from environment variables (sourced via `pydantic-settings`):

| Env var | Purpose | Required |
|---------|---------|----------|
| `MAESTRO_RD_TOKEN` | Real-Debrid API key | Yes (for RD + composer tools) |
| `MAESTRO_AIOSTREAMS_BASE_URL` | e.g., `https://aiostreams.elfhosted.com` | Yes (for AIOStreams tools) |
| `MAESTRO_AIOSTREAMS_UUID` | per-user UUID from AIOStreams setup | Yes |
| `MAESTRO_AIOSTREAMS_PASSWORD` | raw password (Basic-auth) | Yes |
| `MAESTRO_TORRENTIO_BASE_URL` | e.g., `https://torrentio.strem.fun` | Optional (only for Torrentio tools) |
| `MAESTRO_HTTP_TIMEOUT_S` | per-request timeout | Default 15 |
| `MAESTRO_RETRY_ATTEMPTS` | per-domain retries on 5xx | Default 3 |
| `MAESTRO_COMPOSE_BUDGET_S` | total budget for `find_best_stream` | Default 60 |
| `MAESTRO_LOG_FORMAT` | `json` (default) or `console` | Default `json` |

Standard MCP-Desktop pattern: these go in the `env` block of `claude_desktop_config.json` or `~/.claude/mcp/maestro.json`. They are never logged.

### Schema strategy

Auto-gen pipeline locked due to AIOStreams churn rate (~1 commit / 2.5 days on `schemas.ts`, ~monthly breaking changes):

```
Viren070/AIOStreams@<pinned-tag>/packages/core/src/db/schemas.ts (Zod TS)
            │
            ▼ scripts/regen_aiostreams_schemas.sh
            │   1. fetch schemas.ts at pinned tag
            │   2. npx zod-to-json-schema → schemas.json
            │   3. uvx datamodel-code-generator → schemas_generated.py
            ▼
src/maestro/aiostreams/schemas_generated.py  (Pydantic, auto, never edit)
            │
            ▼ imported by
src/maestro/aiostreams/schemas.py            (hand-overlay validators for
                                              runtime refinements like SEL
                                              max-length that don't survive
                                              auto-conversion)
```

Bumping AIOStreams = update pinned tag, run script, review diff in `schemas_generated.py`, manually update overlay validators if refinement logic changed. CI step in v1.x can automate as a PR-bot pattern.

---

## Section 2 — Component tool surface

~43 tools across 6 domains. Tags: 🔴 **v1.0 must-ship**, 🟡 **v1.0 if-time / else v1.1**, 🟢 **v1.x explicit**.

### Domain 1 — AIOStreams config CRUD (21 tools)

**Reads (8):**
- 🔴 `aiostreams_get_config()` — full UserData (secrets redacted by default)
- 🔴 `aiostreams_get_services()`, `aiostreams_get_addons()`, `aiostreams_get_filters()`, `aiostreams_get_sort_order()`
- 🟡 `aiostreams_get_template_list()`, `aiostreams_get_active_template()`, `aiostreams_get_statistics()`

**Writes (11) — staged via `_modify()` helper, committed by `aiostreams_save()`:**
- 🔴 `aiostreams_set_preferred_languages(langs)`, `aiostreams_set_cached_only(bool)`, `aiostreams_set_resolution_floor(min)`, `aiostreams_set_core_engine(engine)`
- 🔴 `aiostreams_add_addon(url, position)`, `aiostreams_remove_addon(name)`, `aiostreams_toggle_addon(name, enabled)`
- 🔴 `aiostreams_set_filter(type, value)`, `aiostreams_set_sort_order(order)`, `aiostreams_set_misc_toggle(toggle, value)`
- 🟡 `aiostreams_apply_template(name, mode)` — DESTRUCTIVE, requires confirmation

**Commit + read-out (2):**
- 🔴 `aiostreams_save()` — flushes staged writes via PUT `/api/v1/user`
- 🔴 `aiostreams_get_install_url()` — produces Stremio install URL

**Pattern:** AIOStreams PUT is full-replace, not PATCH. `_modify(transform_fn)` fetches current, applies transform, stages in memory. `save()` is the only thing that mutates remote state.

### Domain 2 — Torrentio URL config (5 tools, all 🔴)

- `torrentio_parse_url(url)` — decode pipe-delimited config
- `torrentio_build_url(config)` — build install URL
- `torrentio_validate_config(config)` — validate against filter.js enums
- `torrentio_list_providers()`, `torrentio_list_quality_filters()`

### Domain 3 — Real-Debrid (7 tools)

- 🔴 `realdebrid_get_user_info()`, `realdebrid_check_cache(hashes)`, `realdebrid_filter_gate_check(filename)`, `realdebrid_add_torrent(magnet)`, `realdebrid_get_torrent_status(id)`, `realdebrid_unrestrict_link(url)`
- 🟡 `realdebrid_get_library()`

### Domain 4 — Stremio addon protocol (6 tools)

- 🔴 `stremio_query_addon(url, type, imdb_id, season, episode)`, `stremio_query_addons_parallel(urls, ...)`, `stremio_dedupe_streams(streams)`, `stremio_get_manifest(url)`
- 🟡 `stremio_filter_streams(streams, **criteria)`, `stremio_rank_streams(streams, sort_strategy)`

### Domain 5 — `find_best_stream` composer (1 tool, 🔴 TOP)

```python
find_best_stream(
    title: str,
    type: Literal["movie", "series"],
    season: int | None = None,
    episode: int | None = None,
    preferred_languages: list[str] = ["English"],
    exclude_quality: list[str] = ["CAM", "TS", "SCR", "R5", "R6"],
    require_cached: bool = True,
    fallback_to_uncached: bool = False,
) -> StreamResolution
```

`StreamResolution` is either a playable URL + metadata, or a structured failure report.

### Domain 6 — Diagnostics (3 tools)

- 🟡 `diagnose_stack_health()`, `diagnose_rd_health()`
- 🟢 `diagnose_dud_rate(window)` — v1.x (needs persistent telemetry)

### Cross-cutting

1. **Naming:** `domain_verb_noun`. Prefix-grouping helps Claude's tool selection.
2. **All async:** every HTTP-touching tool is `async def`. Shared httpx AsyncClient per domain.
3. **Schema validation:** FastMCP auto-generates tool schemas from type hints; outputs are Pydantic models.
4. **Docstrings are load-bearing.** Claude reads them to choose tools. Include constraint hints and examples.
5. **Staged-write commit pattern.** AIOStreams writes are staged; `aiostreams_save()` is the only mutating call to remote state.
6. **Secret redaction.** Read-tools default to redacting RD tokens, AIOStreams passwords. Override via `include_secrets=True`; logged when used.
7. **Tool annotations are mandatory** (Anthropic Directory review requirement). Every tool must declare:
    - `title` — human-readable name (e.g., "Set AIOStreams Preferred Languages")
    - `readOnlyHint: true` for read-only tools (all `*_get_*`, `*_list_*`, `*_check_*`, `*_validate_*`, `realdebrid_get_user_info`, `stremio_query_addon`, `stremio_get_manifest`, `torrentio_parse_url`)
    - `destructiveHint: true` for tools that modify or delete state (all `aiostreams_set_*`, `aiostreams_add_*`, `aiostreams_remove_*`, `aiostreams_toggle_*`, `aiostreams_save`, `aiostreams_apply_template`, `realdebrid_add_torrent`, `find_best_stream` — modifies RD library when unrestricting)
    - Neither hint for pure compute (`stremio_dedupe_streams`, `stremio_filter_streams`, `stremio_rank_streams`, `torrentio_build_url`, `torrentio_validate_config`, `realdebrid_filter_gate_check`) — these are read/transform-only
   FastMCP exposes these via the `@mcp.tool(annotations=ToolAnnotations(...))` decorator. All v1 tools must set them explicitly; CI lint to enforce.

**v1.0 ship target:** 33 🔴 tools + 9 🟡 tools as stretch (1 🟢 explicitly v1.x). ~43 total across all tiers.

**Tool count breakdown by domain:**

| Domain | 🔴 | 🟡 | 🟢 | Total |
|--------|----|----|----|-------|
| 1. AIOStreams | 17 | 4 | 0 | 21 |
| 2. Torrentio | 5 | 0 | 0 | 5 |
| 3. Real-Debrid | 6 | 1 | 0 | 7 |
| 4. Stremio protocol | 4 | 2 | 0 | 6 |
| 5. Compose | 1 | 0 | 0 | 1 |
| 6. Diagnose | 0 | 2 | 1 | 3 |
| **Total** | **33** | **9** | **1** | **43** |

---

## Section 3 — Data flow

Three representative traces.

### Flow A — `find_best_stream`

1. **Cinemeta resolve:** GET `https://v3-cinemeta.strem.io/catalog/series/top/search={title}.json` → pick best by year+popularity → `imdb_id`.
2. **AIOStreams query:** GET `<aiostreams>/stream/series/{imdb_id}:{season}:{episode}.json` → ~20 streams (Tamtaro Standard SEL).
3. **Filter-gate overlay:** for each stream, regex-match filename against `BLOCKED_KEYWORDS ∪ LEARNED_KEYWORDS` → attach `filter_gate_risk` score.
4. **Re-sort:** cached & no-risk > cached & risk > uncached (only if `fallback_to_uncached=True`).
5. **Resolve top candidate:** POST RD `/unrestrict/link` → playable URL.
6. **Retry loop:** on failure (filter-gate strike, 4xx, timeout), pop next candidate. Bounded by `MAESTRO_COMPOSE_BUDGET_S`.
7. **Return:** `StreamResolution(url=..., metadata={...}, source="aiostreams", attempts=[...], elapsed_ms=...)` OR structured failure.

**Invariants:** single AIOStreams call (no parallel fan-out — AIOStreams *is* the aggregator). Filter-gate is post-filter overlay. Retries bounded.

### Flow B — Staged write + commit

```
Claude → aiostreams_set_preferred_languages(["English"])
         ↓ stages: filters.preferred_languages = ["English"]
         (no HTTP)

Claude → aiostreams_set_resolution_floor("720p")
         ↓ stages: filters.excludedResolutions += ["240p","360p"]
         (no HTTP)

Claude → aiostreams_save()
         ↓ PUT <aiostreams>/api/v1/user
           body: full staged UserData
         ↓ clear staged on success
         ↓ return SaveResult(install_url=..., changes_applied=[...])
```

**Invariants:** writes never auto-commit. Reads reflect committed remote state. Batched mutations → single PUT.

### Flow C — `realdebrid_check_cache` with filter-gate overlay

1. GET RD `/torrents/instantAvailability/{h1}/{h2}/{h3}` → `{hash: rd_files_map | {}}`.
2. For each hash with known filename: `filter_gate.predict_risk(filename)` → `low | medium | high | unknown`.
3. Return `list[CacheCheckResult(hash, cached, filter_gate_risk, matched_keywords, rd_files)]`.

**Invariant:** filter-gate is advisory, not filter. Caller decides whether to skip high-risk results.

---

## Section 4 — Error handling

### Core principles

1. **Tools never raise to Claude.** All returns are `OK[T]` or structured `Error[E]`. Stack traces are useless to an agent; structured info enables next-step decisions.
2. **Filter-gate is runtime-learning.** May 2026 RD behavior is post-cache-check filtering — `instantAvailability` says cached but `unrestrict` returns 403/`infringing_file`. The composer promotes these into a runtime `LEARNED_KEYWORDS` set persisted to `~/.config/maestro/filter_gate_state.json`.
3. **Schema drift detected, not crashed-on.** Unknown fields → log+coerce. Missing required → `SchemaError` with regen suggestion.
4. **Backoff is httpx-native** + `tenacity` for composer-level retries. Bounded by env-var budgets.

### Error class shape

```python
class MaestroError(BaseModel):
    code: str                # machine-readable
    message: str             # human/Claude readable
    domain: str              # aiostreams|torrentio|realdebrid|stremio|compose
    suggestion: str | None
    retry_after_s: float | None
    is_transient: bool
```

### Error taxonomy (representative)

| Domain | Trigger | Class | Suggestion |
|--------|---------|-------|------------|
| AIOStreams | 401 | `AuthError` | check `MAESTRO_AIOSTREAMS_PASSWORD` |
| AIOStreams | 400 on PUT | `SchemaError` | run `scripts/regen_aiostreams_schemas.sh` |
| AIOStreams | Pydantic validation on GET | `SchemaError` | same |
| RD | 403 `infringing_file` on `/unrestrict/link` | `FilterGateStrike` | auto-add keywords to learned set; advisory to caller |
| Stremio | `/stream/` timeout | `AddonTimeout` | per-source — don't kill fan-out |
| Compose | all candidates failed | `CompositionFailure(attempts=[...])` | structured per-candidate report |
| Compose | Cinemeta 0 matches | `TitleUnresolved` | pass `imdb_id` directly |

### Filter-gate learning loop

```python
class FilterGateLearner:
    KNOWN_KEYWORDS: set[str] = {"WEB-DL", "WEBRip", "AMZN", "NF", "CR",
                                "YTS", "RARBG", "[eztv]"}
    LEARNED_KEYWORDS: dict[str, LearnEvidence] = {}

    def predict_risk(self, filename: str) -> RiskLevel: ...
    def record_strike(self, filename, rd_error) -> None: ...  # promotes keyword
    def export_state(self) -> dict: ...
    def load_state(self, state: dict) -> None: ...
```

State persisted via `~/.config/maestro/filter_gate_state.json` to survive MCP server restarts.

### Backoff + timeouts

| Layer | Default | Env override |
|-------|---------|--------------|
| Per-HTTP timeout | 15s | `MAESTRO_HTTP_TIMEOUT_S` |
| Domain client retry (5xx) | 3× exponential (1s, 2s, 4s) | `MAESTRO_RETRY_ATTEMPTS` |
| Composer total budget | 60s | `MAESTRO_COMPOSE_BUDGET_S` |
| Composer per-candidate timeout | 10s | `MAESTRO_COMPOSE_CANDIDATE_TIMEOUT_S` |
| Rate-limit `retry_after_s` | honor header, else 30s | n/a |

### Logging

`structlog` → stderr → JSON by default. Every error path emits a structured event with relevant context (hash, filename, suggestion, transient). v1.x adds `diagnose_recent_errors(window)` tool.

---

## Section 5 — Testing strategy

Four-layer model. Coverage target ~80% line on `src/maestro/`.

### Layers

| Suite | Trigger | Time | Live network |
|-------|---------|------|--------------|
| `unit/` | LSP-driven + pre-commit | <2s | No |
| `integration/` | pre-commit + CI on PR | <10s | No (respx) |
| `schema_fidelity/` | CI on PR + nightly | <5s | One GET to GitHub raw |
| `smoke/` | manual dispatch + nightly cron | ~30s | **Yes — secrets in CI** |

### Test organization

```
tests/
├── unit/{aiostreams,torrentio,realdebrid,stremio,compose}/
├── integration/{aiostreams,realdebrid,stremio,compose}/
│   └── fixtures/         # real recorded JSON via scripts/refresh_fixtures.sh
├── smoke/
│   ├── test_live_aiostreams.py
│   ├── test_live_rd.py
│   └── test_live_compose.py
├── schema_fidelity/
│   └── test_aiostreams_schema_pinned.py
└── conftest.py
```

### Fixture refresh

`scripts/refresh_fixtures.sh` — manual workflow run with live credentials, saves real responses to `tests/integration/<domain>/fixtures/`. CI never runs this.

### CI workflows

- **`.github/workflows/ci.yaml`** — push/PR. Steps: ruff check + format check, basedpyright, pytest on 3.12/3.13/3.14 matrix (unit + integration + schema_fidelity).
- **`.github/workflows/smoke.yaml`** — manual dispatch + nightly cron. Requires secrets. Advisory (failures don't block merges; surface upstream regressions).

### Principles

1. **No mocking the AIOStreams client in integration tests** — replay real responses. Catches schema mismatches pure mocks would hide.
2. **Smoke tests are advisory** — they fail when upstream is broken. Status reflects upstream-vs-us.
3. **Schema fidelity is the canary** — when AIOStreams ships `schemas.ts` changes, this test fails and we know to regen.
4. **MCP Inspector integration in v1.x** — drive a test FastMCP server via `mcp-inspector --cli` in CI to catch tool-schema regressions.

### Testing inside Claude (release readiness)

Independent of directory submission (deferred indefinitely for v1), every tool should be exercised end-to-end inside a real Claude client before tagging v1.0. v1 release checklist:

1. **Local install via Claude Code CLI MCP config** (primary dev loop):
   - `~/.claude/mcp/maestro.json` with stdio command + env block
   - Verify each tool surfaces in `/tools` listing
   - Exercise every 🔴 tool via natural-language prompt
2. **Local install via Claude Desktop** (secondary, MCPB-prep for v1.x):
   - `claude_desktop_config.json` with `command` + `env`
   - Verify identical behavior to Claude Code
3. **MCP Inspector full sweep** (`npx @modelcontextprotocol/inspector`):
   - Connect to local stdio server
   - Exercise every tool with mocked + real inputs
   - Capture output for spec/docs
4. **Verify `clientInfo.name: "claude-ai"`** is received on initialize when connected to real Claude (informational diagnostic).

---

## Open questions deferred to v1.x

- **MCPB packaging** (v1.x — invokes `mcp-server-dev:build-mcpb` skill; bundles Python runtime in `.mcpb` (~50-80MB) for Claude Desktop one-click install; project structure already MCPB-compatible)
- **Elicitation for destructive-tool confirmations** (v1.x — currently `apply_template` requires explicit two-call confirmation; v1.x adds elicitation with capability-check + fallback pattern per MCP spec, requires Claude Code ≥2.1.76)
- **CI auto-regen PR-bot** for AIOStreams schemas (v1.x — adds infra complexity)
- **Persistent telemetry** for `diagnose_dud_rate` (v1.x — needs storage layer)
- **MCP Inspector in CI** (v1.x)
- **URL-paste-and-decrypt** AIOStreams password extraction (v1.x — needs reverse engineering)
- **Configurable scoring profiles for the composer** (v1.x — v1 ships single default)
- **Multi-instance support** (v1.x — v1 supports one AIOStreams instance per server process)
- **`diagnose_recent_errors(window)` tool** (v1.x — needs in-memory log buffer)
- **Hybrid search+execute tool pattern** (defer to evidence: ship v1 one-per-action; only refactor to hybrid if real-world context burn proves problematic)
- **Anthropic Directory submission** (deferred indefinitely — Stremio+RD ecosystem is piracy-adjacent and may not pass directory review; PyPI + GitHub distribution covers Clayworks-portfolio reach without review-risk; reassess if landscape shifts)

---

## References

### Upstream repos / docs

- **AIOStreams source:** https://github.com/Viren070/AIOStreams
- **AIOStreams User API docs:** https://docs.aiostreams.viren070.me/apis/user
- **AIOStreams v2.30 migration notes:** https://github.com/Viren070/AIOStreams/blob/main/packages/docs/content/docs/migrations/v2.30.mdx
- **UserDataSchema:** https://github.com/Viren070/AIOStreams/blob/main/packages/core/src/db/schemas.ts
- **Tamtaro SEL templates:** https://github.com/Tam-Taro/SEL-Filtering-and-Sorting
- **Vidhin's regex patterns:** https://github.com/Vidhin05/Releases-Regex
- **Torrentio source:** https://github.com/TheBeastLT/torrentio-scraper
- **Torrentio config parser:** https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/configuration.js
- **Torrentio filter enums:** https://github.com/TheBeastLT/torrentio-scraper/blob/master/addon/lib/filter.js
- **Real-Debrid API:** https://api.real-debrid.com/
- **Stremio addon SDK:** https://github.com/Stremio/stremio-addon-sdk
- **FastMCP docs:** https://gofastmcp.com/

### Filter-gate context

- **ElfHosted RD filtering May 2026 post:** https://store.elfhosted.com/blog/2026/05/12/real-debrid-filtering-may-2026/
- **TorrentFreak RD crackdown:** https://torrentfreak.com/real-debrids-renewed-piracy-crackdown-follows-corporate-restructuring/
- **arnav.au RD-vs-TorBox-vs-AllDebrid:** https://arnav.au/2026/05/20/real-debrid-vs-torbox-vs-alldebrid/

### Internal artifacts

- **Cross-session handoff doc:** `C:\Users\chawo\Documents\task-order-decision-communication\to-stremio-mcp-builder_from-stremio-optimization_aiostreams-handoff_2026-05-21.md`
- **Config feasibility research report:** `C:\Users\chawo\agent\research\maestro-addon-config-feasibility-2026-05-21.md`
- **Engram decision record:** `decision/maestro-clayworks-mcp-scope-pivot-2026-05-21-multi-cc-session`
