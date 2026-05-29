"""Pin the generated Pydantic module's content (codegen-OUTPUT integrity).

Complements ``test_aiostreams_schema_pinned.py``: that hashes the upstream
INPUT (``schemas.ts``) at the pinned tag; this hashes the committed OUTPUT
(``schemas_generated.py``). The output depends on BOTH upstream inputs
(``db/schemas.ts`` AND ``utils/constants.ts``) plus the codegen toolchain, so:

- a drift in ``constants.ts`` -- which the input-hash does NOT cover -- trips
  this pin (closes the "integrity test pins only schemas.ts" gap), and
- a toolchain change that alters codegen output trips it too (partial defense
  for the unpinned build chain), and
- an accidental hand-edit of the generated module trips it.

Line endings are normalized to LF before hashing so the pin is stable across
a Windows (CRLF) working tree and Linux CI (LF). On a legitimate re-pin
(``scripts/regen_aiostreams_schemas.sh``), re-seed ``schemas_generated.sha256``
from the regenerated file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

GENERATED = (
    Path(__file__).resolve().parents[2] / "src" / "maestro" / "aiostreams" / "schemas_generated.py"
)
PINNED_SHA_FILE = Path(__file__).parent / "schemas_generated.sha256"

pytestmark = pytest.mark.schema_fidelity


def test_generated_module_matches_pinned_sha() -> None:
    """The committed ``schemas_generated.py`` (LF-normalized) must match its pin.

    A mismatch means one of: an upstream input changed (``schemas.ts`` OR
    ``constants.ts``), the codegen toolchain produced different output, or the
    file was hand-edited. Re-run ``scripts/regen_aiostreams_schemas.sh``,
    review the diff, and re-seed ``schemas_generated.sha256``.
    """
    content = GENERATED.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(content).hexdigest()
    expected = PINNED_SHA_FILE.read_text(encoding="utf-8").strip()
    assert actual == expected, (
        f"schemas_generated.py drift.\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        f"Re-run scripts/regen_aiostreams_schemas.sh, review the diff, and re-seed "
        f"{PINNED_SHA_FILE.name}."
    )
