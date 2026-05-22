# Maestro by Clayworks

> MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks.

**Status:** Pre-release (v0.1.0). 8 of 10 phases locked. See [docs/specs/2026-05-21-maestro-design.md](docs/specs/2026-05-21-maestro-design.md) for the design spec.

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
| 8 | Diagnostics | Next |
| 9 | Release readiness | Pending |

Tool surface: 40 MCP tools (21 AIOStreams + 5 Torrentio + 7 Real-Debrid + 6 Stremio + 1 `find_best_stream`). Test suite: 172 passing.

## Install

Coming in v1.0.0. See [docs/plans/2026-05-21-maestro-v1-implementation.md](docs/plans/2026-05-21-maestro-v1-implementation.md) for build progress.

## License

MIT — see [LICENSE](LICENSE).
