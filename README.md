# Maestro by Clayworks

> MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks.

**Status:** v0.2.0 — released. All 9 implementation phases locked; a post-v0.1.0 review campaign + polish pass added 2 discovery tools and hardened security/CI (see [CHANGELOG.md](CHANGELOG.md)). Design spec: [docs/specs/2026-05-21-maestro-design.md](docs/specs/2026-05-21-maestro-design.md).

## What it does

Maestro is a local Python MCP server that lets an AI agent (Claude Code, Cursor, Claude Desktop) read, audit, and write configurations across a user's existing Stremio addons — primarily AIOStreams (Tamtaro SEL Setup) and Torrentio — and chain those primitives into a `find_best_stream` composer that resolves a single playable Real-Debrid URL per title query.

## Progress

| Phase | Scope | Status |
|---|---|---|
| 0 | Project foundation (uv, LICENSE, CI) | Locked 2026-05-21 |
| 1 | Core scaffolding (logging, config, errors, server) | Locked 2026-05-21 |
| 2 | AIOStreams schema generation pipeline | Locked 2026-05-21 |
| 3 | AIOStreams domain (async client + 21 MCP tools) | Locked 2026-05-21 |
| 4 | Torrentio domain (URL encoder + 5 MCP tools) | Locked 2026-05-21 |
| 5 | Real-Debrid domain (async client + filter-gate learner + 7 MCP tools) | Locked 2026-05-22 |
| 6 | Stremio addon protocol domain (generic client + 6 MCP tools) | Locked 2026-05-22 |
| 7 | `find_best_stream` composer (the killer feature) | Locked 2026-05-22 |
| 8 | Diagnostics (3 health-probe tools) | Locked 2026-05-22 |
| 9 | Release readiness (smoke workflow + refresh script + CF7) | Locked 2026-05-22 |

Tool surface: 45 MCP tools (21 AIOStreams + 7 Torrentio + 7 Real-Debrid + 6 Stremio + 1 `find_best_stream` + 3 Diagnose). Test suite: 252 unit + integration tests passing + 1 opt-in smoke test. Coverage: ~93%.

## Install

Local install via uv:

```bash
git clone https://github.com/clayboicardi/maestro
cd maestro
uv tool install .
maestro-mcp --help
```

Not yet on PyPI — install from source (above). Publish is deferred (no auto-publish on tag).

## Configure

Maestro reads its configuration from environment variables. Set them in your MCP client's config file.

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

Claude Desktop's `claude_desktop_config.json` uses the same shape.

## Development

```bash
uv sync
uv run pytest                              # 181 unit + integration + schema_fidelity
uv run ruff check && uv run basedpyright   # lint + type check
```

Live-upstream smoke tests are opt-in:

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
