#!/usr/bin/env bash
# Refresh integration-test fixtures from live upstream.
#
# Requires the same env vars as the smoke workflow. Saves real responses
# to tests/integration/<domain>/fixtures/.
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
        curl -sS \
            -u "${MAESTRO_AIOSTREAMS_UUID}:${MAESTRO_AIOSTREAMS_PASSWORD}" \
            "${MAESTRO_AIOSTREAMS_BASE_URL%/}/api/v1/user/${MAESTRO_AIOSTREAMS_UUID}" \
            | python -m json.tool > "${FIXTURE_DIR}/get_config_response.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/get_config_response.json"
        ;;
    realdebrid)
        if [[ -z "${MAESTRO_RD_TOKEN:-}" ]]; then
            echo "MAESTRO_RD_TOKEN not set" >&2
            exit 1
        fi
        echo "[refresh] fetching RD user info"
        curl -sS \
            -H "Authorization: Bearer ${MAESTRO_RD_TOKEN}" \
            "https://api.real-debrid.com/rest/1.0/user" \
            | python -m json.tool > "${FIXTURE_DIR}/get_user_response.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/get_user_response.json"
        ;;
    stremio)
        echo "[refresh] fetching Cinemeta sample (no auth needed)"
        curl -sSL \
            "https://v3-cinemeta.strem.io/catalog/series/top/search=Severance.json" \
            | python -m json.tool > "${FIXTURE_DIR}/cinemeta_search_severance.json"
        echo "[refresh] wrote ${FIXTURE_DIR}/cinemeta_search_severance.json"
        ;;
    *)
        echo "unknown domain: $DOMAIN" >&2
        exit 1
        ;;
esac

echo "[refresh] done."
