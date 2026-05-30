# Maestro — Developer Notes

Local MCP server, Python (uv-managed). See `README.md` + `docs/specs/2026-05-21-maestro-design.md` for what it does and `docs/plans/2026-05-21-maestro-v1-implementation.md` for build progress.

Project conventions and gotchas a developer (human or AI) needs in scope before touching the code.

## Hard invariants

- **MCP stdio rule**: stdout MUST stay empty (it carries the JSON-RPC frame). All logging goes to **stderr** via structlog. Anything that prints to stdout breaks the protocol — no `print()`, no untyped library calls that emit warnings to stdout.
- **Secrets**: `SecretStr` fields require `.get_secret_value()` for comparison. `SecretStr.__eq__` does NOT compare to plain strings (Pydantic v2 behavior).
- **Schema regen**: `scripts/regen_aiostreams_schemas.sh` is pinned to AIOStreams v2.29.6 (Zod 4). Re-pinning means updating BOTH the script's version constant AND `tests/schema_fidelity/aiostreams_schema.sha256` (LF-terminated, 65 bytes).
- **Generated code**: `src/maestro/aiostreams/schemas_generated.py` is auto-generated and lint-exempt via `pyproject.toml`. Don't hand-edit; re-run the regen script.
- **AIOStreams `presets` is a list, not a dict**: v2.29.6 `UserDataSchema.presets` is `list[Preset3]` (required, `extra="forbid"`) — there is **no** `presets.active`. The active-template marker lives in `appliedTemplates` (`{id, version}`); `get_active_template` filters to known-maestro-template ids so AIOStreams' own `appliedTemplates` entries don't masquerade as active. Don't reintroduce a `presets.active` read/write — it raises on real configs and is rejected on PUT.

## Lint / test gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `N818` fires on Pydantic `*Error` classes | Parent-name heuristic | Per-file-ignore in `pyproject.toml` (comment explains) |
| `N815` fires on `readOnlyHint`/`destructiveHint` | MCP mandates camelCase | Same per-file-ignore pattern |
| `B017`/`PT011` on `pytest.raises(Exception)` | Ruleset bans bare-Exception | Narrow to `pytest.raises(ValidationError)` |
| CI silently passes with 0 tests | Stale `tests/integration` ref in `ci.yaml` (fixed in `0088e4a`) | Don't reintroduce; pytest collection paths must exist |
| Env vars leak between tests | `os.environ.setdefault` is global | Always `monkeypatch.setenv` in tests |
| `ruff format --check` passes locally but CI fails | `ruff check` ≠ `ruff format --check` | Self-review runs BOTH; CI runs BOTH |
| `await mcp.list_tools()` needed | FastMCP 3.3.1 has no `_tool_manager` | Use the async public API |

## Workflow

- **Commit trailers** (soft convention, adopted 2026-05-21): commit bodies MAY include `decision:`, `gotcha:`, `todo:` lines — one each, optional. Useful when summarizing a commit range later (phase-lock notes, changelog, handoff).

  ```
  fix(scope): one-line subject

  Body paragraph explaining the change.

  decision: <one-line architectural call>
  gotcha:   <one-line surprise/quirk>
  todo:     <one-line deferred item>
  ```

  No tooling enforces this. Commits without trailers still work — they just show up as bare subjects in the phase-lock summary.

- **No `print()` for debugging**: violates the stdio invariant. Use structlog's stderr logger.
