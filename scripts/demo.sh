#!/usr/bin/env bash
#
# Splunk App Lifecycle Copilot — one-command demo.
#
# Runs the self-heal loops end-to-end and prints where every artifact landed.
#
#   ./scripts/demo.sh             # AppInspect loop, plus the live onboarding
#                                 #   loop when .env is configured
#   ./scripts/demo.sh appinspect  # only the AppInspect loop (no external deps)
#   ./scripts/demo.sh onboarding  # only the live onboarding loop (Splunk + MCP)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
COPILOT="$ROOT/.venv/bin/copilot"
MODE="${1:-all}"
APPINSPECT_OUT=""
ONBOARDING_OUT=""

bold() { printf '\n\033[1m%s\033[0m\n' "$1"; }
info() { printf '  %s\n' "$1"; }

# --- preflight -----------------------------------------------------------
if [[ ! -x "$COPILOT" ]]; then
  bold "The copilot CLI is not installed in .venv."
  info "Run 'make setup' first (creates the Python 3.13 venv and installs the package)."
  exit 1
fi

# copilot loads .env itself; we only inspect it to decide whether the live
# onboarding path is wired up, without sourcing arbitrary shell.
env_has() { [[ -f "$ROOT/.env" ]] && grep -Eq "^${1}=.+" "$ROOT/.env"; }
onboarding_configured() {
  env_has SPLUNK_HEC_TOKEN && env_has SPLUNK_MCP_ENDPOINT && env_has SPLUNK_MCP_ENCRYPTED_TOKEN
}

wait_for_splunk() {
  bold "Starting Splunk (docker compose up -d)..."
  docker compose up -d >/dev/null
  bold "Waiting for the splunk-copilot container to report healthy..."
  for _ in $(seq 1 60); do
    local status
    status="$(docker inspect -f '{{.State.Health.Status}}' splunk-copilot 2>/dev/null || echo unknown)"
    if [[ "$status" == "healthy" ]]; then
      info "Splunk is healthy."
      return 0
    fi
    sleep 5
  done
  bold "Splunk did not become healthy within 5 minutes."
  info "Check 'docker compose logs splunk' and re-run."
  return 1
}

run_appinspect() {
  APPINSPECT_OUT="runs/appinspect-demo-$STAMP"
  bold "Stage 2 - AppInspect self-heal loop -> $APPINSPECT_OUT"
  "$COPILOT" appinspect fixtures/appinspect/broken_app --out "$APPINSPECT_OUT"
}

run_onboarding() {
  ONBOARDING_OUT="runs/onboarding-demo-$STAMP"
  bold "Stage 1 - Onboarding MCP self-heal loop -> $ONBOARDING_OUT"
  "$COPILOT" onboard fixtures/onboarding/sample_upi.log --out "$ONBOARDING_OUT"
}

# --- orchestrate ---------------------------------------------------------
case "$MODE" in
  appinspect)
    run_appinspect
    ;;
  onboarding)
    if ! onboarding_configured; then
      bold "Onboarding needs SPLUNK_HEC_TOKEN, SPLUNK_MCP_ENDPOINT and SPLUNK_MCP_ENCRYPTED_TOKEN in .env."
      exit 1
    fi
    wait_for_splunk
    run_onboarding
    ;;
  all)
    run_appinspect
    if onboarding_configured; then
      if wait_for_splunk; then
        run_onboarding || bold "Onboarding loop failed -- see the output above."
      fi
    else
      bold "Skipping the live onboarding loop."
      info ".env is missing SPLUNK_HEC_TOKEN / SPLUNK_MCP_ENDPOINT / SPLUNK_MCP_ENCRYPTED_TOKEN."
      info "Replay the committed onboarding run in the dashboard instead (no Splunk required):"
      info "  cd ui/dashboard && bun install && bun run dev   # open the Onboarding stage"
    fi
    ;;
  *)
    bold "Unknown mode '$MODE' (use: all | appinspect | onboarding)."
    exit 2
    ;;
esac

# --- where everything landed ---------------------------------------------
bold "Demo complete. Artifacts:"
[[ -n "$APPINSPECT_OUT" ]] && info "AppInspect : $APPINSPECT_OUT  (summary.json, provenance.jsonl, events.json)"
[[ -n "$ONBOARDING_OUT" ]] && info "Onboarding : $ONBOARDING_OUT  (summary.json, provenance.jsonl, events.json)"

bold "Replay any run in the dashboard:"
info "cd ui/dashboard && bun install && bun run dev"
info "Then click 'Load events' and pick a run's events.json -- or explore the committed demo stages."
