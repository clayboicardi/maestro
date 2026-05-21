#!/usr/bin/env bash
# Regenerate src/maestro/aiostreams/schemas_generated.py from upstream Zod.
#
# Pipeline:
#   1. clone Viren070/AIOStreams at pinned tag
#   2. copy db/schemas.ts + utils/constants.ts into an isolated extract
#      workspace, stub utils/env.ts (only two numeric constants are
#      referenced from the Zod schemas)
#   3. run a tsx extractor that imports the Zod schemas and feeds each
#      exported ZodType through Zod 4's built-in `z.toJSONSchema()`
#   4. pipe JSON Schema into datamodel-code-generator -> Pydantic
#
# Bumping: edit PINNED_TAG, run this script, review diff, manually
# update overlay validators in schemas.py if refinement logic changed.
#
# Notes on the design:
#   - Upstream uses Zod v4 (`zod@^4.4.3`). `z.enum(arrayConst)` is a
#     v4-only syntax form; the older `zod-to-json-schema` npm package is
#     Zod-3-only, so we use the v4 built-in `z.toJSONSchema()` instead.
#   - We use `tsx` (esbuild) to execute the .ts extractor directly. This
#     handles type-only erasure and `.js`-extensioned imports of `.ts`
#     files (the NodeNext convention upstream uses).
#   - `utils/env.ts` is stubbed because the full upstream env loader
#     pulls in dotenv, envalid, metadata.json, etc., none of which we
#     need for schema extraction. The Zod schemas only reference
#     `Env.MAX_FORMATTER_TEMPLATE_LENGTH` and `Env.MAX_SEL_LENGTH`.

set -euo pipefail

PINNED_TAG="v2.29.6"
REPO_URL="https://github.com/Viren070/AIOStreams.git"
SCHEMA_PATH="packages/core/src/db/schemas.ts"
CONSTANTS_PATH="packages/core/src/utils/constants.ts"
OUT_PY="src/maestro/aiostreams/schemas_generated.py"
WORK_DIR="$(mktemp -d)"

trap 'rm -rf "$WORK_DIR"' EXIT

echo "[regen] cloning ${REPO_URL}@${PINNED_TAG} into ${WORK_DIR}"
git clone --depth=1 --branch "$PINNED_TAG" "$REPO_URL" "$WORK_DIR/AIOStreams" >/dev/null 2>&1

SOURCE_TS="$WORK_DIR/AIOStreams/$SCHEMA_PATH"
CONSTANTS_TS="$WORK_DIR/AIOStreams/$CONSTANTS_PATH"
if [[ ! -f "$SOURCE_TS" ]]; then
    echo "[regen] FATAL: ${SCHEMA_PATH} not found at tag ${PINNED_TAG}" >&2
    exit 1
fi
if [[ ! -f "$CONSTANTS_TS" ]]; then
    echo "[regen] FATAL: ${CONSTANTS_PATH} not found at tag ${PINNED_TAG}" >&2
    exit 1
fi

echo "[regen] preparing extractor workspace"
EXTRACT="$WORK_DIR/extract"
mkdir -p "$EXTRACT/db" "$EXTRACT/utils"
cp "$SOURCE_TS" "$EXTRACT/db/schemas.ts"
cp "$CONSTANTS_TS" "$EXTRACT/utils/constants.ts"

# Stub utils/env.ts. The Zod schemas in db/schemas.ts only reference two
# numeric Env constants (used as .max() bounds). The real env loader
# defaults are MAX_FORMATTER_TEMPLATE_LENGTH=5000 and MAX_SEL_LENGTH=3000.
cat > "$EXTRACT/utils/env.ts" <<'TS'
// Stub for regen pipeline. Real env loader lives in upstream
// packages/core/src/utils/env.ts and pulls dotenv/envalid/metadata.json;
// none of that is needed to materialize Zod schemas. Only these two
// numeric fields are referenced from db/schemas.ts.
export const Env = {
  MAX_FORMATTER_TEMPLATE_LENGTH: 5000,
  MAX_SEL_LENGTH: 3000,
} as const;
TS

