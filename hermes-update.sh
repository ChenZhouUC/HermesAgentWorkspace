#!/usr/bin/env bash
# ~/.hermes/hermes-update.sh
#
# Comprehensive Hermes update script.
# Runs the full update sequence and shows a final status summary.
#
# Covers:
#   1. Preflight checks
#   2. Save & clean local patches  → patches/local-patches.diff + git checkout
#   3. git pull + uv pip install   (via hermes update)
#   4. Skills Hub sync             (via hermes update)
#   5. Config migration check      (via hermes update, interactive)
#   6. Gateway process restart     (via hermes update, if already running)
#   7. Gateway launchd plist refresh (hermes gateway install --force)
#   8. Ensure gateway running
#   9. zsh completion script regeneration
#  10. Re-apply & verify local patches
#  11. Health verification (hermes doctor + gateway status)
#
# ⚠  Keep this script in sync with upstream workflow changes:
#    - If hermes update adds/removes steps, review whether steps 7–9 are still needed
#    - If gateway install flags change, update step 7
#    - If venv or binary paths move, update step 9
#    - Steps 2 + 10 manage local patches to hermes-agent source files.
#      The saved diff lives at ~/.hermes/patches/local-patches.diff and is
#      tracked in the config repo. If a patch conflicts with upstream after an
#      update, follow the instructions in the summary or see README.md § 本地补丁.
#    Referenced from README.md § 更新
#
# Usage:
#   bash ~/.hermes/hermes-update.sh
#   chmod +x ~/.hermes/hermes-update.sh && ~/.hermes/hermes-update.sh

set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"
PATCHES_DIR="${HERMES_HOME}/patches"
PATCH_FILE="${PATCHES_DIR}/local-patches.diff"

# Files we maintain local patches for (relative to HERMES_AGENT).
# Note: completions/_hermes (PATCH-3) is handled separately in step 6 via
# inline python rewrite, not via git diff, since it lives outside HERMES_AGENT.
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "hermes_cli/doctor.py"
    "hermes_cli/main.py"
)

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
# "PID" = NNNN only when the process is running.
gw_running() {
    hermes gateway status 2>&1 | grep -q '"PID"'
}

# ── Trap: restore patches if script dies after reverting them ────────────────
# Set to true in step 2 after reverting; cleared once hermes update completes.
_PATCHES_REVERTED=false

_trap_restore_patches() {
    if $_PATCHES_REVERTED && [[ -f "${PATCH_FILE}" ]]; then
        printf "\n${YLW}⚠${NC}  Script exited early — attempting to restore local patches...\n"
        cd "${HERMES_AGENT}" && git apply "${PATCH_FILE}" 2>/dev/null ||
            git apply --3way "${PATCH_FILE}" 2>/dev/null ||
            printf "  ${RED}✗${NC} Could not auto-restore. Run: cd %s && git apply %s\n" "${HERMES_AGENT}" "${PATCH_FILE}"
    fi
}
trap _trap_restore_patches EXIT

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

# ── 2. Save & clean local patches ────────────────────────────────────────────
# Save all local patches to patches/local-patches.diff, then revert the files
# to HEAD so that hermes update finds a clean tree and skips git stash entirely.
# This eliminates stash-conflict failures. A trap restores patches on early exit.
step "Saving local patches"

mkdir -p "${PATCHES_DIR}"
cd "${HERMES_AGENT}"

_CHANGED_PATCH_FILES=()
for _f in "${PATCHED_FILES[@]}"; do
    if ! git --no-pager diff --quiet HEAD -- "${_f}" 2>/dev/null; then
        _CHANGED_PATCH_FILES+=("${_f}")
    fi
done

