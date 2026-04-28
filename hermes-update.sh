#!/usr/bin/env bash
# ~/.hermes/hermes-update.sh
#
# Comprehensive Hermes update script.
# Runs the full update sequence and shows a final status summary.
#
# Covers:
#   1. Preflight checks
#   2. Save & clean local patches  → patches/local-patches.diff + git checkout
#   3. hermes update               (pull · deps · web · skills · config migration · restart)
#   4. npm audit fix               (fix known npm vulnerabilities after deps install)
#   4b. Skills mirror sync         (rsync --delete to match upstream exactly)
#   5. Gateway launchd plist refresh (hermes gateway install --force, if needed)
#   6. Ensure gateway running
#   7. zsh completion script regeneration
#   8. Re-apply & verify local patches
#      8a. Apply saved diff
#      8b. Behavioral verification
#      8c. Refresh saved diff
#      8d. Gateway restart         (reload patched Python modules into running process)
#   9. Health verification         (hermes doctor + gateway status)
#
# ⚠  Keep this script in sync with upstream workflow changes:
#    - If hermes update adds/removes steps, review whether steps 5–9 are still needed
#    - If gateway install flags change, update step 5
#    - If venv or binary paths move, update step 7
#    - Steps 2 + 8 manage local patches to hermes-agent source files.
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
# Note: completions/_hermes (PATCH-3) is handled separately in step 7 via
# inline python rewrite, not via git diff, since it lives outside HERMES_AGENT.
# PATCH-5 (delegate_tool), PATCH-8 (Gemini thought_signature) and PATCH-4
# (hermes_cli/main.py dashboard web-build skip) were merged upstream and
# removed from this list.
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "hermes_cli/doctor.py"
    "pyproject.toml"
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