cat > "$EXTRACT/package.json" <<'JSON'
{
  "name": "extract",
  "version": "0.0.0",
  "type": "module",
  "dependencies": {
    "zod": "^4.4.3",
    "tsx": "^4.21.0"
  }
}
JSON

cat > "$EXTRACT/extract.ts" <<'TS'
import { z, type ZodType } from "zod";
import * as mod from "./db/schemas.ts";

const exports: Record<string, unknown> = {};
const skipped: string[] = [];

for (const [name, value] of Object.entries(mod)) {
    // Zod v4 schemas expose `_zod` (private internals) and `parse`. The
    // legacy `_def` marker also survives. Detect either to cover future
    // Zod minor bumps.
    const isZodSchema =
        value !== null &&
        typeof value === "object" &&
        typeof (value as { parse?: unknown }).parse === "function" &&
        ("_zod" in value || "_def" in value);
    if (!isZodSchema) {
        continue;
    }
    try {
        exports[name] = z.toJSONSchema(value as ZodType, {
            // Inline everything; datamodel-code-generator handles refs
            // fine but inlining keeps the output module flat and
            // matches the pinned-tag-diff workflow Clay wants.
            unrepresentable: "any",
        });
    } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        console.error(`skip ${name}: ${msg}`);
        skipped.push(name);
    }
}

// Wrap each exported Zod schema's JSON Schema under a single root
// object with `$defs`, so datamodel-code-generator emits one Pydantic
// class per top-level Zod export.
const root = {
    $schema: "https://json-schema.org/draft/2020-12/schema",
    title: "AIOStreamsSchemas",
    type: "object",
    properties: Object.fromEntries(
        Object.entries(exports).map(([name, schema]) => [
            name,
            { $ref: `#/$defs/${name}` },
        ]),
    ),
    $defs: exports,
};

if (skipped.length > 0) {
    console.error(`[extract] skipped ${skipped.length} export(s): ${skipped.join(", ")}`);
}
console.log(JSON.stringify(root, null, 2));
TS

cd "$EXTRACT"
echo "[regen] installing extractor deps (zod v4 + tsx)"
npm install --silent --no-audit --no-fund

echo "[regen] running Zod -> JSON Schema extractor (tsx)"
npx --no-install tsx extract.ts > "$WORK_DIR/schemas.json" 2> "$WORK_DIR/extract.err" || {
    echo "[regen] FATAL: extraction failed" >&2
    cat "$WORK_DIR/extract.err" >&2
    exit 1
}

# Surface any non-fatal per-export skips to the operator.
if [[ -s "$WORK_DIR/extract.err" ]]; then
    echo "[regen] extractor stderr (non-fatal skips):"
    cat "$WORK_DIR/extract.err"
fi

cd - >/dev/null

echo "[regen] generating Pydantic models via datamodel-code-generator"
# Use ruff formatters (instead of the default black+isort) so the
# generated file matches Maestro's `ruff format` style and passes the
# `ruff format --check .` gate in CI without a follow-up reformat pass.
uv run --with "datamodel-code-generator[ruff]" datamodel-codegen \
    --input "$WORK_DIR/schemas.json" \
    --input-file-type jsonschema \
    --output "$OUT_PY" \
    --output-model-type pydantic_v2.BaseModel \
    --target-python-version 3.12 \
    --use-standard-collections \
    --use-union-operator \
    --field-constraints \
    --reuse-model \
    --use-schema-description \
    --capitalise-enum-members \
    --collapse-root-models \
    --formatters ruff-check ruff-format \
    --custom-file-header "# AUTO-GENERATED from Viren070/AIOStreams@${PINNED_TAG}.
# DO NOT EDIT BY HAND - overwritten by scripts/regen_aiostreams_schemas.sh.
# Hand-overlay validators (runtime refinements that don't survive Zod->JSON-Schema
# round-trip) live in schemas.py."

echo "[regen] done. Wrote ${OUT_PY}"
echo "[regen] PINNED_TAG=${PINNED_TAG}"
