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

Coverage boundary (the material one): this test walks only TOP-LEVEL
`UserDataSchema.model_fields`. It does NOT recurse, so it gives zero guard
over the NESTED credential containers the redactor actually hand-codes --
`services[].credentials` (debrid API keys), `proxy.credentials`, and
`parentConfig.password`. If upstream renames a nested credential key, the
redactor silently no-ops AND this test stays green. (The suffix regex is a
secondary, top-level-only limit; widening it does NOT close the structural
nesting gap.) A recursive nested-credential walker -- plus the
`parentConfig.password` redaction fix it would expose -- is tracked as a
dedicated follow-up.

If this test fails after a schema regen, extend the tuple in
`src/maestro/aiostreams/tools.py`.
"""

from __future__ import annotations

import re

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