# Returns 0 if any of the given files contain git merge conflict markers.
# Unlike `git diff --check`, this only catches actual conflict markers —
# it ignores trailing-whitespace and indent-style issues that would
# otherwise cause false-positive rollbacks.
_has_conflict_markers() {
    local _f
    for _f in "$@"; do
        [[ -f "$_f" ]] || continue
        if grep -qE '^(<<<<<<<($| )|=======$|>>>>>>>($| ))' "$_f" 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

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
    git --no-pager diff HEAD -- "${_CHANGED_PATCH_FILES[@]}" >"${PATCH_FILE}.tmp" &&
        mv -f "${PATCH_FILE}.tmp" "${PATCH_FILE}"
    ok "Saved ${#_CHANGED_PATCH_FILES[@]} patched file(s) → patches/local-patches.diff"
    git checkout HEAD -- "${_CHANGED_PATCH_FILES[@]}"
    _PATCHES_REVERTED=true
    ok "Reverted patched files to HEAD (clean tree for git pull)"
    # Warn if OTHER unrelated changes exist — step 3 will auto-clean them.
    _DIRTY=$(git status --porcelain 2>/dev/null)
    if [[ -n "${_DIRTY}" ]]; then
        note "Other uncommitted changes in hermes-agent (will be auto-stashed in step 3):"
        printf '%s\n' "${_DIRTY}" | sed 's/^/      /'
    fi
elif [[ -f "${PATCH_FILE}" ]]; then
    note "Patches already clean — will re-apply from saved patches/local-patches.diff after update"
else
    note "No local patches to save — update will proceed on a clean tree"
fi

cd - >/dev/null

# ── 3. hermes update ──────────────────────────────────────────────────────────
# Handles: pull · deps · web · skills · config migration · restart
# Tree should be clean after step 2 (patches reverted). However, other
# uncommitted changes outside PATCHED_FILES can still trigger hermes update's
# interactive stash prompt.  To avoid this, fully clean the hermes-agent tree
# before invoking hermes update: stash everything (including untracked),
# pull cleanly, then pop the stash with "theirs" strategy (upstream wins for
# any overlap — our patches are re-applied from the saved diff in step 8).
step "Updating Hermes  [pull · deps · web · skills · restart]"
echo ""

cd "${HERMES_AGENT}"
_EXTRA_STASH_REF=""
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    _EXTRA_STASH_REF=$(git stash create 2>/dev/null || true)
    if [[ -n "${_EXTRA_STASH_REF}" ]]; then
        git stash store -m "hermes-update-extra-$(date +%Y%m%d-%H%M%S)" "${_EXTRA_STASH_REF}"
        note "Stashed extra uncommitted changes → ${_EXTRA_STASH_REF:0:12}"
    fi
    git checkout -- . 2>/dev/null || true
    git clean -fd 2>/dev/null || true
    ok "hermes-agent tree is fully clean"
fi
cd - >/dev/null

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

# If we stashed extra changes above, silently pop them back.
# Conflicts are expected (upstream may have changed same files); use checkout
# --theirs to prefer upstream, since our patches are re-applied from the diff.
if [[ -n "${_EXTRA_STASH_REF}" ]]; then
    cd "${HERMES_AGENT}"
    if git stash pop --quiet 2>/dev/null; then
        ok "Restored extra changes from stash"
    else
        # Pop failed (conflict) — reset to clean and leave stash for manual recovery
        git reset --hard HEAD >/dev/null 2>&1
        note "Extra stash could not auto-merge — kept in stash for manual recovery"
        note "  Recover with: cd ${HERMES_AGENT} && git stash list"
    fi
    cd - >/dev/null
fi

# Patches have been reverted; hermes update is now complete.
# Clear the trap flag — patches will be re-applied in step 8.
_PATCHES_REVERTED=false

# ── 4. npm audit fix ─────────────────────────────────────────────────────────
# hermes update runs `npm install --no-audit` for node-based tools (e.g.
# agent-browser). This can leave known npm vulnerabilities unfixed.
# Run npm audit fix to patch them automatically.
step "Fixing npm vulnerabilities"

cd "${HERMES_AGENT}"
set +e
_AUDIT_OUT=$(npm audit fix --quiet 2>&1)
_AUDIT_RC=$?
set -e

if [[ $_AUDIT_RC -eq 0 ]]; then
    if echo "${_AUDIT_OUT}" | grep -q "changed"; then
        ok "npm audit fix: $(echo "${_AUDIT_OUT}" | grep 'changed' | head -1)"
    else
        ok "npm audit: no vulnerabilities to fix"
    fi
else
    warn "npm audit fix exited $_AUDIT_RC — non-critical"
    add_act "Run manually: cd ${HERMES_AGENT} && npm audit fix"
fi
cd - >/dev/null

# ── 4b. Full skills sync (mirror upstream) ────────────────────────────────────
# hermes update copies bundled skills from hermes-agent/skills/ → ~/.hermes/skills/
# but only adds, never removes. This leaves orphans when upstream deletes a skill.
# Use rsync --delete to make ~/.hermes/skills/ an exact mirror of upstream.
# User-created skills live in my-skills/ (configured via external_dirs) and are
# never touched by this step.
BUNDLED_SKILLS_DIR="${HERMES_AGENT}/skills"
LOCAL_SKILLS_DIR="${HERMES_HOME}/skills"

step "Skills sync (mirror upstream)"
if [[ -d "${BUNDLED_SKILLS_DIR}" ]]; then
    mkdir -p "${LOCAL_SKILLS_DIR}"
    # --archive preserves structure, --delete removes anything not in upstream
    _SYNC_OUT=$(rsync -a --delete --itemize-changes \
        "${BUNDLED_SKILLS_DIR}/" "${LOCAL_SKILLS_DIR}/" 2>&1) || true

    _ADDED=$(echo "${_SYNC_OUT}" | grep -c '^>f+++' || true)
    _UPDATED=$(echo "${_SYNC_OUT}" | grep -c '^>f[^+]' || true)
    _DELETED=$(echo "${_SYNC_OUT}" | grep -c '^\*deleting' || true)

    if [[ ${_ADDED} -gt 0 || ${_UPDATED} -gt 0 || ${_DELETED} -gt 0 ]]; then
        ok "Skills synced: +${_ADDED} new, ~${_UPDATED} updated, -${_DELETED} removed"
    else
        ok "Skills already in sync with upstream"
    fi
else
    warn "Bundled skills dir not found: ${BUNDLED_SKILLS_DIR}"
    add_act "Check hermes-agent installation — skills directory missing"
fi

# ── 5. Refresh gateway launchd plist ─────────────────────────────────────────
# Only bootstrap the plist when the service is not already loaded. hermes update
# handles plist installation; calling install --force on an already-bootstrapped
# service triggers launchd exit 5 (Input/Output error). If the service is loaded
# but not running (OnDemand=true), skip directly to step 6 (ensure gateway running).
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
    ok "Gateway plist already loaded (OnDemand) — will start in step 6"
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

# ── 6. Ensure gateway is running ──────────────────────────────────────────────
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

# ── 7. Update zsh completions ─────────────────────────────────────────────────
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

# ── 8. Re-apply & verify local patches ───────────────────────────────────────
# Re-applies the saved diff (from step 2). Runs behavioral + structural checks
# before accepting the result. Only refreshes the saved diff on full success,
# so the canonical patch is never overwritten with a bad/partial merge.
step "Re-applying local patches"

VENV_PY="${HERMES_AGENT}/venv/bin/python3"
SKILL_TOOL="${HERMES_AGENT}/tools/skill_manager_tool.py"
DOCTOR_PY="${HERMES_AGENT}/hermes_cli/doctor.py"
DELEGATE_TOOL="${HERMES_AGENT}/tools/delegate_tool.py"
PYPROJECT="${HERMES_AGENT}/pyproject.toml"
_PATCH_APPLY_OK=false

# -- 8a. Apply saved diff -------------------------------------------------------
if [[ -f "${PATCH_FILE}" ]]; then
    cd "${HERMES_AGENT}"
    if grep -nE '^\+?(<<<<<<<|=======|>>>>>>>)' "${PATCH_FILE}" >/dev/null 2>&1; then
        warn "Saved patch file contains conflict markers — skipping auto-apply"
        add_warn "patches/local-patches.diff is poisoned with merge conflict markers"
        add_act "Repair ${PATCH_FILE} (or restore it from git) before re-running this script"
        add_act "Restore last committed patch file: cd ${HERMES_HOME} && git restore --source=HEAD -- patches/local-patches.diff"
    else
        _PATCH_MODE=""
        if git apply --check "${PATCH_FILE}" 2>/dev/null; then
            if git apply "${PATCH_FILE}" 2>/dev/null; then
                _PATCH_MODE="clean"
            else
                git restore --source=HEAD --staged --worktree -- "${PATCHED_FILES[@]}" 2>/dev/null || true
                warn "Patches passed --check but apply failed unexpectedly"
                add_warn "Local patches were NOT applied — some customizations inactive"
                add_act "Retry manually: cd ${HERMES_AGENT} && git apply ${PATCH_FILE}"
                add_act "See README.md § 本地补丁 for re-application instructions"
            fi
        elif git apply --3way "${PATCH_FILE}" 2>/dev/null; then
            _PATCH_MODE="3-way"
        else
            git restore --source=HEAD --staged --worktree -- "${PATCHED_FILES[@]}" 2>/dev/null || true
            warn "Patches could not be applied (upstream conflict)"
            add_warn "Local patches were NOT applied — some customizations inactive"
            add_act "Manual fix: cd ${HERMES_AGENT} && git apply --reject ${PATCH_FILE}"
            add_act "See README.md § 本地补丁 for re-application instructions"
        fi

        if [[ -n "${_PATCH_MODE}" ]]; then
            if _has_conflict_markers "${PATCHED_FILES[@]}"; then
                git restore --source=HEAD --staged --worktree -- "${PATCHED_FILES[@]}" 2>/dev/null || true
                warn "${_PATCH_MODE} apply introduced conflict markers — restored patched files to HEAD"
                add_warn "Patch re-apply produced conflicts; patched files were restored to clean upstream state"
                add_act "Inspect drift: cd ${HERMES_AGENT} && git apply --reject ${PATCH_FILE}"
                add_act "See README.md § 本地补丁 for re-application instructions"
            else
                _PATCH_APPLY_OK=true
                if [[ "${_PATCH_MODE}" == "clean" ]]; then
                    ok "Patches applied cleanly from patches/local-patches.diff"
                else
                    ok "Patches applied via 3-way merge (upstream changed same area)"
                fi
            fi
        fi
    fi
    cd - >/dev/null
else
    note "No saved patch file — skipping apply (fresh install or patches never saved)"
fi

# -- 8b. Behavioral verification -----------------------------------------------
# PATCH-5 (delegate ACP routing) was merged upstream in v0.10.0.
# PATCH-4 (dashboard web-build skip) was merged upstream in v0.11.x via
# upstream commit 5b5a53a1 introducing _web_ui_build_needed().
_SKILL_PATCH_OK=false
_DOCTOR_PATCH_OK=false
_DELEGATE_PATCH_OK=false
_FEISHU_DEPS_PATCH_OK=false

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
        add_act "Re-apply: see PATCHES.md § [PATCH-1] skill_manager_tool.py"
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
        add_act "Re-apply: see PATCHES.md § [PATCH-2] doctor.py issue count"
    fi
else
    warn "Could not locate hermes_cli/doctor.py — skipping doctor patch check"
fi

# PATCH-4 (dashboard web-build skip) was merged upstream via _web_ui_build_needed()
# in commit 5b5a53a1; verify the upstream helper is present so we can detect
# regressions, but no local patch is required.
MAIN_PY="${HERMES_AGENT}/hermes_cli/main.py"
if [[ -f "${MAIN_PY}" ]]; then
    if grep -q '_web_ui_build_needed' "${MAIN_PY}" 2>/dev/null; then
        ok "Dashboard web-build skip: active (upstream merged, PATCH-4 retired)"
    else
        warn "Upstream _web_ui_build_needed() missing — dashboard may rebuild on every start"
        add_act "Check upstream: hermes_cli/main.py should define _web_ui_build_needed()"
    fi
fi

# PATCH-5 (delegate ACP routing) was merged upstream in v0.10.0.
# Verify the behavior still exists but don't require local patch.
if [[ -f "${DELEGATE_TOOL}" ]]; then
    if grep -q 'override_acp_command' "${DELEGATE_TOOL}" 2>/dev/null &&
        grep -q 'copilot-acp' "${DELEGATE_TOOL}" 2>/dev/null; then
        ok "Delegate ACP routing: active (upstream merged, PATCH-5 retired)"
        _DELEGATE_PATCH_OK=true
    else
        warn "Delegate ACP routing missing — delegate_task acp_command may be ignored"
        add_act "Check upstream: _build_child_agent should force copilot-acp when override_acp_command is set"
    fi
else
    warn "Could not locate tools/delegate_tool.py — skipping delegate patch check"
fi

if [[ -f "${PYPROJECT}" ]]; then
    if grep -q 'python-socks' "${PYPROJECT}" 2>/dev/null; then
        ok "Feishu python-socks dep patch: active (proxy support in feishu extra)"
        _FEISHU_DEPS_PATCH_OK=true
    else
        warn "Feishu python-socks dep patch inactive — feishu gateway may fail behind proxy"
        add_act "Re-apply: see PATCHES.md § [PATCH-7] pyproject.toml feishu python-socks"
    fi
else
    warn "Could not locate pyproject.toml — skipping feishu deps check"
fi

# -- 8c. Refresh saved diff only after full verification -----------------------
# Regenerating the diff captures any upstream changes that touched our patched
# files but did not conflict. Only do this once ALL patches are confirmed live
# and the patched files are conflict-marker-free.
if $_PATCH_APPLY_OK && $_SKILL_PATCH_OK && $_DOCTOR_PATCH_OK && $_DELEGATE_PATCH_OK && $_FEISHU_DEPS_PATCH_OK; then
    cd "${HERMES_AGENT}"
    if _has_conflict_markers "${PATCHED_FILES[@]}"; then
        warn "Patched files contain conflict markers — skipping diff refresh"
        add_warn "patches/local-patches.diff was NOT refreshed because patched files are not clean"
        add_act "Inspect patched files: cd ${HERMES_AGENT} && grep -rnE '^(<{7}|={7}|>{7})' ${PATCHED_FILES[*]}"
    else
        _REFRESHED=()
        for _f in "${PATCHED_FILES[@]}"; do
            if ! git --no-pager diff --quiet HEAD -- "${_f}" 2>/dev/null; then
                _REFRESHED+=("${_f}")
            fi
        done
        if [[ ${#_REFRESHED[@]} -gt 0 ]]; then
            git --no-pager diff HEAD -- "${_REFRESHED[@]}" >"${PATCH_FILE}.tmp" &&
                mv -f "${PATCH_FILE}.tmp" "${PATCH_FILE}"
            ok "patches/local-patches.diff refreshed (${#_REFRESHED[@]} file(s))"
            # Record upstream base commit for provenance tracking
            printf '%s %s\n' "$(git rev-parse HEAD)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                >"${PATCHES_DIR}/.local-patches.base"
        elif [[ -f "${PATCH_FILE}" ]]; then
            # All patches are now upstream — diff is empty but file still exists.
            note "All patched files match upstream HEAD — patches may have been absorbed"
            note "Review PATCHED_FILES list and PATCHES.md for stale entries"
            add_act "If patches are fully upstream, prune PATCHED_FILES in hermes-update.sh and PATCHES.md"
        fi
    fi
    cd - >/dev/null
fi

# ── 8d. Gateway restart (post-patch) ─────────────────────────────────────────
# hermes update (step 3) restarts the gateway BEFORE patches are re-applied.
# The running Python process still has the pre-patch modules cached in
# sys.modules. A restart ensures patched code (skill routing, delegate ACP
# routing, etc.) is loaded by the gateway immediately. On macOS, stopping the
# launchd job can briefly leave it unloaded, so poll for the PID instead of
# assuming a fixed 3s start window is sufficient.
if $_PATCH_APPLY_OK; then
    set +e
    if gw_running; then
        step "Restarting gateway (loading patched code)"
        hermes gateway stop >/dev/null 2>&1
        sleep 2
        _GW_RESTART_OUT=$(hermes gateway start 2>&1)
        _GW_RESTART_RC=$?
        for _ in {1..12}; do
            sleep 1
            if gw_running; then
                break
            fi
        done
        if gw_running; then
            ok "Gateway restarted — patched modules now active"
        else
            warn "Gateway did not come back up after restart"
            if [[ -n "${_GW_RESTART_OUT:-}" ]]; then
                add_warn "gateway start output: ${_GW_RESTART_OUT//$'\n'/ | }"
            elif [[ ${_GW_RESTART_RC:-0} -ne 0 ]]; then
                add_warn "gateway start exited ${_GW_RESTART_RC}"
            fi
            add_act "Start gateway manually: hermes gateway start"
        fi
    fi
    set -e
fi

# ── 9. Verify ─────────────────────────────────────────────────────────────────
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
printf "  Dashboard: ${BOLD}hermes dashboard${NC}\n"
echo ""

exit $FINAL_RC
