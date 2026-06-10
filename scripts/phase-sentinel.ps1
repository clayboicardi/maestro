#!/usr/bin/env pwsh
# phase-sentinel.ps1
# Maestro Phase Sentinel — wraps a phase's completion in a falsifiable /goal predicate
# and dispatches headless `claude -p` to drive the phase to done.
#
# Pattern: invoke as `./phase-sentinel.ps1 -Phase 1` (or 2/3/.../9).
# The phase definitions live in this file's $PhaseGoals hashtable below.
#
# Each goal MUST be falsifiable per the Quantitative Falsification trait:
# (a) deterministic check command(s); (b) explicit pass criteria; (c) artifact path(s).
#
# On completion: writes handoff-phaseN+1-from-phaseN_<ts>.md to
# ~/Documents/task-order-decision-communication/ with auto_spawn: true metadata,
# so cc-comms-spawn-handler picks up the next phase.
#
# Telemetry: each phase's full /goal transcript is saved to
# ~/Projects/maestro/docs/phase-runs/phase-N_<utc-iso>.log.
#
# Created 2026-05-21 from /octo:define top-5 ship.

param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 9)]
    [int]$Phase,

    [switch]$DryRun = $false,
    [switch]$NoHandoff = $false
)

$ErrorActionPreference = 'Stop'
$repo_root = (Resolve-Path "$PSScriptRoot/..").Path
$plan_doc  = Join-Path $repo_root 'docs/plans/maestro-master-plan.md'
$comms_dir = "$HOME/Documents/task-order-decision-communication"
$log_dir   = Join-Path $repo_root 'docs/phase-runs'

if (-not (Test-Path $log_dir)) { New-Item -ItemType Directory -Path $log_dir | Out-Null }

# ──────────────────────────────────────────────────────────────────────
# Phase goal definitions. Each MUST be falsifiable.
# Edit these per Maestro's master plan. Templates given; sharpen per phase.
# ──────────────────────────────────────────────────────────────────────
$PhaseGoals = @{
    # NOTE 2026-05-21: Phases 0/1/2 LOCKED by parallel CC session before this template existed.
    # Phase 0 ended at 2e24654 (uv init, LICENSE/CHANGELOG/README, CI workflow).
    # Phase 1 ended at 62c23ae (logging, config, errors, annotations, server entry, smoke).
    # Phase 2 ended at 0088e4a (AIOStreams Zod->Pydantic schema generation pipeline).
    # See handoff doc: ~/Documents/task-order-decision-communication/handoff-maestro-phase3-resume_2026-05-21.md
    # Do NOT re-run Phase 1 or Phase 2 via this template — they are shipped. Start at Phase 3.

    3 = @{
        Summary  = 'Phase 3 — AIOStreams domain (HTTP client + staged writes + 21 MCP tools)'
        Goal     = @"
Phase 3 complete iff ALL of the following are true:
  (a) src/maestro/aiostreams/client.py implements HTTP client per Phase 3 spec (auth, retries, schema validation against schemas_generated.py)
  (b) src/maestro/aiostreams/staged.py implements the staged-write helper (load -> mutate -> diff-preview -> commit gate)
  (c) src/maestro/aiostreams/tools.py exposes all 21 MCP tools per the 3.1-3.9 task breakdown in the handoff doc
  (d) tools registered with the FastMCP server in src/maestro/server.py (verified by `maestro-mcp` boot + tool-list query)
  (e) `uv run pytest tests/unit/aiostreams -v` passes (existing 29-test baseline + new Phase 3 coverage)
  (f) `uv run ruff check .` clean, `uv run ruff format --check .` clean, `uv run basedpyright` 0/0/0
  (g) `git status --porcelain` empty; `git log origin/main..HEAD --oneline` shows commits attributable to Phase 3 tasks 3.1-3.9
  (h) docs/plans/maestro-master-plan.md Phase 3 status flipped from 'planned' to 'shipped'
Stop only when ALL (a)-(h) pass; do not declare done if any check fails.
Reference: handoff-maestro-phase3-resume_2026-05-21.md in cc-comms folder.
"@
    }
    # 4..9 templates: copy pattern above. Sharpen per spec when each phase enters scope.
}