if [[ ${#_CHANGED_PATCH_FILES[@]} -gt 0 ]]; then
    git --no-pager diff HEAD -- "${_CHANGED_PATCH_FILES[@]}" >"${PATCH_FILE}"
    ok "Saved ${#_CHANGED_PATCH_FILES[@]} patched file(s) → patches/local-patches.diff"
    git checkout HEAD -- "${_CHANGED_PATCH_FILES[@]}"
    _PATCHES_REVERTED=true
    ok "Reverted patched files to HEAD (clean tree for git pull)"
    # Warn if OTHER unrelated changes exist — hermes update will still stash those.
    _DIRTY=$(git status --porcelain 2>/dev/null)
    if [[ -n "${_DIRTY}" ]]; then
        warn "Other uncommitted changes remain in hermes-agent (outside patch set):"
        printf '%s\n' "${_DIRTY}" | sed 's/^/      /'
        add_warn "hermes update will stash those unrelated changes — verify they restore correctly"
    fi
elif [[ -f "${PATCH_FILE}" ]]; then
    note "Patches already clean — will re-apply from saved patches/local-patches.diff after update"
else
    note "No local patches to save — update will proceed on a clean tree"
fi

cd - >/dev/null

# ── 3. hermes update ──────────────────────────────────────────────────────────
# Handles: git pull · uv pip install · skills sync · config migration prompts
#          · gateway process restart (running launchd/systemd instances)
# Tree is now clean (patches were reverted in step 2), so hermes update will
# not need to stash and the pull/reset will succeed without conflicts.
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

# Patches have been reverted; hermes update is now complete.
# Clear the trap flag — patches will be re-applied in step 10.
_PATCHES_REVERTED=false

# ── 4. Refresh gateway launchd plist ─────────────────────────────────────────
# Only bootstrap the plist when the service is not already loaded. hermes update
# handles plist installation; calling install --force on an already-bootstrapped
# service triggers launchd exit 5 (Input/Output error). If the service is loaded
# but not running (OnDemand=true), skip directly to step 5 (hermes gateway start).
step "Gateway launchd plist"

set +e
GW_IS_RUNNING=false
gw_running && GW_IS_RUNNING=true
GW_IS_LOADED=false
launchctl list 2>/dev/null | grep -q "ai.hermes.gateway" && GW_IS_LOADED=true
set -e

if $GW_IS_RUNNING; then
    ok "Gateway running post-update — plist refresh not needed"
    note "To force-refresh the plist manually: hermes gateway install --force"
elif $GW_IS_LOADED; then
    ok "Gateway plist already loaded (OnDemand) — will start in step 5"
else
    note "Gateway not bootstrapped — installing plist..."
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

# ── 5. Ensure gateway is running ──────────────────────────────────────────────
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

# ── 6. Update zsh completions ─────────────────────────────────────────────────
step "Updating zsh completions"

COMP_FILE="${HERMES_HOME}/completions/_hermes"
mkdir -p "${HERMES_HOME}/completions"

set +e
hermes completion zsh >"${COMP_FILE}" 2>/dev/null
COMP_RC=$?
set -e

if [[ $COMP_RC -eq 0 ]]; then
    ok "Written: ${COMP_FILE}"

    # PATCH-3: fix invalid _arguments spec syntax generated by upstream.
    # hermes completion zsh emits (...){...} combos which zsh _arguments
    # rejects with "invalid argument", causing Tab completion to silently
    # return nothing. Apply the fix immediately after generation; skip if
    # upstream has already corrected the output.
    # See: README.md § 本地补丁记录 [PATCH-3]
    if grep -q '){-h,--help}' "${COMP_FILE}" 2>/dev/null ||
        grep -q '){-V,--version}' "${COMP_FILE}" 2>/dev/null ||
        grep -q '){-p,--profile}' "${COMP_FILE}" 2>/dev/null; then
        python3 - "${COMP_FILE}" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
fixes = [
    (
        "        '(-h --help){-h,--help}[Show help and exit]' \\",
        "        '(- :)-h[Show help and exit]' \\\n        '(- :)--help[Show help and exit]' \\"
    ),
    (
        "        '(-V --version){-V,--version}[Show version and exit]' \\",
        "        '(- :)-V[Show version and exit]' \\\n        '(- :)--version[Show version and exit]' \\"
    ),
    (
        "        '(-p --profile){-p,--profile}[Profile name]:profile:_hermes_profiles' \\",
        "        '(-p --profile)-p[Profile name]:profile:_hermes_profiles' \\\n        '(-p --profile)--profile[Profile name]:profile:_hermes_profiles' \\"
    ),
]
for old, new in fixes:
    content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
PYEOF
        ok "PATCH-3 applied: fixed _arguments invalid syntax in completion script"
    else
        ok "PATCH-3: upstream completion output already uses correct syntax — no fix needed"
    fi

    rm -f ~/.zcompdump*
    note "zsh completion cache cleared (rebuilds on next shell open)"
else
    warn "Could not generate completions (exit $COMP_RC)"
    add_act "Run: hermes completion zsh > ~/.hermes/completions/_hermes"
fi

# ── 7. Re-apply & verify local patches ───────────────────────────────────────
# Re-applies the saved diff (from step 2). Runs behavioral + structural checks
# before accepting the result. Only refreshes the saved diff on full success,
# so the canonical patch is never overwritten with a bad/partial merge.
step "Re-applying local patches"

VENV_PY="${HERMES_AGENT}/venv/bin/python3"
SKILL_TOOL="${HERMES_AGENT}/tools/skill_manager_tool.py"
DOCTOR_PY="${HERMES_AGENT}/hermes_cli/doctor.py"

# -- 7a. Apply saved diff -------------------------------------------------------
if [[ -f "${PATCH_FILE}" ]]; then
    cd "${HERMES_AGENT}"
    if git apply --check "${PATCH_FILE}" 2>/dev/null; then
        git apply "${PATCH_FILE}"
        ok "Patches applied cleanly from patches/local-patches.diff"
    elif git apply --3way "${PATCH_FILE}" 2>/dev/null; then
        # 3-way may silently produce conflict markers — detect them
        _CONFLICTS=$(git diff --check 2>&1 || true)
        if [[ -n "${_CONFLICTS}" ]]; then
            warn "3-way apply introduced conflict markers — patches NOT fully active"
            add_warn "Patch conflict markers present in hermes-agent source"
            add_act "Resolve conflicts: cd ${HERMES_AGENT} && git diff --check"
            add_act "See README.md § 本地补丁 for re-application instructions"
        else
            ok "Patches applied via 3-way merge (upstream changed same area)"
        fi
    else
        warn "Patches could not be applied (upstream conflict)"
        add_warn "Local patches were NOT applied — some customizations inactive"
        add_act "Manual fix: cd ${HERMES_AGENT} && git apply --reject ${PATCH_FILE}"
        add_act "See README.md § 本地补丁 for re-application instructions"
    fi
    cd - >/dev/null
else
    note "No saved patch file — skipping apply (fresh install or patches never saved)"
fi

# -- 7b. Behavioral verification -----------------------------------------------
_SKILL_PATCH_OK=false
_DOCTOR_PATCH_OK=false

if [[ -f "${VENV_PY}" && -f "${SKILL_TOOL}" ]]; then
    _SKILL_CHECK=$(
        cd "${HERMES_AGENT}" &&
            "${VENV_PY}" - <<'PYEOF' 2>/dev/null
import sys
sys.path.insert(0, ".")
from tools.skill_manager_tool import _resolve_skill_dir
result = str(_resolve_skill_dir("_patch_test"))
print("ok" if "my-skills" in result or "/skills/_patch_test" not in result else "native")
PYEOF
    )
    if [[ "${_SKILL_CHECK}" == "ok" ]]; then
        ok "Skill routing patch: active (new skills → my-skills/)"
        _SKILL_PATCH_OK=true
    else
        warn "Skill routing patch inactive — new skills will land in ~/.hermes/skills/"
        add_act "Re-apply: see README.md § Skills → 自定义 Skill 创建路径修复"
    fi
else
    warn "Could not locate venv or skill_manager_tool.py — skipping skill routing check"
fi

if [[ -f "${DOCTOR_PY}" ]]; then
    if grep -q "_get_platform_tools" "${DOCTOR_PY}" 2>/dev/null; then
        ok "Doctor issue-count patch: active (unused tools excluded from issue count)"
        _DOCTOR_PATCH_OK=true
    else
        warn "Doctor issue-count patch inactive — hermes doctor may report false issue for moa/rl"
        add_act "Re-apply: see README.md § doctor.py issue count 修复"
    fi
else
    warn "Could not locate hermes_cli/doctor.py — skipping doctor patch check"
fi

# -- 7c. Refresh saved diff only after full verification -----------------------
# Regenerating the diff captures any upstream changes that touched our patched
# files but did not conflict. Only do this once BOTH patches are confirmed live.
if $_SKILL_PATCH_OK && $_DOCTOR_PATCH_OK; then
    cd "${HERMES_AGENT}"
    _REFRESHED=()
    for _f in "${PATCHED_FILES[@]}"; do
        if ! git --no-pager diff --quiet HEAD -- "${_f}" 2>/dev/null; then
            _REFRESHED+=("${_f}")
        fi
    done
    if [[ ${#_REFRESHED[@]} -gt 0 ]]; then
        git --no-pager diff HEAD -- "${_REFRESHED[@]}" >"${PATCH_FILE}"
        ok "patches/local-patches.diff refreshed (${#_REFRESHED[@]} file(s))"
    fi
    cd - >/dev/null
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

# ── Summary ───────────────────────────────────────────────────────────────────
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
