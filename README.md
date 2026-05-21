# Maestro by Clayworks

> MCP server giving AI agents programmatic control over Stremio + Real-Debrid stacks.

**Status:** Pre-release (v0.1.0). See [docs/specs/2026-05-21-maestro-design.md](docs/specs/2026-05-21-maestro-design.md) for the design spec.

## What it does

Maestro is a local Python MCP server that lets an AI agent (Claude Code, Cursor, Claude Desktop) read, audit, and write configurations across a user's existing Stremio addons — primarily AIOStreams (Tamtaro SEL Setup) and Torrentio — and chain those primitives into a `find_best_stream` composer that resolves a single playable Real-Debrid URL per title query.

## Install

Coming in v1.0.0. See [docs/plans/2026-05-21-maestro-v1-implementation.md](docs/plans/2026-05-21-maestro-v1-implementation.md) for build progress.

## License

MIT — see [LICENSE](LICENSE).
