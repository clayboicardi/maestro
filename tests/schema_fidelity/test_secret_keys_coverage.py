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

Coverage boundary: the regex matches only the listed suffixes (api_key /
access_token / password / secret / token). A future credential field named
outside that set -- e.g. `*Bearer`, `*Credential`, or a bare `auth` -- would
NOT be flagged and could ship unredacted. Widen `_SENSITIVE_SUFFIX_RE` if
upstream introduces such a naming.

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
