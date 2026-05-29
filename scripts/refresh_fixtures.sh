#!/usr/bin/env bash
# Refresh integration-test fixtures from live upstream.
#
# Requires the same env vars as the smoke workflow. Saves real responses to
# tests/integration/<domain>/fixtures/.
#
# Safety:
#   - All fetches use `curl --fail-with-body` + an atomic temp->mv write, so an
#     HTTP 4xx/5xx (e.g. expired auth) can't overwrite a good fixture with an
#     error body (a plain `curl -sS` exits 0 on a 404, defeating `set -e`).
#   - The AIOStreams config response is piped through maestro's `_redact_secrets`
#     before writing, so a refreshed fixture never carries live credentials
#     (parentConfig.password, services/proxy creds, top-level keys, preset
#     options) into git.
#
# Usage:
#   MAESTRO_RD_TOKEN=... MAESTRO_AIOSTREAMS_UUID=... \
#   MAESTRO_AIOSTREAMS_PASSWORD=... ./scripts/refresh_fixtures.sh <domain>
#
# Where <domain> is one of: aiostreams, realdebrid, stremio

set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
    echo "usage: $0 <domain>"
    echo "  domain ∈ {aiostreams, realdebrid, stremio}"
    exit 1
fi

FIXTURE_DIR="tests/integration/${DOMAIN}/fixtures"
mkdir -p "$FIXTURE_DIR"

case "$DOMAIN" in
    aiostreams)
        if [[ -z "${MAESTRO_AIOSTREAMS_BASE_URL:-}" ]]; then
            echo "MAESTRO_AIOSTREAMS_BASE_URL not set" >&2
            exit 1
        fi
        echo "[refresh] fetching AIOStreams config via GET /api/v1/user"
        raw="$(mktemp)"
        out="$(mktemp)"
        curl --fail-with-body -sSL \
            -u "${MAESTRO_AIOSTREAMS_UUID}:${MAESTRO_AIOSTREAMS_PASSWORD}" \
            "${MAESTRO_AIOSTREAMS_BASE_URL%/}/api/v1/user/${MAESTRO_AIOSTREAMS_UUID}" \
            > "$raw"
        # Redact before the fixture can be committed -- the live config returns
        # the same secret classes _redact_secrets guards on read paths.
        uv run python - "$raw" "$out" <<'PY'
import json
import sys

from maestro.aiostreams.tools import _redact_secrets

with open(sys.argv[1]) as f:
    data = json.load(f)
with open(sys.argv[2], "w") as f:
    json.dump(_redact_secrets(data), f, indent=2)
PY
        mv "$out" "${FIXTURE_DIR}/get_config_response.json"
        rm -f "$raw"
        echo "[refresh] wrote (redacted) ${FIXTURE_DIR}/get_config_response.json"
        ;;
    realdebrid)
        if [[ -z "${MAESTRO_RD_TOKEN:-}" ]]; then
            echo "MAESTRO_RD_TOKEN not set" >&2
            exit 1
        fi
        echo "[refresh] fetching RD user info"
        raw="$(mktemp)"
        out="$(mktemp)"
        curl --fail-with-body -sSL \
            -H "Authorization: Bearer ${MAESTRO_RD_TOKEN}" \
            "https://api.real-debrid.com/rest/1.0/user" \
            > "$raw"
        python -m json.tool "$raw" "$out"
        mv "$out" "${FIXTURE_DIR}/get_user_response.json"
        rm -f "$raw"
        echo "[refresh] wrote ${FIXTURE_DIR}/get_user_response.json"
        ;;
    stremio)
        echo "[refresh] fetching Cinemeta sample (no auth needed)"
        raw="$(mktemp)"
        out="$(mktemp)"
        curl --fail-with-body -sSL \
            "https://v3-cinemeta.strem.io/catalog/series/top/search=Severance.json" \
            > "$raw"
        python -m json.tool "$raw" "$out"
        mv "$out" "${FIXTURE_DIR}/cinemeta_search_severance.json"
        rm -f "$raw"
        echo "[refresh] wrote ${FIXTURE_DIR}/cinemeta_search_severance.json"
        ;;
    *)
        echo "unknown domain: $DOMAIN" >&2
        exit 1
        ;;
esac

echo "[refresh] done."