if (-not $PhaseGoals.ContainsKey($Phase)) {
    Write-Error "Phase $Phase has no goal definition. Add to `$PhaseGoals` hashtable in this script before invoking."
    exit 2
}

$phase_def = $PhaseGoals[$Phase]
$ts_utc    = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH-mm-ssZ')
$log_path  = Join-Path $log_dir "phase-$Phase`_$ts_utc.log"

Write-Host "── Maestro Phase Sentinel ──" -ForegroundColor Cyan
Write-Host "Phase:    $Phase ($($phase_def.Summary))"
Write-Host "Log:      $log_path"
Write-Host "Dry run:  $DryRun"
Write-Host ""
Write-Host "Goal:" -ForegroundColor Yellow
Write-Host $phase_def.Goal
Write-Host ""

if ($DryRun) {
    Write-Host "[DryRun] Would dispatch:" -ForegroundColor DarkYellow
    Write-Host "  claude -p --goal `"<phase goal>`" --cwd $repo_root"
    exit 0
}

# Dispatch. `claude -p` runs headless with --goal driving multi-turn until complete.
# We capture full transcript to the phase log for retroactive analysis.
Push-Location $repo_root
try {
    $goal_text = $phase_def.Goal
    # Note: --goal flag landed v2.1.139. If your installed CC predates that, the
    # invocation falls back gracefully but loses the persistent-condition behavior.
    claude -p $goal_text --output-format stream-json 2>&1 | Tee-Object -FilePath $log_path
    $exit_code = $LASTEXITCODE
} finally {
    Pop-Location
}

Write-Host ""
if ($exit_code -ne 0) {
    Write-Host "── Phase $Phase EXITED with code $exit_code ──" -ForegroundColor Red
    Write-Host "Inspect log: $log_path"
    exit $exit_code
}

Write-Host "── Phase $Phase reported completion ──" -ForegroundColor Green
Write-Host "Verify the falsifiable criteria yourself before trusting completion claim."
Write-Host "Log: $log_path"

# Handoff: drop a cc-comms file so the next phase can auto-spawn (per CLAUDE.md cc-comms convention).
if ($NoHandoff -or $Phase -ge 9) {
    Write-Host "(handoff skipped: NoHandoff=$NoHandoff or final phase reached)"
    exit 0
}

$next_phase = $Phase + 1
if (-not (Test-Path $comms_dir)) { New-Item -ItemType Directory -Path $comms_dir | Out-Null }
$handoff_file = Join-Path $comms_dir "handoff-phase$next_phase-from-phase$Phase`_$ts_utc.md"

$handoff_body = @"
<!-- cc-comms-meta
auto_spawn: false
cwd: $repo_root
launch_mode: interactive
wait_seconds: 120
-->
# Maestro Phase $next_phase handoff (from Phase $Phase)

Phase $Phase reported completion at $ts_utc.
Run log: $log_path

---

Read $repo_root/docs/plans/maestro-master-plan.md Phase $next_phase section.
Then invoke this Phase Sentinel for Phase $next_phase:

    pwsh -NoProfile -File $repo_root/scripts/phase-sentinel.ps1 -Phase $next_phase

NOTE: auto_spawn is set to false by default. Flip to true in the metadata block above
ONLY after a human verifies Phase $Phase actually shipped (do not trust completion-claim alone).
"@

Set-Content -Path $handoff_file -Value $handoff_body -Encoding UTF8
Write-Host "Handoff written: $handoff_file"
Write-Host "  (auto_spawn: false by default — flip after verifying Phase $Phase actually shipped)"
