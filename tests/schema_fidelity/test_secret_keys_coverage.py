"""Schema-fidelity guard: `_TOP_LEVEL_SECRET_KEYS` must cover every sensitive
UserDataSchema top-level field.

An earlier security review flagged that the `_TOP_LEVEL_SECRET_KEYS` tuple
in `src/maestro/aiostreams/tools.py` is a manually-maintained list. If
AIOStreams upstream adds a new credential-bearing top-level field (e.g.
`sonarrApiKey`, `traktApiKey`, `<new_provider>AccessToken`) on the next
regen, the field will ship unredacted through every MCP read path until
someone manually extends the tuple. This test closes that drift gap by
walking `UserDataSchema.model_fields` and asserting every field name
matching a conservative sensitive-suffix regex is present in the tuple.

This module guards secret coverage at two levels:

1. `test_top_level_secret_keys_covers_schema_sensitive_fields` -- every
   TOP-LEVEL UserDataSchema field with a sensitive-suffix name must appear in
   `_TOP_LEVEL_SECRET_KEYS`.
2. `test_no_unhandled_nested_sensitive_fields` -- every NESTED sensitive-suffix
   field (any depth) must be a known redactor-handled path. As of v2.29.6,
   `parentConfig.password` is the only one, and `_redact_secrets` now redacts it.

Known limit: neither walk sees DYNAMIC dict keys (e.g. `presets[].options`,
typed `dict[str, Any]`). Those are owned by `_redact_secrets` directly via
`_SENSITIVE_OPTION_KEY_RE` key-matching. The credential CONTAINERS
(`services[].credentials`, `proxy.credentials`) are named "credentials" -- not a
sensitive suffix -- and are likewise handled by the redactor by container name.

If this test fails after a schema regen, extend the tuple in
`src/maestro/aiostreams/tools.py`.
"""

from __future__ import annotations

import re
import typing
from collections.abc import Iterator

from pydantic import BaseModel

from maestro.aiostreams import schemas_generated
from maestro.aiostreams.tools import _TOP_LEVEL_SECRET_KEYS

# Conservative suffix regex. Matches camelCase field names ending in any of:
# - apikey / api_key
# - accesstoken / access_token
# - password
# - secret
# - token
# Case-insensitive; matches only at end-of-name to avoid false positives on
# fields like `tokenizer`, `keyword`, `passwordless`.
_SENSITIVE_SUFFIX_RE = re.compile(r"(?i)(api_?key|access_?token|password|secret|token)$")


def test_top_level_secret_keys_covers_schema_sensitive_fields() -> None:
    user_data = schemas_generated.UserDataSchema
    missing = {
        name
        for name in user_data.model_fields
        if _SENSITIVE_SUFFIX_RE.search(name) and name not in _TOP_LEVEL_SECRET_KEYS
    }
    assert not missing, (
        f"UserDataSchema has sensitive top-level fields not covered by "
        f"_TOP_LEVEL_SECRET_KEYS: {sorted(missing)}. Extend the tuple in "
        f"src/maestro/aiostreams/tools.py to redact these through MCP "
        f"read paths."
    )


# Nested sensitive fields that _redact_secrets (src/maestro/aiostreams/tools.py)
# is KNOWN to handle. As of upstream v2.29.6, parentConfig.password is the only
# nested *scalar* sensitive field; the credential CONTAINERS
# (services[].credentials, proxy.credentials) are named "credentials" -- not a
# sensitive suffix -- and the redactor handles them by container name.
_KNOWN_NESTED_SENSITIVE_PATHS = {"parentConfig.password"}


def _iter_nested_models(annotation: object) -> Iterator[type[BaseModel]]:
    """Yield BaseModel subclasses reachable from a field annotation, unwrapping
    Optional/Union/list/dict via typing.get_args."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    for arg in typing.get_args(annotation):
        yield from _iter_nested_models(arg)


def _nested_sensitive_field_paths(
    model: type[BaseModel], prefix: str = "", seen: set[type] | None = None
) -> list[str]:
    """Dotted paths of every field whose NAME matches the sensitive regex, at any depth."""
    seen = seen if seen is not None else set()
    if model in seen:
        return []
    seen = (
        seen | {model}
    )  # per-ancestral-path (not shared across siblings) -- blocks cycles without skipping sibling branches
    paths: list[str] = []
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        if _SENSITIVE_SUFFIX_RE.search(name):
            paths.append(path)
        for sub in _iter_nested_models(field.annotation):
            paths.extend(_nested_sensitive_field_paths(sub, f"{path}.", seen))
    return paths


def test_no_unhandled_nested_sensitive_fields() -> None:
    """Drift guard for NESTED secrets (complements the top-level test above).

    Any field named with a sensitive suffix below the top level must be a known
    redactor-handled path. A new upstream nested secret (e.g. ``fooConfig.apiToken``)
    fails here until ``_redact_secrets`` AND ``_KNOWN_NESTED_SENSITIVE_PATHS`` are
    updated -- closing the exact gap that let ``parentConfig.password`` leak.
    """
    nested = {
        p for p in _nested_sensitive_field_paths(schemas_generated.UserDataSchema) if "." in p
    }
    unhandled = nested - _KNOWN_NESTED_SENSITIVE_PATHS
    assert not unhandled, (
        f"Unhandled nested sensitive fields in UserDataSchema: {sorted(unhandled)}. "
        f"Add redaction in _redact_secrets (src/maestro/aiostreams/tools.py) and extend "
        f"_KNOWN_NESTED_SENSITIVE_PATHS."
    )
