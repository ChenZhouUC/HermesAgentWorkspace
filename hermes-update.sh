#!/usr/bin/env bash
# ~/.hermes/hermes-update.sh
#
# Comprehensive Hermes update script.
# Runs the full update sequence and shows a final status summary.
#
# Covers:
#   1. git pull + uv pip install (via hermes update)
#   2. Skills Hub sync           (via hermes update)
#   3. Config migration check    (via hermes update, interactive)
#   4. Gateway process restart   (via hermes update, if already running)
#   5. Gateway launchd plist refresh (hermes gateway install --force)
#   6. zsh completion script regeneration
#   7. Health verification (hermes doctor + gateway status)
#
# ⚠  Keep this script in sync with upstream workflow changes:
#    - If hermes update adds/removes steps, review whether step 5–6 are still needed
#    - If gateway install flags change, update step 5
#    - If venv or binary paths move, update step 6
#    Referenced from README.md § 更新
#
# Usage:
#   bash ~/.hermes/hermes-update.sh
#   chmod +x ~/.hermes/hermes-update.sh && ~/.hermes/hermes-update.sh

set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"

# ── Colour helpers (auto-disable outside a TTY) ───────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GRN='\033[0;32m'
    YLW='\033[1;33m'
    BLU='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''
    GRN=''
    YLW=''
    BLU=''
    BOLD=''
    NC=''
fi

step() { printf "\n${BLU}══${NC} %s\n" "$1"; }
ok() { printf "  ${GRN}✓${NC} %s\n" "$1"; }
warn() { printf "  ${YLW}⚠${NC}  %s\n" "$1"; }
fail() { printf "  ${RED}✗${NC} %s\n" "$1"; }
note() { printf "  ${BOLD}→${NC} %s\n" "$1"; }

WARNS=()
ACTS=()
add_warn() { WARNS+=("$1"); }
add_act() { ACTS+=("$1"); }
FINAL_RC=0

# ── 1. Preflight ──────────────────────────────────────────────────────────────
step "Preflight"

if ! command -v hermes &>/dev/null; then
    fail "hermes not found in PATH (expected ~/.local/bin/hermes)"
    printf "  Ensure ~/.local/bin is in PATH, then retry.\n"
    exit 1
fi
ok "hermes: $(command -v hermes)"

if [[ ! -d "${HERMES_AGENT}/.git" ]]; then
    fail "Not a git repository: ${HERMES_AGENT}"
    printf "  Re-install: git clone https://github.com/NousResearch/hermes-agent.git %s\n" "${HERMES_AGENT}"
    exit 1
fi
ok "Repo: ${HERMES_AGENT}"

# Network sanity check (non-fatal)
if ! curl -sf --connect-timeout 5 --max-time 8 https://github.com >/dev/null 2>&1; then
    warn "github.com unreachable — git fetch may stall"
    add_warn "Network: github.com unreachable. Check connectivity if update hangs."
fi

PRE_VERSION=$(hermes --version 2>/dev/null | head -1 || echo "unknown")
note "Current: ${PRE_VERSION}"

# ── 2. hermes update ──────────────────────────────────────────────────────────
# Handles: git pull · uv pip install · skills sync · config migration prompts
#          · gateway process restart (running launchd/systemd instances)
step "Updating Hermes  [git pull · deps · skills · gateway restart]"
echo ""

set +e
hermes update
UPDATE_RC=$?
set -e
echo ""

if [[ $UPDATE_RC -ne 0 ]]; then
    fail "hermes update exited $UPDATE_RC — review output above"
    add_act "Resolve the update errors above, then re-run this script"
    FINAL_RC=1
fi

# ── 3. Refresh gateway launchd service ────────────────────────────────────────
# hermes update restarts a running gateway process but does NOT refresh the
# launchd plist. Force-reinstalling is cheap and idempotent; it ensures the
# plist stays accurate after a version bump (updated env vars, paths, etc.).
step "Refreshing gateway launchd plist"

