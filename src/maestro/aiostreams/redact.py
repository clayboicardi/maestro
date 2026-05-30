"""CLI: redact an AIOStreams config JSON file to another file.

Usage::

    python -m maestro.aiostreams.redact <in.json> <out.json>

Reads the JSON at ``<in.json>``, runs it through :func:`redact_config`, and writes
the redacted result to ``<out.json>`` (``indent=2``). Used by
``scripts/refresh_fixtures.sh`` so the fixture-refresh path depends on a stable
public entry point rather than importing the private ``_redact_secrets`` through
an inline heredoc.

Diagnostics go to stderr; nothing is written to stdout (output is the file).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from maestro.aiostreams.tools import redact_config

_EXPECTED_ARGC = 2


def main(argv: list[str] | None = None) -> int:
    """Redact ``argv[0]`` -> ``argv[1]``. Returns 0 on success, 2 on usage error."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != _EXPECTED_ARGC:
        print(
            "usage: python -m maestro.aiostreams.redact <in.json> <out.json>",
            file=sys.stderr,
        )
        return 2
    in_path, out_path = args
    data = json.loads(Path(in_path).read_text(encoding="utf-8"))
    Path(out_path).write_text(json.dumps(redact_config(data), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
