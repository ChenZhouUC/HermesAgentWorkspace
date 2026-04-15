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
#   7. Local patch verification  (skill routing + doctor issue count)
#   8. Health verification (hermes doctor + gateway status)
#
# ⚠  Keep this script in sync with upstream workflow changes:
#    - If hermes update adds/removes steps, review whether steps 5–6 are still needed
#    - If gateway install flags change, update step 5
#    - If venv or binary paths move, update step 6
#    - Step 7a checks a local patch to tools/skill_manager_tool.py that routes
#      new agent-created skills to ~/.hermes/my-skills/ (external_dirs).
#      hermes update stash-restores this patch automatically; if a conflict
#      arises, resolve it in ~/.hermes/hermes-agent/tools/skill_manager_tool.py
#      (see README.md § Skills → 自定义 Skill 创建路径修复 for details).
#    - Step 7b checks a local patch to hermes_cli/doctor.py that suppresses
#      false issue reports for moa/rl (disabled optional tools with missing API
#      keys). Re-apply if lost: see README.md § doctor.py issue count 修复.
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

# Returns 0 (true) if the launchd gateway service has an active PID.
# hermes gateway status on macOS outputs a launchd JSON blob that contains
# "PID" = NNNN only when the process is running; the words "running"/"active"
# do not appear in the output.
gw_running() {
    hermes gateway status 2>&1 | grep -q '"PID"'
}

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

# ── 3. Refresh gateway launchd plist ─────────────────────────────────────────
# Only refresh the plist when the gateway is NOT already running post-update.
# When hermes update successfully restarted the service it used the current
# plist. Force-reinstalling an already-running service triggers a bootout then
# bootstrap; the bootstrap can fail with launchd exit 5 (I/O error) due to
# timing, leaving the service unloaded. Skip this step if the gateway is live.
step "Gateway launchd plist"

set +e
GW_IS_RUNNING=false
gw_running && GW_IS_RUNNING=true
set -e

if $GW_IS_RUNNING; then
    ok "Gateway running post-update — plist refresh not needed"
    note "To force-refresh the plist manually: hermes gateway install --force"
else
    note "Gateway not running — installing/refreshing plist..."
    set +e
    hermes gateway install --force
    GW_INSTALL_RC=$?
    set -e
    if [[ $GW_INSTALL_RC -eq 0 ]]; then
        ok "Plist installed/refreshed"
    else
        warn "hermes gateway install --force returned $GW_INSTALL_RC"
        add_act "Run manually: hermes gateway install --force"
    fi
fi

# ── 4. Ensure gateway is running ──────────────────────────────────────────────
# hermes update already restarts a running gateway; this step only fires if
# the gateway was stopped before the update (or install --force started it).
set +e
GW_IS_RUNNING=false
gw_running && GW_IS_RUNNING=true
set -e

if ! $GW_IS_RUNNING; then
    note "Gateway not running — starting..."
    set +e
    hermes gateway start 2>&1
    GW_START_RC=$?
    set -e
    sleep 3 # give launchd a moment to spawn the process
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

# ── 7a. Verify local skill-routing patch ─────────────────────────────────────
# hermes update stash-restores local modifications to hermes-agent source.
# This step confirms the patch that routes new skills to my-skills/ survived.
# If stash-restore had a conflict the patch may be missing or partial.
step "Skill routing patch (7a)"

SKILL_TOOL="${HERMES_AGENT}/tools/skill_manager_tool.py"
VENV_PY="${HERMES_AGENT}/venv/bin/python3"

if [[ -f "${VENV_PY}" && -f "${SKILL_TOOL}" ]]; then
    PATCH_CHECK=$(
        cd "${HERMES_AGENT}" &&
            "${VENV_PY}" - <<'PYEOF' 2>/dev/null
import sys
sys.path.insert(0, ".")
from tools.skill_manager_tool import _resolve_skill_dir
result = str(_resolve_skill_dir("_patch_test"))
# Pass if result is NOT inside the bundled skills dir
print("ok" if "my-skills" in result or "/skills/_patch_test" not in result else "native")
PYEOF
    )
    if [[ "${PATCH_CHECK}" == "ok" ]]; then
        ok "New skills route to my-skills/ (external_dirs)"
    else
        warn "skill_manager_tool.py routing patch missing — new skills land in ~/.hermes/skills/"
        add_warn "Skill routing patch lost (likely stash conflict). New skills will go to native skills dir."
        add_act "Re-apply patch: see README.md § Skills → 自定义 Skill 创建路径修复"
    fi
else
    warn "Could not locate venv or skill_manager_tool.py — skipping patch check"
fi

# ── 7b. Verify doctor issue-count patch ──────────────────────────────────────
# This patch prevents moa/rl (disabled optional tools) from being counted as
# "issues" by hermes doctor when their API keys aren't configured.
step "Doctor issue-count patch (7b)"

DOCTOR_PY="${HERMES_AGENT}/hermes_cli/doctor.py"
if [[ -f "${DOCTOR_PY}" ]]; then
    if grep -q "_get_platform_tools" "${DOCTOR_PY}" 2>/dev/null; then
        ok "doctor.py patch present (unused tools excluded from issue count)"
    else
        warn "doctor.py patch missing — hermes doctor may report false issue for moa/rl"
        add_act "Re-apply doctor.py patch: see README.md § 'doctor.py issue count 修复'"
    fi
else
    warn "Could not locate hermes_cli/doctor.py — skipping patch check"
fi

# ── 8. Verify ─────────────────────────────────────────────────────────────────
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
# Doctor summarises problems as "Found N issue(s) to address"
if echo "$DOCTOR_OUT" | grep -qE 'Found [0-9]+ issue'; then
    add_act "hermes doctor found issues — run: hermes doctor --fix"
fi
echo ""

GW_FINAL=$(hermes gateway status 2>&1)
echo "$GW_FINAL"
if gw_running; then
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