set +e
hermes gateway install --force
GW_INSTALL_RC=$?
set -e

if [[ $GW_INSTALL_RC -eq 0 ]]; then
    ok "Plist refreshed"
else
    warn "hermes gateway install --force returned $GW_INSTALL_RC"
    add_act "Run manually: hermes gateway install --force"
fi

# ── 4. Ensure gateway is running ──────────────────────────────────────────────
# hermes update already restarts a running gateway; this step only fires if
# the gateway was stopped before the update.
set +e
GW_STATUS_OUT=$(hermes gateway status 2>&1)
set -e

if ! echo "$GW_STATUS_OUT" | grep -qi "running\|active"; then
    note "Gateway not running — starting..."
    set +e
    hermes gateway start 2>&1
    GW_START_RC=$?
    set -e
    if [[ $GW_START_RC -eq 0 ]]; then
        ok "Gateway started"
    else
        warn "hermes gateway start returned $GW_START_RC"
        add_act "Run: hermes gateway start  (diagnose with: hermes logs)"
    fi
fi

# ── 5. Update zsh completions ─────────────────────────────────────────────────
step "Updating zsh completions"

COMP_FILE="${HERMES_HOME}/completions/_hermes"
mkdir -p "${HERMES_HOME}/completions"

set +e
hermes completion zsh >"${COMP_FILE}" 2>/dev/null
COMP_RC=$?
set -e

if [[ $COMP_RC -eq 0 ]]; then
    ok "Written: ${COMP_FILE}"
    rm -f ~/.zcompdump*
    note "zsh completion cache cleared (rebuilds on next shell open)"
else
    warn "Could not generate completions (exit $COMP_RC)"
    add_act "Run: hermes completion zsh > ~/.hermes/completions/_hermes"
fi

# ── 6. Verify ─────────────────────────────────────────────────────────────────
step "Verifying"
echo ""

POST_VERSION=$(hermes --version 2>/dev/null | head -1 || echo "unknown")
if [[ "$PRE_VERSION" != "$POST_VERSION" ]]; then
    ok "Version: ${PRE_VERSION} → ${POST_VERSION}"
else
    ok "Version: ${POST_VERSION}  (no change)"
fi
echo ""

DOCTOR_OUT=$(hermes doctor 2>&1)
echo "$DOCTOR_OUT"
if echo "$DOCTOR_OUT" | grep -qiE '(✗|^\s+error|failed:)'; then
    add_act "hermes doctor reported issues — run: hermes doctor --fix"
fi
echo ""

GW_FINAL=$(hermes gateway status 2>&1)
echo "$GW_FINAL"
if echo "$GW_FINAL" | grep -qi "running\|active"; then
    ok "Gateway is running"
else
    fail "Gateway is not running"
    add_act "Start gateway: hermes gateway start  (diagnose: hermes logs)"
    FINAL_RC=1
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
printf "${BOLD}══════════════════════════════════════════════${NC}\n"
printf "${BOLD}  Hermes update — done${NC}\n"
printf "${BOLD}══════════════════════════════════════════════${NC}\n"
echo ""

if [[ ${#WARNS[@]} -gt 0 ]]; then
    printf "${YLW}Warnings:${NC}\n"
    for w in "${WARNS[@]}"; do printf "  • %s\n" "$w"; done
    echo ""
fi

if [[ ${#ACTS[@]} -gt 0 ]]; then
    printf "${YLW}Recommended actions:${NC}\n"
    for a in "${ACTS[@]}"; do printf "  → %s\n" "$a"; done
else
    printf "${GRN}✓ All systems nominal — no further action required.${NC}\n"
fi

echo ""
printf "  Gateway:   ${BOLD}hermes gateway status${NC}\n"
printf "  Logs:      ${BOLD}hermes logs${NC}\n"
printf "  Health:    ${BOLD}hermes doctor${NC}\n"
printf "  Dashboard: ${BOLD}hermes-dashboard${NC}\n"
echo ""

exit $FINAL_RC
