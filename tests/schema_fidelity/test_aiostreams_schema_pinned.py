"""Detect upstream AIOStreams schema drift.

This test fetches the live schemas.ts at our pinned tag and compares
its SHA256 against the value we recorded at last regen. Drift = run
scripts/regen_aiostreams_schemas.sh and review the diff before bumping
the pin.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
import pytest

PINNED_TAG = "v2.29.6"
SCHEMA_URL = (
    f"https://raw.githubusercontent.com/Viren070/AIOStreams/"
    f"{PINNED_TAG}/packages/core/src/db/schemas.ts"
)
PINNED_SHA_FILE = Path(__file__).parent / "aiostreams_schema.sha256"


pytestmark = pytest.mark.schema_fidelity


@pytest.mark.skipif(
    os.environ.get("CI") != "true" and not PINNED_SHA_FILE.exists(),
    reason="Pinned SHA file missing - run scripts/regen_aiostreams_schemas.sh and seed the SHA file from the same URL",
)
def test_upstream_schema_matches_pinned_sha() -> None:
    """Live schemas.ts at PINNED_TAG must match the recorded SHA256."""
    response = httpx.get(SCHEMA_URL, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    live_sha = hashlib.sha256(response.content).hexdigest()

    expected_sha = PINNED_SHA_FILE.read_text().strip()
    assert live_sha == expected_sha, (
        f"Upstream schema drift detected at tag {PINNED_TAG}.\n"
        f"  expected SHA: {expected_sha}\n"
        f"  live SHA:     {live_sha}\n"
        f"Run scripts/regen_aiostreams_schemas.sh and review the diff."
    )


def test_pinned_sha_file_exists_in_ci() -> None:
    """The recorded SHA file must be committed for CI to enforce drift detection."""
    if os.environ.get("CI") == "true":
        assert PINNED_SHA_FILE.exists(), (
            "tests/schema_fidelity/aiostreams_schema.sha256 missing in CI. "
            "Seed it by running once locally then commit the file."
        )
