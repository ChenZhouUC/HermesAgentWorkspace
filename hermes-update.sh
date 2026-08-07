#!/usr/bin/env bash
# ~/.hermes/hermes-update.sh
#
# Comprehensive Hermes update/reconciliation script.
# An explicit --update acquires one upstream snapshot. Every retry or later
# convergence pass is pinned to that snapshot and performs no network fetch.
#
# Covers:
#   1. Preflight checks
#   2. Save & clean local patches  → patches/local-patches.diff + scoped git restore
#   3. upstream transaction        (--update: one fetch/pull; reconcile: pinned SHA, no network)
#   4. npm audit fix               (attempt non-breaking fixes; retain full residual audit output)
#   4b. Skills mirror sync         (rsync --delete upstream content; preserve runtime metadata)
#   5. Gateway launchd plist refresh (hermes gateway install --force, if needed)
#   6. Ensure gateway running
#   7. zsh completion script regeneration
#   8. Re-apply & verify local patches
#      8a. Apply saved diff
#      8b. Patch invariant gates     (structural sentinels + smoke checks)
#      8c. Refresh saved diff + re-sync patched bundled skills
#      8d. Gateway restart         (reload patched Python modules into running process)
#   8e. User-plugin compatibility checks (plugins/*/verify.sh)
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
#    - Step 8e runs verify.sh for each user plugin under ~/.hermes/plugins/.
#      When adding a new plugin, register its verify.sh in the
#      PLUGIN_VERIFIERS array below. See README.md § 用户插件 (Plugins).
#    Referenced from README.md § 更新
#
# Usage:
#   bash ~/.hermes/hermes-update.sh --update       # one new upstream snapshot
#   bash ~/.hermes/hermes-update.sh --reconcile    # pinned/local convergence; no fetch
#   bash ~/.hermes/hermes-update.sh                # same as --reconcile
#   bash ~/.hermes/hermes-update.sh --transaction-status
#   bash ~/.hermes/hermes-update.sh --print-restart-wait-seconds
#   bash ~/.hermes/hermes-update.sh --print-patched-files
#   bash ~/.hermes/hermes-update.sh --print-patched-tests
#   bash ~/.hermes/hermes-update.sh --self-test-transaction

# This file is an executable workflow, not a function library. Reject both
# bash and zsh source attempts before enabling strict mode or mutating state.
if [[ (-n "${ZSH_EVAL_CONTEXT:-}" && "${ZSH_EVAL_CONTEXT}" == *:file) ||
    (-n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "$0") ]]; then
    printf 'hermes-update.sh must be executed, not sourced.\n' >&2
    return 2
fi

set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"
PATCHES_DIR="${HERMES_HOME}/patches"
PATCH_FILE="${PATCHES_DIR}/local-patches.diff"
TRANSACTION_FILE="${HERMES_HOME}/.hermes-update-transaction"
TRANSACTION_LOCK_DIR="${HERMES_HOME}/.hermes-update-transaction.lock"
TRANSACTION_TARGET_REF="refs/hermes-update/target"

# Files we maintain local patches for (relative to HERMES_AGENT).
# Note: completions/_hermes (PATCH-ZSH-COMPLETION-SYNTAX) is handled separately in step 7 via
# inline python rewrite, not via git diff, since it lives outside HERMES_AGENT.
# As of v0.20.0 / main 863e31318553cda8ad61df681d08175364d4164b, `hermes completion zsh` already emits the
# canonical `'(-)'{-h,--help}'[...]'` form. The step 7 regression sentinel
# dates back to v0.13.0 (upstream commit fe61d95b4) and stays as a guard
# against future upstream regression.
# PATCH-DOCTOR-ENABLED-TOOLSETS (doctor issue-count), PATCH-DELEGATE-ACP-ROUTING (delegate_tool), PATCH-GEMINI-THOUGHT-SIGNATURE (Gemini
# thought_signature), PATCH-DASHBOARD-BUILD-CACHE (hermes_cli/main.py dashboard web-build skip),
# and PATCH-LAZY-ACTIVATION (first-declared lazy dependency as the activation anchor)
# were merged upstream and removed from this list.
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "pyproject.toml"
    "uv.lock"
    "tools/lazy_deps.py"
    "optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"
    "website/docs/guides/migrate-from-openclaw.md"
    "website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md"
    "gateway/authz_mixin.py"
    "gateway/config.py"
    "gateway/display_config.py"
    "plugins/platforms/feishu/adapter.py"
    "skills/research/llm-wiki/SKILL.md"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/slash_commands.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "gateway/stream_consumer.py"
    "hermes_cli/doctor.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/skill_utils.py"
    "tools/approval.py"
    "tests/tools/test_approval.py"
    "tools/skills_tool.py"
    "tests/tools/test_skills_tool.py"
    "toolsets.py"
    "tools/feishu_doc_tool.py"
    "tests/tools/test_feishu_tools.py"
    "tools/read_extract.py"
    "tests/tools/test_read_extract.py"
    "tests/gateway/feishu_helpers.py"
    "tests/gateway/test_config.py"
    "tests/gateway/test_display_config.py"
    "tests/gateway/test_feishu.py"
    "tests/gateway/test_document_context_note.py"
    "tests/gateway/test_feishu_bot_admission.py"
    "tests/gateway/test_feishu_bot_auth_bypass.py"
    "tests/gateway/test_session.py"
    "tests/gateway/test_session_env.py"
    "tests/gateway/test_run_progress_topics.py"
    "tests/gateway/test_background_command.py"
    "tests/gateway/test_verbose_command.py"
    "tests/gateway/test_stream_consumer_silence.py"
    "tests/hermes_cli/test_doctor.py"
    "tests/hermes_cli/test_skills_config.py"
    "tests/hermes_cli/test_tools_config.py"
    "website/docs/reference/environment-variables.md"
    "website/docs/user-guide/configuration.md"
    "website/docs/user-guide/messaging/feishu.md"
    "plugins/model-providers/vertex/__init__.py"
    "tests/hermes_cli/test_vertex_provider.py"
    "agent/vertex_adapter.py"
    "hermes_cli/auth.py"
    "hermes_cli/runtime_provider.py"
    "agent/auxiliary_client.py"
    "agent/image_routing.py"
    "tests/agent/test_image_routing.py"
    "tests/gateway/test_image_input_routing_runtime.py"
    "agent/replay_cleanup.py"
    "tests/agent/test_replay_cleanup.py"
    "tests/gateway/test_stale_confirmation_expiry.py"
    "native/fts5_cjk/build.sh"
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

# Return 0 only when a replay bundle contains every PATCHED_FILES path exactly
# once and no unregistered path. All current managed paths are Git-safe names
# without quoting; a future path that needs Git's quoted diff header must extend
# this parser before it can enter the registry.
_bundle_matches_patched_files() {
    local _bundle="$1"
    local _f
    local _header_count
    [[ -f "${_bundle}" ]] || return 1
    _header_count=$(grep -c '^diff --git a/' "${_bundle}" 2>/dev/null || true)
    [[ "${_header_count}" -eq "${#PATCHED_FILES[@]}" ]] || return 1
    for _f in "${PATCHED_FILES[@]}"; do
        [[ "$(grep -Fxc -- "diff --git a/${_f} b/${_f}" "${_bundle}" 2>/dev/null || true)" -eq 1 ]] || return 1
    done
}

# Restore only replay-managed paths to HEAD. Run path-by-path so one file that
# upstream deleted cannot prevent the remaining conflict/index state from being
# cleaned up. A managed file absent from HEAD can only have been created by the
# replay attempt, so remove that exact path from both index and worktree.
_restore_patched_files_to_head() {
    local _restore_rc=0
    local _f
    for _f in "$@"; do
        if git cat-file -e "HEAD:${_f}" 2>/dev/null; then
            git restore --source=HEAD --staged --worktree -- "${_f}" 2>/dev/null || _restore_rc=1
        else
            # Delete only a path that the failed apply actually placed in the
            # index. Leave an unrelated untracked file untouched and fail
            # closed so the user can recover it explicitly.
            if git ls-files --error-unmatch -- "${_f}" >/dev/null 2>&1; then
                git rm -f --cached --ignore-unmatch -- "${_f}" >/dev/null 2>&1 || _restore_rc=1
                rm -f -- "${_f}" || _restore_rc=1
            elif [[ -e "${_f}" || -L "${_f}" ]]; then
                _restore_rc=1
            fi
        fi
    done
    return "${_restore_rc}"
}

# PATCH-UPDATE-GIT-FETCH-RETRY + PATCH-UPDATE-TRANSACTION-PIN: acquire exactly
# one official branch snapshot. Failed transport attempts may retry, but as soon
# as a valid changed tracking ref exists it is pinned and no further fetch is
# allowed in this transaction.
_acquire_upstream_target_with_retry() {
    local _fetch_log="$1"
    local _max_attempts=3
    local _attempt=1
    local _fetch_rc _origin

    while true; do
        : >"${_fetch_log}"
        set +e
        git -C "${HERMES_AGENT}" fetch --force origin \
            "main:${TRANSACTION_TARGET_REF}" >"${_fetch_log}" 2>&1
        _fetch_rc=$?
        set -e

        _origin=$(git -C "${HERMES_AGENT}" rev-parse "${TRANSACTION_TARGET_REF}" 2>/dev/null || true)
        # The dedicated ref is deleted before a new transaction starts, so any
        # valid value here was established by this exact fetch. Some transports
        # can return non-zero after updating refs; pin the immutable result
        # instead of performing another network attempt.
        if _valid_git_sha "${_origin}"; then
            _TX_TARGET_SHA="${_origin}"
            _TX_PHASE="pinned"
            _write_transaction
            cat "${_fetch_log}"
            note "Acquired and pinned official main at ${_TX_TARGET_SHA}"
            return 0
        fi

        # Retry only GitHub transport failures. Auth/permission errors are
        # deterministic and must fail immediately; generic connection errors
        # only count when the same line names github.com (this is a raw
        # scoped `git fetch`, so upstream-CLI error strings never appear).
        if ((_attempt < _max_attempts)) &&
            ! grep -qiE \
                'Authentication failed|could not read Username|Invalid username or password|Permission denied \(publickey\)|returned error: 40[137]' \
                "${_fetch_log}" &&
            grep -qiE \
                'Failed to connect to github\.com|Could not resolve host: github\.com|github\.com.*(SSL_ERROR_SYSCALL|tls handshake eof|Connection timed out|Connection reset by peer|Operation timed out|Recv failure|Send failure|Empty reply from server|Couldn.t connect to server)|(SSL_ERROR_SYSCALL|tls handshake eof|Connection timed out|Connection reset by peer).*github\.com' \
                "${_fetch_log}"; then
            note "Transient GitHub fetch failure (attempt ${_attempt}/${_max_attempts}) — retrying"
            _attempt=$((_attempt + 1))
            continue
        fi

        cat "${_fetch_log}"
        return "${_fetch_rc:-1}"
    done
}

_create_pinned_git_wrapper() {
    local _path="$1"
    # Single-quoted lines are the generated script body; expansion is meant to
    # happen when that wrapper runs, not while this parent writes it.
    # shellcheck disable=SC2016
    printf '%s\n' \
        '#!/usr/bin/env bash' \
        'set -euo pipefail' \
        'case "${1:-}" in' \
        '    fetch)' \
        '        if [[ "$#" -eq 3 && "${2:-}" == "origin" && "${3:-}" == "main" ]]; then' \
        '            printf "pinned git: skipped network fetch origin main\\n" >&2' \
        '            exit 0' \
        '        fi' \
        '        printf "pinned git: blocked unexpected fetch: %s\\n" "$*" >&2' \
        '        exit 97' \
        '        ;;' \
        '    pull|ls-remote|clone)' \
        '        printf "pinned git: blocked network-capable command: %s\\n" "$*" >&2' \
        '        exit 97' \
        '        ;;' \
        'esac' \
        'args=()' \
        'for arg in "$@"; do' \
        '    args+=("${arg//origin\/main/${HERMES_UPDATE_PINNED_SHA}}")' \
        'done' \
        'exec "${HERMES_UPDATE_REAL_GIT}" "${args[@]}"' >"${_path}"
    chmod 700 "${_path}"
}

# Run the official updater while pinning every origin/main read to TARGET_SHA
# and turning its mandatory `git fetch origin main` into a successful no-op.
# The updater still owns its normal merge, dependency, migration, skills and
# restart behavior; it simply cannot contact or observe a newer official tip.
_run_pinned_hermes_update() {
    local _update_log="$1"
    local _wrapper_dir _real_git
    _real_git=$(command -v git)
    _wrapper_dir=$(mktemp -d -t hermes-pinned-git.XXXXXX)
    _create_pinned_git_wrapper "${_wrapper_dir}/git"

    # Bash nounset treats an explicitly empty array as unset during an
    # ``[@]`` expansion. Reconcile on npm <12 has no policy entries, so use a
    # nounset-safe expansion rather than aborting before the pinned updater runs.
    set +e
    PATH="${_wrapper_dir}:${PATH}" \
        HERMES_UPDATE_REAL_GIT="${_real_git}" \
        HERMES_UPDATE_PINNED_SHA="${_TX_TARGET_SHA}" \
        env "${_NPM_POLICY_ENV[@]+"${_NPM_POLICY_ENV[@]}"}" hermes update >"${_update_log}" 2>&1
    UPDATE_RC=$?
    set -e
    rm -f -- "${_wrapper_dir}/git"
    rmdir "${_wrapper_dir}" 2>/dev/null || true
    cat "${_update_log}"

    local _head
    _head=$(git -C "${HERMES_AGENT}" rev-parse HEAD 2>/dev/null || true)
    if grep -qF 'pinned git: blocked' "${_update_log}" 2>/dev/null; then
        UPDATE_RC=1
    fi
    if [[ ${UPDATE_RC} -eq 0 && "${_head}" == "${_TX_TARGET_SHA}" ]]; then
        _TX_PHASE="upstream_applied"
        if [[ "${_head}" != "${_TX_OLD_SHA}" ]] ||
            grep -qE 'Restarted ai\.hermes\.gateway|Restart required' "${_update_log}" 2>/dev/null; then
            _TX_RUNTIME_DIRTY="1"
        fi
        _write_transaction
        return 0
    fi
    if [[ ${UPDATE_RC} -eq 0 ]]; then
        printf 'Pinned updater ended at %s, expected %s\n' "${_head:-none}" "${_TX_TARGET_SHA}" >>"${_update_log}"
        UPDATE_RC=1
    fi
    if [[ ${UPDATE_RC} -ne 0 ]]; then
        _TX_RUNTIME_DIRTY="1"
        _write_transaction
    fi
    return "${UPDATE_RC}"
}

# PATCH-UPDATE-TRANSACTION-PIN: one user-requested update owns one immutable
# upstream target. The state file is deliberately data-only (never sourced),
# mode 0600, and atomically replaced. A failed/interrupted run keeps it; only a
# complete exit 0 removes it. This lets a stateless AI resume without fetching a
# newer origin/main and turning a repair loop into an endless moving target.
_TX_VERSION="1"
_TX_PHASE=""
_TX_OLD_SHA=""
_TX_ORIGIN_BEFORE=""
_TX_TARGET_SHA=""
_TX_STARTED_AT=""
_TX_RUNTIME_DIRTY="0"
_TRANSACTION_INITIALIZED=false
_TRANSACTION_LOCK_HELD=false

_valid_git_sha() {
    [[ "${1:-}" =~ ^[0-9a-f]{40,64}$ ]]
}

_transaction_value() {
    local _key="$1"
    local _file="$2"
    sed -n "s/^${_key}=//p" "${_file}" 2>/dev/null | head -n 1
}

_load_transaction() {
    local _version _phase _old_sha _origin_before _target_sha _started_at _runtime_dirty
    [[ -f "${TRANSACTION_FILE}" && ! -L "${TRANSACTION_FILE}" ]] || return 1
    [[ "$(stat -f '%Lp' "${TRANSACTION_FILE}" 2>/dev/null || stat -c '%a' "${TRANSACTION_FILE}" 2>/dev/null)" == "600" ]] || return 1
    [[ "$(wc -l <"${TRANSACTION_FILE}" | tr -d '[:space:]')" == "7" ]] || return 1
    ! grep -qEv '^(version|phase|old_sha|origin_before|target_sha|started_at|runtime_dirty)=' "${TRANSACTION_FILE}" || return 1
    local _key
    for _key in version phase old_sha origin_before target_sha started_at runtime_dirty; do
        [[ "$(grep -c "^${_key}=" "${TRANSACTION_FILE}" 2>/dev/null || true)" == "1" ]] || return 1
    done

    _version=$(_transaction_value version "${TRANSACTION_FILE}")
    _phase=$(_transaction_value phase "${TRANSACTION_FILE}")
    _old_sha=$(_transaction_value old_sha "${TRANSACTION_FILE}")
    _origin_before=$(_transaction_value origin_before "${TRANSACTION_FILE}")
    _target_sha=$(_transaction_value target_sha "${TRANSACTION_FILE}")
    _started_at=$(_transaction_value started_at "${TRANSACTION_FILE}")
    _runtime_dirty=$(_transaction_value runtime_dirty "${TRANSACTION_FILE}")

    [[ "${_version}" == "1" ]] || return 1
    [[ "${_phase}" == "acquiring" || "${_phase}" == "pinned" || "${_phase}" == "upstream_applied" ]] || return 1
    _valid_git_sha "${_old_sha}" || return 1
    _valid_git_sha "${_origin_before}" || return 1
    [[ -z "${_target_sha}" ]] || _valid_git_sha "${_target_sha}" || return 1
    [[ "${_started_at}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || return 1
    [[ "${_runtime_dirty}" == "0" || "${_runtime_dirty}" == "1" ]] || return 1

    _TX_VERSION="${_version}"
    _TX_PHASE="${_phase}"
    _TX_OLD_SHA="${_old_sha}"
    _TX_ORIGIN_BEFORE="${_origin_before}"
    _TX_TARGET_SHA="${_target_sha}"
    _TX_STARTED_AT="${_started_at}"
    _TX_RUNTIME_DIRTY="${_runtime_dirty}"
    return 0
}

_write_transaction() {
    local _tmp="${TRANSACTION_FILE}.tmp.$$"
    (
        umask 077
        printf '%s\n' \
            "version=${_TX_VERSION}" \
            "phase=${_TX_PHASE}" \
            "old_sha=${_TX_OLD_SHA}" \
            "origin_before=${_TX_ORIGIN_BEFORE}" \
            "target_sha=${_TX_TARGET_SHA}" \
            "started_at=${_TX_STARTED_AT}" \
            "runtime_dirty=${_TX_RUNTIME_DIRTY}" >"${_tmp}" &&
            mv -f "${_tmp}" "${TRANSACTION_FILE}"
    )
}

_print_transaction_status() {
    if [[ ! -e "${TRANSACTION_FILE}" && ! -L "${TRANSACTION_FILE}" ]]; then
        printf 'none\n'
        return 0
    fi
    if ! _load_transaction; then
        printf 'invalid: %s\n' "${TRANSACTION_FILE}" >&2
        return 1
    fi
    printf 'phase=%s\nold_sha=%s\ntarget_sha=%s\nstarted_at=%s\nruntime_dirty=%s\n' \
        "${_TX_PHASE}" "${_TX_OLD_SHA}" "${_TX_TARGET_SHA:-pending}" \
        "${_TX_STARTED_AT}" "${_TX_RUNTIME_DIRTY}"
}

_local_version() {
    local _init_file="${HERMES_AGENT}/hermes_cli/__init__.py"
    local _version _release_date
    _version=$(sed -nE 's/^__version__[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "${_init_file}" 2>/dev/null | head -n 1)
    _release_date=$(sed -nE 's/^__release_date__[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "${_init_file}" 2>/dev/null | head -n 1)
    if [[ -n "${_version}" ]]; then
        printf 'Hermes Agent v%s%s\n' "${_version}" "${_release_date:+ (${_release_date})}"
    else
        printf 'unknown\n'
    fi
}

_self_test_transaction() {
    local _real_file="${TRANSACTION_FILE}"
    local _real_agent="${HERMES_AGENT}"
    local _real_target_ref="${TRANSACTION_TARGET_REF}"
    local _test_file _wrapper_dir _fake_log _git_root _first_sha _second_sha
    _test_file=$(mktemp -t hermes-update-transaction-test.XXXXXX)
    rm -f -- "${_test_file}"
    TRANSACTION_FILE="${_test_file}"
    _TX_PHASE="upstream_applied"
    _TX_OLD_SHA="1111111111111111111111111111111111111111"
    _TX_ORIGIN_BEFORE="2222222222222222222222222222222222222222"
    _TX_TARGET_SHA="3333333333333333333333333333333333333333"
    _TX_STARTED_AT="2026-01-02T03:04:05Z"
    _TX_RUNTIME_DIRTY="1"
    _write_transaction

    _TX_PHASE=""
    _TX_OLD_SHA=""
    _TX_ORIGIN_BEFORE=""
    _TX_TARGET_SHA=""
    _TX_STARTED_AT=""
    _TX_RUNTIME_DIRTY="0"
    _load_transaction
    [[ "${_TX_PHASE}" == "upstream_applied" ]]
    [[ "${_TX_OLD_SHA}" == "1111111111111111111111111111111111111111" ]]
    [[ "${_TX_ORIGIN_BEFORE}" == "2222222222222222222222222222222222222222" ]]
    [[ "${_TX_TARGET_SHA}" == "3333333333333333333333333333333333333333" ]]
    [[ "${_TX_STARTED_AT}" == "2026-01-02T03:04:05Z" ]]
    [[ "${_TX_RUNTIME_DIRTY}" == "1" ]]
    [[ "$(stat -f '%Lp' "${TRANSACTION_FILE}" 2>/dev/null || stat -c '%a' "${TRANSACTION_FILE}")" == "600" ]]

    # Fail-closed negatives: a symlinked state file and a tampered file with
    # an extra line must both be rejected by _load_transaction.
    local _decoy_file
    _decoy_file=$(mktemp -t hermes-update-transaction-decoy.XXXXXX)
    mv -- "${TRANSACTION_FILE}" "${_decoy_file}"
    ln -s "${_decoy_file}" "${TRANSACTION_FILE}"
    if _load_transaction 2>/dev/null; then
        printf 'self-test: symlinked transaction state was not rejected\n' >&2
        return 1
    fi
    rm -f -- "${TRANSACTION_FILE}"
    mv -- "${_decoy_file}" "${TRANSACTION_FILE}"
    chmod 600 "${TRANSACTION_FILE}"
    printf 'extra_key=tampered\n' >>"${TRANSACTION_FILE}"
    if _load_transaction 2>/dev/null; then
        printf 'self-test: tampered transaction state (extra line) was not rejected\n' >&2
        return 1
    fi
    # Restore a valid state file for the remaining assertions/cleanup.
    _TX_PHASE="upstream_applied"
    _TX_OLD_SHA="1111111111111111111111111111111111111111"
    _TX_ORIGIN_BEFORE="2222222222222222222222222222222222222222"
    _TX_TARGET_SHA="3333333333333333333333333333333333333333"
    _TX_STARTED_AT="2026-01-02T03:04:05Z"
    _TX_RUNTIME_DIRTY="1"
    _write_transaction

    _wrapper_dir=$(mktemp -d -t hermes-pinned-git-test.XXXXXX)
    _fake_log="${_wrapper_dir}/calls"
    # shellcheck disable=SC2016
    printf '%s\n' \
        '#!/usr/bin/env bash' \
        'printf "%s\\n" "$*" >>"${HERMES_UPDATE_FAKE_LOG}"' \
        'exit 0' >"${_wrapper_dir}/real-git"
    chmod 700 "${_wrapper_dir}/real-git"
    _create_pinned_git_wrapper "${_wrapper_dir}/git"
    HERMES_UPDATE_REAL_GIT="${_wrapper_dir}/real-git" \
        HERMES_UPDATE_PINNED_SHA="3333333333333333333333333333333333333333" \
        HERMES_UPDATE_FAKE_LOG="${_fake_log}" \
        "${_wrapper_dir}/git" fetch origin main 2>/dev/null
    [[ ! -e "${_fake_log}" ]]
    HERMES_UPDATE_REAL_GIT="${_wrapper_dir}/real-git" \
        HERMES_UPDATE_PINNED_SHA="3333333333333333333333333333333333333333" \
        HERMES_UPDATE_FAKE_LOG="${_fake_log}" \
        "${_wrapper_dir}/git" rev-list HEAD..origin/main --count
    grep -qF 'rev-list HEAD..3333333333333333333333333333333333333333 --count' "${_fake_log}"

    rm -f -- "${TRANSACTION_FILE}"
    rm -f -- "${_wrapper_dir}/git" "${_wrapper_dir}/real-git" "${_fake_log}"
    rmdir "${_wrapper_dir}" 2>/dev/null || true

    # Exercise the real scoped-fetch transaction against a local bare remote.
    # A second remote commit appears after acquisition; resume must keep the
    # first immutable SHA without refreshing any remote-tracking ref.
    _git_root=$(mktemp -d -t hermes-update-git-test.XXXXXX)
    git init -q -b main "${_git_root}/seed"
    git -C "${_git_root}/seed" config user.name hermes-update-test
    git -C "${_git_root}/seed" config user.email hermes-update-test@example.invalid
    git -C "${_git_root}/seed" commit -q --allow-empty -m initial
    git clone -q --bare "${_git_root}/seed" "${_git_root}/official.git"
    git clone -q -b main "${_git_root}/official.git" "${_git_root}/work"

    HERMES_AGENT="${_git_root}/work"
    TRANSACTION_FILE="${_git_root}/transaction"
    TRANSACTION_TARGET_REF="refs/hermes-update/test-target"
    _REQUESTED_MODE="update"
    _TRANSACTION_INITIALIZED=false
    _ACQUIRE_UPSTREAM=false
    _RUN_PINNED_UPDATER=false
    _TX_PHASE=""
    _TX_OLD_SHA=""
    _TX_ORIGIN_BEFORE=""
    _TX_TARGET_SHA=""
    _TX_STARTED_AT="2026-01-02T03:04:05Z"
    _TX_RUNTIME_DIRTY="0"
    _TX_PHASE="acquiring"
    _TX_OLD_SHA=$(git -C "${HERMES_AGENT}" rev-parse HEAD)
    _TX_ORIGIN_BEFORE=$(git -C "${HERMES_AGENT}" rev-parse refs/remotes/origin/main)
    _write_transaction
    _acquire_upstream_target_with_retry "${_git_root}/fetch.log" >/dev/null
    _first_sha="${_TX_TARGET_SHA}"

    git -C "${_git_root}/seed" commit -q --allow-empty -m later
    git -C "${_git_root}/official.git" fetch -q "${_git_root}/seed" \
        "+main:refs/heads/main"
    _second_sha=$(git -C "${_git_root}/seed" rev-parse HEAD)
    [[ "${_first_sha}" != "${_second_sha}" ]]

    _TX_TARGET_SHA=""
    _load_transaction
    [[ "${_TX_TARGET_SHA}" == "${_first_sha}" ]]
    [[ "$(git -C "${HERMES_AGENT}" rev-parse "${TRANSACTION_TARGET_REF}")" == "${_first_sha}" ]]

    rm -f -- "${TRANSACTION_FILE}" "${_git_root}/fetch.log"
    git -C "${HERMES_AGENT}" update-ref -d "${TRANSACTION_TARGET_REF}"
    rm -rf -- "${_git_root}/official.git" "${_git_root}/seed" "${_git_root}/work"
    rmdir "${_git_root}" 2>/dev/null || true

    HERMES_AGENT="${_real_agent}"
    TRANSACTION_FILE="${_real_file}"
    TRANSACTION_TARGET_REF="${_real_target_ref}"
    printf 'transaction-state self-test OK\n'
}

_acquire_transaction_lock() {
    local _holder=""
    if mkdir "${TRANSACTION_LOCK_DIR}" 2>/dev/null; then
        printf '%s\n' "$$" >"${TRANSACTION_LOCK_DIR}/pid"
        _TRANSACTION_LOCK_HELD=true
        return 0
    fi

    if [[ -f "${TRANSACTION_LOCK_DIR}/pid" ]]; then
        _holder=$(sed -nE 's/^([0-9]+)$/\1/p' "${TRANSACTION_LOCK_DIR}/pid" | head -n 1)
    fi
    if [[ -n "${_holder}" ]] && kill -0 "${_holder}" 2>/dev/null; then
        fail "Another hermes-update workflow is active (PID ${_holder})"
        return 1
    fi

    # Recover only this exact stale lock; never remove a broad or unresolved
    # path. rmdir also fails closed if unexpected files appeared inside it.
    rm -f -- "${TRANSACTION_LOCK_DIR}/pid" 2>/dev/null || true
    if ! rmdir "${TRANSACTION_LOCK_DIR}" 2>/dev/null ||
        ! mkdir "${TRANSACTION_LOCK_DIR}" 2>/dev/null; then
        fail "Could not acquire update transaction lock: ${TRANSACTION_LOCK_DIR}"
        return 1
    fi
    printf '%s\n' "$$" >"${TRANSACTION_LOCK_DIR}/pid"
    _TRANSACTION_LOCK_HELD=true
}

# Invoked indirectly from the EXIT handler.
# shellcheck disable=SC2329
_release_transaction_lock() {
    $_TRANSACTION_LOCK_HELD || return 0
    rm -f -- "${TRANSACTION_LOCK_DIR}/pid" 2>/dev/null || true
    rmdir "${TRANSACTION_LOCK_DIR}" 2>/dev/null || true
    _TRANSACTION_LOCK_HELD=false
}

# Print the active gateway PID, accepting both the older JSON-like status
# output and the current "Gateway is supervised by <service> (PID NNN)".
gw_pid() {
    hermes gateway status 2>&1 | sed -nE \
        -e 's/.*"PID"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' \
        -e 's/.*PID[[:space:]]+([0-9]+).*/\1/p' | head -n 1
}

# Returns 0 if the launchd gateway service has an active PID.
gw_running() {
    [[ -n "$(gw_pid)" ]]
}

# Allow a planned restart to use the complete configured drain budget, plus a
# small supervisor-respawn margin. Fall back to the upstream default budget if
# the freshly-updated runtime cannot import its config helper yet.
# Forward-compat (upstream db3f7e4eb, post-26e0b1c): newer runtimes defer the
# in-band restart until active turns finish and expose the combined wait via
# resolve_restart_exit_wait_budget() (drain + restart_after_turn_timeout +
# headroom). Prefer that native budget when present so this wrapper never
# times out while the gateway is still patiently draining; otherwise keep the
# drain-only formula that matches the current runtime.
gw_restart_wait_seconds() {
    local _python="${HERMES_AGENT}/venv/bin/python"
    # Last-resort fallback when the venv interpreter is unavailable: local
    # config pins agent.restart_drain_timeout=900, +30s supervisor margin.
    # Keep this in sync with config.yaml — a too-small value here would time
    # out while the gateway is still legitimately draining.
    local _fallback=930
    if [[ ! -x "${_python}" ]]; then
        echo "${_fallback}"
        return
    fi
    "${_python}" -c '
try:
    from hermes_cli.gateway import _get_restart_exit_wait_budget
    budget = float(_get_restart_exit_wait_budget())
except Exception:
    from hermes_cli.gateway import _get_restart_drain_timeout
    budget = float(_get_restart_drain_timeout())
print(int(max(30.0, budget + 30.0)))
' 2>/dev/null || echo "${_fallback}"
}

# This script is executable, not a shell function library. Give the playbook
# and external supervisors side-effect-free inspection entry points; sourcing
# the whole script would otherwise start a reconciliation workflow.
case "${1:-}" in
"" | --reconcile)
    _REQUESTED_MODE="reconcile"
    ;;
--update)
    _REQUESTED_MODE="update"
    ;;
--transaction-status)
    _print_transaction_status
    exit $?
    ;;
--print-restart-wait-seconds)
    gw_restart_wait_seconds
    exit 0
    ;;
--print-patched-files)
    printf '%s\n' "${PATCHED_FILES[@]}"
    exit 0
    ;;
--print-patched-tests)
    for _f in "${PATCHED_FILES[@]}"; do
        [[ "${_f}" == tests/* ]] && printf '%s\n' "${_f}"
    done
    exit 0
    ;;
--self-test-transaction)
    _self_test_transaction
    exit 0
    ;;
*)
    printf 'Usage: %s [--update|--reconcile|--transaction-status|--print-restart-wait-seconds|--print-patched-files|--print-patched-tests|--self-test-transaction]\n' "$0" >&2
    exit 2
    ;;
esac

# Personal display contract: the owner DM may show each newly-started tool as
# a separate progress card, while Feishu groups expose no tool/interim/thinking
# UI. Both scopes keep final assistant delivery non-streaming and draft-free.
_verify_feishu_display_policy() {
    "${HERMES_AGENT}/venv/bin/python" -c '
import sys, yaml
with open(sys.argv[1], encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}
platforms = ((config.get("display") or {}).get("platforms") or {})
dm = platforms.get("feishu") or {}
group = platforms.get("feishu_group") or {}
disabled = ("streaming", "interim_assistant_messages", "long_running_notifications", "busy_ack_detail", "thinking_progress")
assert dm.get("tool_progress") == "new"
assert all(dm.get(key) is False for key in disabled)
assert group.get("tool_progress") is False
assert all(group.get(key) is False for key in disabled)
' "${HERMES_HOME}/config.yaml" >/dev/null 2>&1
}

_prepare_transaction() {
    local _head _origin _target_ref
    _head=$(git -C "${HERMES_AGENT}" rev-parse HEAD 2>/dev/null) || return 1
    _origin=$(git -C "${HERMES_AGENT}" rev-parse refs/remotes/origin/main 2>/dev/null) || return 1
    _target_ref=$(git -C "${HERMES_AGENT}" rev-parse "${TRANSACTION_TARGET_REF}" 2>/dev/null || true)

    if [[ -e "${TRANSACTION_FILE}" || -L "${TRANSACTION_FILE}" ]]; then
        if ! _load_transaction; then
            fail "Invalid update transaction state: ${TRANSACTION_FILE}"
            printf '  Inspect or move this file aside; it is never sourced automatically.\n'
            return 1
        fi
        _TRANSACTION_INITIALIZED=true

        # If the previous process died after the wrapper fetch updated its
        # dedicated ref but before state publication, reconstruct the target.
        if [[ -z "${_TX_TARGET_SHA}" ]]; then
            if _valid_git_sha "${_target_ref}"; then
                _TX_TARGET_SHA="${_target_ref}"
            elif [[ "${_head}" != "${_TX_OLD_SHA}" ]]; then
                _TX_TARGET_SHA="${_head}"
            fi
            if [[ -n "${_TX_TARGET_SHA}" ]]; then
                _TX_PHASE="pinned"
                _write_transaction || return 1
            fi
        fi

        if [[ -n "${_TX_TARGET_SHA}" ]]; then
            _ACQUIRE_UPSTREAM=false
            if [[ "${_TX_PHASE}" == "pinned" ]]; then
                _RUN_PINNED_UPDATER=true
            else
                _RUN_PINNED_UPDATER=false
            fi
            note "Resuming pinned update transaction at ${_TX_TARGET_SHA:0:12} (no fetch/pull)"
            if [[ "${_REQUESTED_MODE}" == "update" ]]; then
                note "--update did not open a new transaction because an unfinished target already exists"
            fi
        elif [[ "${_REQUESTED_MODE}" == "update" ]]; then
            # No fetch ever established a target. Retrying acquisition is safe:
            # it cannot move a previously pinned transaction because none exists.
            _ACQUIRE_UPSTREAM=true
            _RUN_PINNED_UPDATER=true
            note "Resuming target acquisition; no upstream SHA was established by the failed attempt"
        else
            fail "The unfinished transaction has no pinned target yet"
            printf '  Resume once with --update so the initial acquisition can finish; later runs use --reconcile.\n'
            return 1
        fi
        return 0
    fi

    # A target ref has meaning only together with its transaction state. Clear
    # any orphan before opening a genuinely new local or upstream transaction.
    git -C "${HERMES_AGENT}" update-ref -d "${TRANSACTION_TARGET_REF}" 2>/dev/null || return 1
    _TX_PHASE="upstream_applied"
    _TX_OLD_SHA="${_head}"
    _TX_ORIGIN_BEFORE="${_origin}"
    _TX_TARGET_SHA="${_head}"
    _TX_STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    _TX_RUNTIME_DIRTY="0"

    if [[ "${_REQUESTED_MODE}" == "update" ]]; then
        _TX_PHASE="acquiring"
        _TX_TARGET_SHA=""
        _ACQUIRE_UPSTREAM=true
        _RUN_PINNED_UPDATER=true
        note "Starting one upstream acquisition from HEAD ${_head:0:12}"
    else
        _ACQUIRE_UPSTREAM=false
        _RUN_PINNED_UPDATER=false
        note "Starting local reconciliation pinned to HEAD ${_head:0:12} (no fetch/pull)"
    fi

    _write_transaction || return 1
    _TRANSACTION_INITIALIZED=true
}

_mark_runtime_dirty() {
    if [[ "${_TX_RUNTIME_DIRTY}" != "1" ]]; then
        _TX_RUNTIME_DIRTY="1"
        _write_transaction
    fi
}

_reconcile_pinned_head() {
    local _head
    if ! _valid_git_sha "${_TX_TARGET_SHA}" ||
        ! git -C "${HERMES_AGENT}" cat-file -e "${_TX_TARGET_SHA}^{commit}" 2>/dev/null; then
        fail "Pinned target is missing or unavailable locally: ${_TX_TARGET_SHA:-none}"
        return 1
    fi

    _head=$(git -C "${HERMES_AGENT}" rev-parse HEAD 2>/dev/null) || return 1
    if [[ "${_head}" == "${_TX_TARGET_SHA}" ]]; then
        ok "Pinned upstream target unchanged: ${_TX_TARGET_SHA:0:12}"
        return 0
    fi

    if ! git -C "${HERMES_AGENT}" merge-base --is-ancestor "${_head}" "${_TX_TARGET_SHA}"; then
        fail "HEAD ${_head:0:12} cannot fast-forward to pinned target ${_TX_TARGET_SHA:0:12}"
        return 1
    fi
    if ! git -C "${HERMES_AGENT}" merge --ff-only "${_TX_TARGET_SHA}"; then
        fail "Could not fast-forward locally to pinned target ${_TX_TARGET_SHA:0:12}"
        return 1
    fi

    _PINNED_HEAD_ADVANCED=true
    _mark_runtime_dirty
    ok "Fast-forwarded locally to pinned target ${_TX_TARGET_SHA:0:12} (no fetch/pull)"
}

# ── Trap: restore patches if script dies after reverting them ────────────────
# Set to true in step 2 after reverting; cleared only once step 8a has made its
# apply decision (applied, or deliberately rolled back). This keeps the crash-
# recovery window open across steps 3–7, where the tree is intentionally bare:
# an interruption there would otherwise leave the runtime unpatched with no
# automatic re-apply on the next manual inspection.
_PATCHES_REVERTED=false
_NPM_POLICY_FILE=""
_ACQUIRE_UPSTREAM=false
_RUN_PINNED_UPDATER=false
_PINNED_HEAD_ADVANCED=false

# Invoked indirectly by `trap ... EXIT`; ShellCheck cannot see that edge.
# shellcheck disable=SC2329
_trap_restore_patches() {
    if [[ -n "${_NPM_POLICY_FILE:-}" ]]; then
        rm -f -- "${_NPM_POLICY_FILE}" 2>/dev/null || true
    fi
    if $_PATCHES_REVERTED && [[ -f "${PATCH_FILE}" ]]; then
        printf '\n%s⚠%s  Script exited early — attempting to restore local patches...\n' "${YLW}" "${NC}"
        local _trap_apply_ok=false
        if cd "${HERMES_AGENT}"; then
            if git apply "${PATCH_FILE}" 2>/dev/null; then
                _trap_apply_ok=true
            elif git apply --3way "${PATCH_FILE}" 2>/dev/null &&
                git restore --staged -- "${PATCHED_FILES[@]}" 2>/dev/null; then
                _trap_apply_ok=true
            fi

            if $_trap_apply_ok && ! _has_conflict_markers "${PATCHED_FILES[@]}" &&
                git diff --cached --quiet; then
                printf '  %s✓%s Local patches restored after early exit.\n' "${GRN}" "${NC}"
            else
                # A failed 3-way attempt may leave unmerged index entries and
                # conflict markers. Return every replay-managed path to a clean
                # upstream state so the next AI sees a deterministic takeover
                # point and can re-apply the preserved bundle explicitly.
                _restore_patched_files_to_head "${PATCHED_FILES[@]}" >/dev/null 2>&1 || true
                printf '  %s✗%s Could not auto-restore cleanly. Run: cd %s && git apply --3way %s\n' \
                    "${RED}" "${NC}" "${HERMES_AGENT}" "${PATCH_FILE}"
            fi
        else
            printf '  %s✗%s Could not enter %s; replay bundle remains at %s\n' \
                "${RED}" "${NC}" "${HERMES_AGENT}" "${PATCH_FILE}"
        fi
    fi
}

# Invoked indirectly by `trap ... EXIT`.
# shellcheck disable=SC2329
_on_exit() {
    local _rc=$?
    trap - EXIT
    set +e

    if [[ "${_rc}" -eq 0 && "${_PATCHES_REVERTED}" == "true" ]]; then
        _rc=1
    fi
    _trap_restore_patches

    if $_TRANSACTION_INITIALIZED; then
        if [[ "${_rc}" -eq 0 ]]; then
            rm -f -- "${TRANSACTION_FILE}"
            git -C "${HERMES_AGENT}" update-ref -d "${TRANSACTION_TARGET_REF}" 2>/dev/null || true
            printf '  %s✓%s Update transaction complete — removed pinned state.\n' "${GRN}" "${NC}"
        else
            # Best-effort crash recovery: if acquisition moved a local ref before
            # the normal pin step ran, preserve that SHA for the next process.
            if [[ -z "${_TX_TARGET_SHA}" ]]; then
                local _exit_head _exit_target_ref
                _exit_head=$(git -C "${HERMES_AGENT}" rev-parse HEAD 2>/dev/null || true)
                _exit_target_ref=$(git -C "${HERMES_AGENT}" rev-parse "${TRANSACTION_TARGET_REF}" 2>/dev/null || true)
                if _valid_git_sha "${_exit_target_ref}"; then
                    _TX_TARGET_SHA="${_exit_target_ref}"
                elif _valid_git_sha "${_exit_head}" && [[ "${_exit_head}" != "${_TX_OLD_SHA}" ]]; then
                    _TX_TARGET_SHA="${_exit_head}"
                fi
                if [[ -n "${_TX_TARGET_SHA}" ]]; then
                    _TX_PHASE="pinned"
                    _TX_RUNTIME_DIRTY="1"
                fi
            fi
            _write_transaction >/dev/null 2>&1 || true
            printf '  %s→%s Update transaction retained at %s (target %s).\n' \
                "${BOLD}" "${NC}" "${TRANSACTION_FILE}" "${_TX_TARGET_SHA:-pending}"
        fi
    fi
    _release_transaction_lock
    exit "${_rc}"
}
trap _on_exit EXIT

if ! _acquire_transaction_lock; then
    exit 1
fi

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

# PATCH-UPDATE-GATE-EXIT-STATUS: replay assumes HEAD is the complete index
# baseline. Never auto-unstage user work; fail closed and let the next AI
# classify it before the update mutates either repository.
if ! git -C "${HERMES_AGENT}" diff --cached --quiet; then
    fail "hermes-agent index has staged changes — refusing to overwrite replay state"
    printf '  Unstage intentionally, then retry: git -C %s restore --staged -- <paths>\n' "${HERMES_AGENT}"
    exit 1
fi

if ! _prepare_transaction; then
    exit 1
fi

# Network checks exist only on the one explicit acquisition path. Reconcile
# mode must be mechanically incapable of contacting origin, including through
# the otherwise convenient `hermes --version` update-check side effect.
if $_ACQUIRE_UPSTREAM &&
    ! curl -sf --connect-timeout 5 --max-time 8 https://github.com >/dev/null 2>&1; then
    note "Initial github.com probe unavailable — the update fetch will retry transient network failures"
fi

PRE_VERSION=$(_local_version)
note "Current: ${PRE_VERSION}"

# ── 2. Save & clean local patches ────────────────────────────────────────────
# PATCH-REPLAY-BUNDLE-FULL-INDEX + PATCH-UPDATE-GATE-EXIT-STATUS: save the
# complete local overlay to patches/local-patches.diff, validate it in both
# directions, then revert the files to HEAD so hermes update finds a clean tree
# and skips git stash entirely. A trap restores patches on early exit.
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
    if [[ -f "${PATCH_FILE}" && ${#_CHANGED_PATCH_FILES[@]} -ne ${#PATCHED_FILES[@]} ]]; then
        fail "Partial patch overlay detected (${#_CHANGED_PATCH_FILES[@]}/${#PATCHED_FILES[@]} managed files differ from HEAD)"
        printf '  Managed paths unexpectedly equal to HEAD; canonical bundle was preserved:\n'
        for _f in "${PATCHED_FILES[@]}"; do
            if git --no-pager diff --quiet HEAD -- "${_f}" 2>/dev/null; then
                printf '      - %s\n' "${_f}"
            fi
        done
        printf '  Reconcile absorption/interruption state before rerunning; do not capture a partial overlay.\n'
        exit 1
    fi

    if ! git --no-pager diff --full-index HEAD -- "${_CHANGED_PATCH_FILES[@]}" >"${PATCH_FILE}.tmp"; then
        rm -f -- "${PATCH_FILE}.tmp"
        fail "Could not generate replay bundle; previous canonical bundle was preserved"
        exit 1
    fi
    if ! git diff --cached --quiet 2>/dev/null ||
        ! _bundle_matches_patched_files "${PATCH_FILE}.tmp" ||
        grep -nE '^\+?(<<<<<<<|=======|>>>>>>>)' "${PATCH_FILE}.tmp" >/dev/null 2>&1 ||
        ! git apply --cached --check "${PATCH_FILE}.tmp" 2>/dev/null ||
        ! git apply --check --reverse "${PATCH_FILE}.tmp" 2>/dev/null; then
        rm -f -- "${PATCH_FILE}.tmp"
        fail "Live patch overlay failed replay validation; previous canonical bundle was preserved"
        printf '  Resolve conflict/index drift before rerunning this script.\n'
        exit 1
    fi
    if [[ ! -f "${PATCH_FILE}" ]] || ! cmp -s "${PATCH_FILE}.tmp" "${PATCH_FILE}"; then
        _mark_runtime_dirty
    fi
    mv -f "${PATCH_FILE}.tmp" "${PATCH_FILE}"
    ok "Saved ${#_CHANGED_PATCH_FILES[@]} patched file(s) → patches/local-patches.diff"
    if ! _restore_patched_files_to_head "${_CHANGED_PATCH_FILES[@]}"; then
        fail "Could not restore every patched file to HEAD after saving the replay bundle"
        add_act "Inspect the managed paths and index: cd ${HERMES_AGENT} && git status --short"
        exit 1
    fi
    _PATCHES_REVERTED=true
    ok "Reverted patched files to HEAD (clean tree for upstream/reconcile step)"
    # Warn if OTHER unrelated changes exist — step 3 will auto-clean them.
    _DIRTY=$(git status --porcelain 2>/dev/null)
    if [[ -n "${_DIRTY}" ]]; then
        note "Other uncommitted changes in hermes-agent (will be auto-stashed in step 3):"
        printf '%s\n' "${_DIRTY}" | sed 's/^/      /'
    fi
elif [[ -f "${PATCH_FILE}" ]]; then
    if ! _bundle_matches_patched_files "${PATCH_FILE}" ||
        grep -nE '^\+?(<<<<<<<|=======|>>>>>>>)' "${PATCH_FILE}" >/dev/null 2>&1 ||
        ! git apply --cached --check "${PATCH_FILE}" 2>/dev/null; then
        fail "Bare worktree takeover found an invalid or incomplete canonical replay bundle"
        printf '  Restore/reconcile patches/local-patches.diff before updating upstream.\n'
        exit 1
    fi
    # This is the expected takeover shape after an interrupted save/revert:
    # the worktree is bare but the complete bundle still exists. Keep the EXIT
    # recovery window armed until Step 8a replays it.
    _PATCHES_REVERTED=true
    note "Patches already clean — will re-apply from saved patches/local-patches.diff"
else
    note "No local patches to save — workflow will proceed on a clean tree"
fi

cd - >/dev/null

# ── 3. Acquire once or reconcile pinned target ────────────────────────────────
# --update invokes upstream exactly once for this transaction. Any unfinished
# transaction and every --reconcile pass reuse the persisted SHA without fetch
# or pull. The remaining workflow is identical, so patch replay/gates can be
# repeated until green without chasing a moving origin/main.
# Tree should be clean after step 2 (patches reverted). However, other
# uncommitted changes outside PATCHED_FILES can still trigger hermes update's
# interactive stash prompt. To avoid this, stash unrelated extra changes
# (including untracked files) before invoking hermes update, then restore them
# afterwards. If stash/pop fails, keep the stash for manual recovery rather than
# deleting untracked work.
if $_ACQUIRE_UPSTREAM; then
    step "Acquiring one official upstream snapshot, then applying pinned update"
elif $_RUN_PINNED_UPDATER; then
    step "Resuming official updater at pinned target  [no fetch/pull]"
else
    step "Reconciling pinned upstream target  [no fetch/pull]"
fi
echo ""

cd "${HERMES_AGENT}"
_EXTRA_STASHED=false
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    if git stash push -u -m "hermes-update-extra-$(date +%Y%m%d-%H%M%S)" >/dev/null 2>&1; then
        _EXTRA_STASHED=true
        ok "Stashed extra uncommitted changes (including untracked files)"
    else
        warn "Could not stash extra changes — leaving tree untouched"
        add_warn "hermes-agent has extra uncommitted changes that could not be stashed"
        add_act "Review: cd ${HERMES_AGENT} && git status --short"
        FINAL_RC=1
        cd - >/dev/null
        exit $FINAL_RC
    fi
fi
cd - >/dev/null

# npm 12 blocks unreviewed dependency lifecycle scripts by default.  Keep the
# PATCH-NPM-DEPENDENCY-HYGIENE: keep install-script approval scoped to this
# Hermes update via a temporary global-config file:
# project-scoped --allow-scripts/env flags are rejected by npm, while changing
# ~/.npmrc would broaden the policy to unrelated projects.  Versions are pinned
# so an upstream bump becomes a deliberate re-review instead of inheriting
# executable permission silently.  unicode-animations is harmless under CI=1;
# fsevents ships the native artifact used on macOS.
_NPM_POLICY_ENV=()
_NPM_MAJOR=$(npm --version 2>/dev/null | cut -d. -f1 || true)
if [[ "${_NPM_MAJOR}" =~ ^[0-9]+$ ]] && ((_NPM_MAJOR >= 12)); then
    _NPM_POLICY_FILE=$(mktemp -t hermes-npm-policy.XXXXXX)
    chmod 600 "${_NPM_POLICY_FILE}"
    # Pins must be re-derived from package-lock.json hasInstallScript entries
    # (root copy is fsevents@2.3.2; tsx/vite nest 2.3.3), never from memory.
    # electron / electron-winstaller / node-pty are desktop-workspace-only and
    # outside the root+ui-tui/web install paths hermes update runs.
    printf '%s\n' \
        'allow-scripts=agent-browser@0.26.0,esbuild@0.28.1,fsevents@2.3.2,fsevents@2.3.3,unicode-animations@1.0.3' \
        >"${_NPM_POLICY_FILE}"
    _NPM_POLICY_ENV=("NPM_CONFIG_GLOBALCONFIG=${_NPM_POLICY_FILE}")
fi

_UPDATE_LOG=$(mktemp -t hermes-update.XXXXXX)
UPDATE_RC=0
if $_ACQUIRE_UPSTREAM; then
    set +e
    _acquire_upstream_target_with_retry "${_UPDATE_LOG}"
    UPDATE_RC=$?
    set -e
fi
if [[ ${UPDATE_RC} -eq 0 ]] && $_RUN_PINNED_UPDATER; then
    set +e
    _run_pinned_hermes_update "${_UPDATE_LOG}"
    UPDATE_RC=$?
    set -e
else
    if [[ ${UPDATE_RC} -eq 0 ]] && ! _reconcile_pinned_head; then
        UPDATE_RC=1
    elif [[ ${UPDATE_RC} -eq 0 ]] && $_PINNED_HEAD_ADVANCED; then
        note "Synchronizing Python runtime to the locally pinned target"
        set +e
        (
            cd "${HERMES_AGENT}" &&
                uv pip install --python venv/bin/python -e ".[all,feishu]"
        ) >"${_UPDATE_LOG}" 2>&1
        UPDATE_RC=$?
        set -e
        cat "${_UPDATE_LOG}"
    fi
fi
echo ""

# uv-pyenv recovery: on machines where uv (≥0.11) is installed but Python is
# managed by pyenv, `uv pip install -e .` inside `hermes update` ignores the
# activated venv and looks for a uv-managed Python at
# `~/.local/share/uv/python`. If that path is empty (as it is on this user's
# setup — see USER.md memory entry on uv/pyenv), the install fails with
# "No virtual environment or system Python installation found for path …".
# Retry once with explicit --python pointing at the project venv before
# giving up. Restricting to this specific error message keeps the fallback
# from masking unrelated install regressions.
if [[ $UPDATE_RC -ne 0 ]] &&
    grep -qF "No virtual environment or system Python installation found for path" "${_UPDATE_LOG}"; then
    note "Detected uv python-path mismatch — retrying install with --python venv/bin/python"
    set +e
    (
        cd "${HERMES_AGENT}" &&
            uv pip install --python venv/bin/python -e ".[all,feishu]"
    )
    _RETRY_RC=$?
    set -e
    if [[ $_RETRY_RC -eq 0 ]]; then
        ok "Install recovered via explicit --python fallback"
        UPDATE_RC=0
    else
        warn "Fallback install also failed (rc=${_RETRY_RC})"
        add_act "Investigate manually: cd ${HERMES_AGENT} && uv pip install --python venv/bin/python -e \".[all,feishu]\""
    fi
fi
rm -f "${_UPDATE_LOG}"

if [[ $UPDATE_RC -ne 0 ]]; then
    fail "Upstream acquisition/pinned reconciliation exited $UPDATE_RC — review output above"
    add_act "Resolve the errors above, then run: bash ${HERMES_HOME}/hermes-update.sh --reconcile"
    FINAL_RC=1
fi

# If we stashed extra changes above, silently pop them back.
# Conflicts are expected (upstream may have changed same files); use checkout
# --theirs to prefer upstream, since our patches are re-applied from the diff.
if $_EXTRA_STASHED; then
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

# Patches remain reverted through steps 4–7; the EXIT-trap restore window
# stays open until step 8a has either re-applied the bundle or deliberately
# rolled back. Do NOT clear _PATCHES_REVERTED here.

# ── 4. npm audit fix (PATCH-NPM-DEPENDENCY-HYGIENE) ──────────────────────────
# hermes update runs `npm install --no-audit` for node-based tools (e.g.
# agent-browser). This can leave known npm vulnerabilities unfixed.
# Run npm audit fix to patch them automatically.
step "Fixing npm vulnerabilities"

cd "${HERMES_AGENT}"
set +e
_AUDIT_OUT=$(env "${_NPM_POLICY_ENV[@]+"${_NPM_POLICY_ENV[@]}"}" CI=1 npm audit fix --quiet 2>&1)
_AUDIT_RC=$?
set -e

if [[ $_AUDIT_RC -eq 0 ]]; then
    if echo "${_AUDIT_OUT}" | grep -q "changed"; then
        ok "npm audit fix: $(echo "${_AUDIT_OUT}" | grep 'changed' | head -1)"
    else
        ok "npm audit: no vulnerabilities to fix"
    fi
else
    warn "npm audit fix exited $_AUDIT_RC — residual advisories or an upstream lock/range blocker remain"
    if [[ -n "${_AUDIT_OUT:-}" ]]; then
        printf '%s\n' "${_AUDIT_OUT}" | sed 's/^/      /'
    fi
    add_act "Review: cd ${HERMES_AGENT} && npm audit --json  (do not use --force; preserve upstream lock/ranges)"
fi

if [[ -n "${_NPM_POLICY_FILE}" ]]; then
    rm -f -- "${_NPM_POLICY_FILE}"
    _NPM_POLICY_FILE=""
fi

# npm audit fix can legitimately update the tracked upstream lockfile. Keep it
# outside local-patches.diff so Step 8 does not replay the same lockfile hunk
# after a future audit fix has already applied it, but surface the drift.
if ! git --no-pager diff --quiet HEAD -- package-lock.json 2>/dev/null; then
    warn "npm audit fix changed package-lock.json (not included in local-patches.diff)"
    add_warn "hermes-agent/package-lock.json is dirty after npm audit fix; review before committing or discarding"
    add_act "Review: cd ${HERMES_AGENT} && git diff -- package-lock.json"
fi
cd - >/dev/null

# ── 4b. Full skills sync (PATCH-SKILLS-MIRROR-METADATA) ──────────────────────
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
    # --archive preserves structure, --delete removes upstream-owned orphans.
    # Runtime sidecars belong to the local installation and must survive the
    # mirror pass: .usage.json stores per-skill telemetry/pins, .curator_state
    # stores scheduler history, .hub/.archive are owned by skills hub/curator,
    # and Python bytecode caches are regenerated by tests/runtime.
    _SKILLS_RUNTIME_EXCLUDES=(
        "/.bundled_manifest"
        "/.curator_state"
        "/.usage.json"
        "/.usage.json.lock"
        "/.curator_backups"
        "/.curator_suppressed"
        "/.hub"
        "/.archive"
        "__pycache__/"
        "*.pyc"
    )
    _SKILLS_RSYNC_EXCLUDE_ARGS=()
    _SKILLS_RSYNC_RETRY_EXCLUDES=""
    for _exclude in "${_SKILLS_RUNTIME_EXCLUDES[@]}"; do
        _SKILLS_RSYNC_EXCLUDE_ARGS+=(--exclude="${_exclude}")
        _SKILLS_RSYNC_RETRY_EXCLUDES+=" --exclude=${_exclude}"
    done
    set +e
    _SYNC_OUT=$(rsync -a --delete --itemize-changes \
        "${_SKILLS_RSYNC_EXCLUDE_ARGS[@]}" \
        "${BUNDLED_SKILLS_DIR}/" "${LOCAL_SKILLS_DIR}/" 2>&1)
    _SYNC_RC=$?
    set -e

    if [[ ${_SYNC_RC} -ne 0 ]]; then
        fail "Skills mirror failed (rsync rc=${_SYNC_RC})"
        if [[ -n "${_SYNC_OUT:-}" ]]; then
            add_warn "Skills rsync output: ${_SYNC_OUT//$'\n'/ | }"
        fi
        add_act "Retry with runtime exclusions: rsync -a --delete${_SKILLS_RSYNC_RETRY_EXCLUDES} ~/.hermes/hermes-agent/skills/ ~/.hermes/skills/"
        FINAL_RC=1
    else
        _ADDED=$(echo "${_SYNC_OUT}" | grep -c '^>f+++' || true)
        _UPDATED=$(echo "${_SYNC_OUT}" | grep -c '^>f[^+]' || true)
        _DELETED=$(echo "${_SYNC_OUT}" | grep -c '^\*deleting' || true)

        if [[ ${_ADDED} -gt 0 || ${_UPDATED} -gt 0 || ${_DELETED} -gt 0 ]]; then
            ok "Skills synced: +${_ADDED} new, ~${_UPDATED} updated, -${_DELETED} removed"
            if [[ ${_ADDED} -gt 0 ]]; then
                # A repeated bulk restore is as diagnostically important as a
                # bulk delete: preserve exact paths so the next stateless audit
                # can correlate which files vanished between convergent runs.
                echo "${_SYNC_OUT}" | sed -n 's|^>f+++[^ ]* |      + added: |p'
            fi
            if [[ ${_DELETED} -gt 0 ]]; then
                # Orphan removal is by design, but the names must survive in the
                # run log: a recurring wipe (2026-08-05 saw "-94" twice in one
                # day with no record of what was removed) is only diagnosable
                # next round if each pass keeps its deletion list.
                echo "${_SYNC_OUT}" | sed -n 's|^\*deleting[[:space:]]*|      - deleted: |p'
            fi
        else
            ok "Skills already in sync with upstream"
        fi
        ok "Skills runtime state preserved (.bundled_manifest, .curator_state, .usage.json, .hub/.archive, bytecode caches)"
    fi
else
    # Missing bundled skills = the mirror did not run at all. That is a
    # "command not executed / artifact missing" transaction failure, not a
    # skippable warning — downstream Step 8c llm-wiki re-seed would also be
    # silently skipped by its file guard.
    warn "Bundled skills dir not found: ${BUNDLED_SKILLS_DIR}"
    add_act "Check hermes-agent installation — skills directory missing"
    FINAL_RC=1
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

    # PATCH-ZSH-COMPLETION-SYNTAX regression sentinel: upstream commit fe61d95b4 (v0.13.0) fixed
    # the generator to emit the valid `'(-)'{-h,--help}'[...]'` form, so the
    # grep below should not match on current releases. If a future upstream
    # change reverts to the broken `(...){...}` combo, this block re-applies
    # the split-flag rewrite so Tab completion keeps working.
    # See: README.md § 本地补丁记录 [PATCH-ZSH-COMPLETION-SYNTAX]
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
        ok "PATCH-ZSH-COMPLETION-SYNTAX applied: fixed _arguments invalid syntax in completion script"
    else
        ok "PATCH-ZSH-COMPLETION-SYNTAX: upstream completion output already uses correct syntax — no fix needed"
    fi

    # Clear zsh completion cache so the regenerated _hermes is picked up.
    # Both regular .zcompdump* files and lingering compinit lock directories
    # (e.g. .zcompdump-host.lock/) are removed. `rm -f` does not delete
    # directories and would abort the script under `set -e`, so use a
    # tolerant loop that handles both.
    shopt -s nullglob 2>/dev/null || setopt NULL_GLOB 2>/dev/null || true
    for _zd in "$HOME"/.zcompdump*; do
        if [[ -d "${_zd}" ]]; then
            rm -rf -- "${_zd}" 2>/dev/null || true
        else
            rm -f -- "${_zd}" 2>/dev/null || true
        fi
    done
    note "zsh completion cache cleared (rebuilds on next shell open)"
else
    warn "Could not generate completions (exit $COMP_RC)"
    add_act "Run: hermes completion zsh > ~/.hermes/completions/_hermes"
    # PATCH-ZSH-COMPLETION-SYNTAX sentinel lives in this step: a failed
    # generation means the sentinel could not run at all, so the upgrade must
    # not report success (playbook: out-of-tree sentinels gate the final RC).
    FINAL_RC=1
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
LAZY_DEPS_PY="${HERMES_AGENT}/tools/lazy_deps.py"
LAZY_DEPS_TEST_PY="${HERMES_AGENT}/tests/tools/test_lazy_deps.py"
_PATCH_APPLY_OK=false

# -- 8a. Apply saved diff -------------------------------------------------------
if [[ -f "${PATCH_FILE}" ]]; then
    cd "${HERMES_AGENT}"
    if ! _bundle_matches_patched_files "${PATCH_FILE}"; then
        warn "Saved patch file does not exactly cover PATCHED_FILES — skipping auto-apply"
        add_warn "patches/local-patches.diff path set is incomplete, duplicated, or unregistered"
        add_act "Reconcile ${PATCH_FILE} with: bash ${HERMES_HOME}/hermes-update.sh --print-patched-files"
    elif grep -nE '^\+?(<<<<<<<|=======|>>>>>>>)' "${PATCH_FILE}" >/dev/null 2>&1; then
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
                _restore_patched_files_to_head "${PATCHED_FILES[@]}" || true
                warn "Patches passed --check but apply failed unexpectedly"
                add_warn "Local patches were NOT applied — some customizations inactive"
                add_act "Retry manually: cd ${HERMES_AGENT} && git apply ${PATCH_FILE}"
                add_act "See README.md § 本地补丁 for re-application instructions"
            fi
        elif git apply --3way "${PATCH_FILE}" 2>/dev/null; then
            # --3way implies --index. Return the resolved overlay to an
            # unstaged worktree immediately; a staged index would invalidate
            # cached-forward replay checks and make the next update ambiguous.
            if git restore --staged -- "${PATCHED_FILES[@]}" 2>/dev/null; then
                _PATCH_MODE="3-way"
            else
                _restore_patched_files_to_head "${PATCHED_FILES[@]}" || true
                warn "3-way apply succeeded but the managed index could not be cleaned"
                add_warn "Local patches were rolled back because replay must end with a clean index"
                add_act "Apply manually, resolve, then unstage managed paths before rerunning"
            fi
        else
            _restore_patched_files_to_head "${PATCHED_FILES[@]}" || true
            warn "Patches could not be applied (upstream conflict)"
            add_warn "Local patches were NOT applied — some customizations inactive"
            add_act "Manual fix: cd ${HERMES_AGENT} && git apply --reject ${PATCH_FILE}"
            add_act "See README.md § 本地补丁 for re-application instructions"
        fi

        if [[ -n "${_PATCH_MODE}" ]]; then
            if ! git diff --cached --quiet; then
                _restore_patched_files_to_head "${PATCHED_FILES[@]}" || true
                warn "${_PATCH_MODE} apply left staged replay state — restored patched files to HEAD"
                add_warn "Patch re-apply did not converge to an index-clean worktree"
                add_act "Inspect the index, then re-apply the preserved bundle manually"
            elif _has_conflict_markers "${PATCHED_FILES[@]}"; then
                _restore_patched_files_to_head "${PATCHED_FILES[@]}" || true
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

# Step 8a has made its apply decision: the tree is either patched or was
# deliberately restored to HEAD (poisoned bundle / failed apply, with manual
# actions queued above). Either way the EXIT trap must no longer re-apply.
_PATCHES_REVERTED=false

# -- 8b. Patch invariant gates (structural sentinels + smoke checks) ------------
# Archived patches retain independent regression gates. A regression in an
# upstream-absorbed invariant must block the replay-bundle refresh just like an
# active patch failure; otherwise the new base could be recorded as healthy.
_ARCHIVED_DOCTOR_TOOLSETS_OK=false
_ARCHIVED_DASHBOARD_BUILD_CACHE_OK=false
_ARCHIVED_DELEGATE_ACP_ROUTING_OK=false
_ARCHIVED_GEMINI_THOUGHT_SIGNATURE_OK=false
_ARCHIVED_LAZY_ACTIVE_ANCHOR_OK=false
_SKILL_PATCH_OK=false
_FEISHU_DEPS_PATCH_OK=false
_OPENCLAW_GATEWAY_TOKEN_PATCH_OK=false
_FEISHU_GROUP_ADMISSION_PATCH_OK=false
_FEISHU_MISSED_EVENT_BACKFILL_PATCH_OK=false
_FEISHU_GROUP_SCOPE_PATCH_OK=false
_PLATFORM_CAPABILITY_SCOPE_PATCH_OK=false
_FEISHU_GROUP_APPROVAL_FLOOR_PATCH_OK=false
_FEISHU_NO_THREAD_PATCH_OK=false
_FEISHU_FINAL_ONLY_PATCH_OK=false
_PEOPLE_PROFILE_PATCH_OK=false
_FEISHU_RESOURCE_ACCESS_PATCH_OK=false
_TRUSTED_DOCUMENT_EXTRACTION_PATCH_OK=false
_FEISHU_MARKDOWN_PATCH_OK=false
_FEISHU_SSRF_TEST_SYSPROXY_PATCH_OK=false
_VERTEX_THOUGHTS_PATCH_OK=false
_VERTEX_DOCTOR_PATCH_OK=false
_VERTEX_FALLBACK_PATCH_OK=false
_VERTEX_IMAGE_ROUTING_PATCH_OK=false
_VERTEX_VIDEO_ROUTING_PATCH_OK=false
_HISTORY_RETENTION_PATCH_OK=false
_APPROVAL_TEMP_CLEANUP_PATCH_OK=false
_FTS5_CJK_BUILD_PATCH_OK=false

if [[ -f "${VENV_PY}" && -f "${SKILL_TOOL}" ]]; then
    _SKILL_CHECK=$(
        cd "${HERMES_AGENT}" &&
            "${VENV_PY}" - <<'PYEOF' 2>/dev/null
import sys
from pathlib import Path
sys.path.insert(0, ".")
from tools.skill_manager_tool import _resolve_skill_dir
result = str(_resolve_skill_dir("_patch_test"))
expected_root = str(Path.home() / ".hermes" / "my-skills") + "/"
print("ok" if result.startswith(expected_root) else "native")
PYEOF
    )
    if [[ "${_SKILL_CHECK}" == "ok" ]]; then
        ok "Skill routing patch: active (new skills → my-skills/)"
        _SKILL_PATCH_OK=true
    else
        warn "Skill routing patch inactive — new skills will land in ~/.hermes/skills/"
        add_act "Re-apply: see PATCHES.md § [PATCH-SKILL-CREATE-ROOT]"
    fi
else
    warn "Could not locate venv or skill_manager_tool.py — skipping skill routing check"
fi

if [[ -f "${DOCTOR_PY}" ]]; then
    if grep -q "_get_platform_tools" "${DOCTOR_PY}" 2>/dev/null; then
        ok "Doctor issue-count filter: active (upstream merged, PATCH-DOCTOR-ENABLED-TOOLSETS retired)"
        _ARCHIVED_DOCTOR_TOOLSETS_OK=true
    else
        warn "Doctor issue-count filter missing — hermes doctor may report false issue for disabled toolsets"
        add_act "Check upstream: hermes_cli/doctor.py should filter missing API-key issues through enabled toolsets"
    fi
else
    warn "Could not locate hermes_cli/doctor.py — skipping doctor patch check"
fi

# PATCH-DASHBOARD-BUILD-CACHE (dashboard web-build skip) was merged upstream via _web_ui_build_needed()
# in commit 5b5a53a1; verify the upstream helper is present so we can detect
# regressions, but no local patch is required.
MAIN_PY="${HERMES_AGENT}/hermes_cli/main.py"
if [[ -f "${MAIN_PY}" ]]; then
    if grep -q '_web_ui_build_needed' "${MAIN_PY}" 2>/dev/null; then
        ok "Dashboard web-build skip: active (upstream merged, PATCH-DASHBOARD-BUILD-CACHE retired)"
        _ARCHIVED_DASHBOARD_BUILD_CACHE_OK=true
    else
        warn "Upstream _web_ui_build_needed() missing — dashboard may rebuild on every start"
        add_act "Check upstream: hermes_cli/main.py should define _web_ui_build_needed()"
    fi
fi

# PATCH-DELEGATE-ACP-ROUTING (delegate ACP routing) was merged upstream in v0.10.0.
# Verify the behavior still exists but don't require local patch.
if [[ -f "${DELEGATE_TOOL}" ]]; then
    if grep -q 'override_acp_command' "${DELEGATE_TOOL}" 2>/dev/null &&
        grep -q 'copilot-acp' "${DELEGATE_TOOL}" 2>/dev/null; then
        ok "Delegate ACP routing: active (upstream merged, PATCH-DELEGATE-ACP-ROUTING retired)"
        _ARCHIVED_DELEGATE_ACP_ROUTING_OK=true
    else
        warn "Delegate ACP routing missing — delegate_task acp_command may be ignored"
        add_act "Check upstream: _build_child_agent should force copilot-acp when override_acp_command is set"
    fi
else
    warn "Could not locate tools/delegate_tool.py — skipping delegate patch check"
fi

# PATCH-GEMINI-THOUGHT-SIGNATURE was merged upstream in v0.11.0. Preserve the
# property + regression-test contract so Gemini tool replay cannot silently
# drop thought_signature metadata again.
TRANSPORT_TYPES_PY="${HERMES_AGENT}/agent/transports/types.py"
TRANSPORT_TYPES_TEST_PY="${HERMES_AGENT}/tests/agent/transports/test_types.py"
if [[ -f "${TRANSPORT_TYPES_PY}" && -f "${TRANSPORT_TYPES_TEST_PY}" ]]; then
    if grep -q 'def extra_content' "${TRANSPORT_TYPES_PY}" 2>/dev/null &&
        grep -q 'provider_data or {}' "${TRANSPORT_TYPES_PY}" 2>/dev/null &&
        grep -q 'test_extra_content_getattr_pattern' "${TRANSPORT_TYPES_TEST_PY}" 2>/dev/null; then
        ok "Gemini thought-signature replay: active (upstream merged, PATCH-GEMINI-THOUGHT-SIGNATURE retired)"
        _ARCHIVED_GEMINI_THOUGHT_SIGNATURE_OK=true
    else
        warn "Gemini thought-signature replay missing — Gemini tool calls may fail on the next turn"
        add_act "Check upstream: ToolCall.extra_content must expose provider_data thought_signature metadata"
    fi
else
    warn "Could not locate transport types or its tests — skipping Gemini thought-signature check"
fi

if [[ -f "${PYPROJECT}" && -f "${LAZY_DEPS_PY}" ]]; then
    if grep -q 'python-socks' "${PYPROJECT}" 2>/dev/null &&
        grep -q 'python-socks' "${LAZY_DEPS_PY}" 2>/dev/null; then
        ok "Feishu python-socks dep patch: active (feishu extra + lazy platform deps)"
        _FEISHU_DEPS_PATCH_OK=true
    else
        warn "Feishu python-socks dep patch inactive — feishu gateway may fail behind proxy"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-SOCKS-DEPENDENCY]"
    fi
else
    warn "Could not locate pyproject.toml or tools/lazy_deps.py — skipping feishu deps check"
fi

if [[ -f "${LAZY_DEPS_PY}" && -f "${LAZY_DEPS_TEST_PY}" ]]; then
    if grep -q 'if specs and _is_present(specs\[0\])' "${LAZY_DEPS_PY}" 2>/dev/null &&
        grep -q 'test_shared_dependency_does_not_activate_feature' "${LAZY_DEPS_TEST_PY}" 2>/dev/null; then
        ok "Lazy feature activation anchor: active (upstream merged, PATCH-LAZY-ACTIVATION retired)"
        _ARCHIVED_LAZY_ACTIVE_ANCHOR_OK=true
    else
        warn "Upstream lazy activation anchor missing — update may retry unused Matrix/python-olm"
        add_act "Check upstream: active_features() should probe only each feature's first declared dependency"
    fi
else
    warn "Could not locate lazy activation source or regression test"
fi

OPENCLAW_MIGRATOR="${HERMES_AGENT}/optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"
OPENCLAW_MIGRATION_DOC="${HERMES_AGENT}/website/docs/guides/migrate-from-openclaw.md"
OPENCLAW_MIGRATION_DOC_ZH="${HERMES_AGENT}/website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md"
if [[ -f "${OPENCLAW_MIGRATOR}" && -f "${OPENCLAW_MIGRATION_DOC}" && -f "${OPENCLAW_MIGRATION_DOC_ZH}" ]]; then
    if ! grep -Eq 'HERMES_GATEWAY_TOKEN|gateway\.auth\.token|Gateway auth token|Gateway 认证 token' "${OPENCLAW_MIGRATOR}" "${OPENCLAW_MIGRATION_DOC}" "${OPENCLAW_MIGRATION_DOC_ZH}" 2>/dev/null; then
        ok "OpenClaw gateway token patch: active (unused HERMES_GATEWAY_TOKEN not migrated)"
        _OPENCLAW_GATEWAY_TOKEN_PATCH_OK=true
    else
        warn "OpenClaw gateway token patch inactive — migration may recreate unused HERMES_GATEWAY_TOKEN"
        add_act "Re-apply: see PATCHES.md § [PATCH-OPENCLAW-TOKEN-MIGRATION]"
    fi
else
    warn "Could not locate OpenClaw migration files — skipping gateway token patch check"
fi

FEISHU_PY="${HERMES_AGENT}/plugins/platforms/feishu/adapter.py"
GATEWAY_RUN_PY="${HERMES_AGENT}/gateway/run.py"
SLASH_COMMANDS_PY="${HERMES_AGENT}/gateway/slash_commands.py"
SESSION_CONTEXT_PY="${HERMES_AGENT}/gateway/session_context.py"
SESSION_PY="${HERMES_AGENT}/gateway/session.py"
GATEWAY_CONFIG_PY="${HERMES_AGENT}/gateway/config.py"
AUTHZ_MIXIN_PY="${HERMES_AGENT}/gateway/authz_mixin.py"
TOOLS_CONFIG_PY="${HERMES_AGENT}/hermes_cli/tools_config.py"
FEISHU_BOT_ADMISSION_TEST_PY="${HERMES_AGENT}/tests/gateway/test_feishu_bot_admission.py"
FEISHU_BOT_AUTH_BYPASS_TEST_PY="${HERMES_AGENT}/tests/gateway/test_feishu_bot_auth_bypass.py"
FEISHU_TEST_PY="${HERMES_AGENT}/tests/gateway/test_feishu.py"
FEISHU_MESSAGING_DOC="${HERMES_AGENT}/website/docs/user-guide/messaging/feishu.md"
SESSION_TEST_PY="${HERMES_AGENT}/tests/gateway/test_session.py"
SESSION_ENV_TEST_PY="${HERMES_AGENT}/tests/gateway/test_session_env.py"
RUN_PROGRESS_TEST_PY="${HERMES_AGENT}/tests/gateway/test_run_progress_topics.py"
VERBOSE_COMMAND_TEST_PY="${HERMES_AGENT}/tests/gateway/test_verbose_command.py"
TOOLS_CONFIG_TEST_PY="${HERMES_AGENT}/tests/hermes_cli/test_tools_config.py"
LLM_WIKI_SKILL_MD="${HERMES_AGENT}/skills/research/llm-wiki/SKILL.md"

# PATCH-FEISHU-GROUP-ADMISSION: group admission, context backfill and current-
# speaker integrity. Trigger priority,
# per-sender batching and prompt attribution are one admission/identity contract.
if [[ -f "${FEISHU_PY}" && -f "${GATEWAY_RUN_PY}" && -f "${SESSION_PY}" && -f "${GATEWAY_CONFIG_PY}" && -f "${AUTHZ_MIXIN_PY}" && -f "${FEISHU_BOT_ADMISSION_TEST_PY}" && -f "${FEISHU_BOT_AUTH_BYPASS_TEST_PY}" && -f "${FEISHU_TEST_PY}" && -f "${SESSION_TEST_PY}" && -f "${LLM_WIKI_SKILL_MD}" ]]; then
    if grep -q 'assistant_user_ids' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_sender_is_configured_assistant_user' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_fetch_channel_context' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_FEISHU_GROUP_TECHNICAL_QUERY_INSTRUCTION' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'never omit search_files.path' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'retry with the explicit allowed path' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'FEISHU_GROUP_ALLOWED_CHATS' "${AUTHZ_MIXIN_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_allowed_chats_wildcard_authorizes_groups_only' "${FEISHU_BOT_AUTH_BYPASS_TEST_PY}" 2>/dev/null &&
        grep -q 'history_backfill_max_chars' "${GATEWAY_CONFIG_PY}" 2>/dev/null &&
        grep -q 'test_process_inbound_message_owner_bot_mention_skips_self_intro' "${FEISHU_BOT_ADMISSION_TEST_PY}" 2>/dev/null &&
        grep -q 'explicit path under ~/.hermes/wiki' "${FEISHU_BOT_ADMISSION_TEST_PY}" 2>/dev/null &&
        grep -q 'bare_mention_intent' "${GATEWAY_CONFIG_PY}" 2>/dev/null &&
        grep -q '_build_bare_mention_intent_text' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'Sandboxed Feishu groups' "${LLM_WIKI_SKILL_MD}" 2>/dev/null &&
        grep -q 'search_files(pattern="transformer", path="~/.hermes/wiki"' "${LLM_WIKI_SKILL_MD}" 2>/dev/null &&
        grep -q 'test_dm_bare_mention_routes_reply_or_recent_conversation_intent' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_bare_mention_dropped_when_toggle_disabled' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'Current message author' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'Current-author rule' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'main subject of your response' "${SESSION_PY}" 2>/dev/null &&
        grep -qF '[New message]' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'test_bot_mention_takes_priority_over_assistant_user_mention' "${FEISHU_BOT_ADMISSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_text_batch_does_not_merge_different_senders' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_group_turn_body_keeps_current_author_next_to_question' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'Current message author' "${SESSION_TEST_PY}" 2>/dev/null; then
        ok "PATCH-FEISHU-GROUP-ADMISSION active: context + current-speaker integrity"
        _FEISHU_GROUP_ADMISSION_PATCH_OK=true
    else
        warn "PATCH-FEISHU-GROUP-ADMISSION inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-GROUP-ADMISSION]"
    fi
else
    warn "Could not locate PATCH-FEISHU-GROUP-ADMISSION files"
fi

# PATCH-FEISHU-MISSED-EVENT-BACKFILL: startup/reconnect scans known chats for
# missed trigger messages and treats quote-covered parent IDs as answered so
# delayed pushes cannot duplicate a manual quote+@ recovery.
if [[ -f "${FEISHU_PY}" && -f "${GATEWAY_CONFIG_PY}" && -f "${FEISHU_TEST_PY}" && -f "${FEISHU_MESSAGING_DOC}" ]]; then
    if grep -q 'def _run_missed_event_backfill' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _backfill_missed_events_for_chat' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _install_ws_reconnected_backfill_hook' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _mark_related_message_ids_covered' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _has_seen_message_id' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'ListMessageRequest is not None' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'missed_event_backfill_chats' "${GATEWAY_CONFIG_PY}" 2>/dev/null &&
        grep -q 'ws_ping_timeout' "${GATEWAY_CONFIG_PY}" 2>/dev/null &&
        grep -q 'test_missed_event_backfill_dispatches_unseen_mentions_from_known_chat' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_quote_covered_parent_is_marked_seen_for_missed_backfill' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_ws_reconnected_hook_schedules_missed_event_backfill' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_startup_backfill_runs_in_boot_window_then_throttles' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'Missed Event Backfill' "${FEISHU_MESSAGING_DOC}" 2>/dev/null; then
        ok "PATCH-FEISHU-MISSED-EVENT-BACKFILL active: reconnect replay + quote-covered dedup"
        _FEISHU_MISSED_EVENT_BACKFILL_PATCH_OK=true
    else
        warn "PATCH-FEISHU-MISSED-EVENT-BACKFILL inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-MISSED-EVENT-BACKFILL]"
    fi
else
    warn "Could not locate PATCH-FEISHU-MISSED-EVENT-BACKFILL files"
fi

# PATCH-FEISHU-GROUP-SCOPE: the group capability namespace. Group sessions resolve tools and
# skill policy through feishu_group while owner DMs remain on feishu.
if [[ -f "${SESSION_CONTEXT_PY}" && -f "${GATEWAY_RUN_PY}" && -f "${SLASH_COMMANDS_PY}" && -f "${TOOLS_CONFIG_PY}" && -f "${SESSION_ENV_TEST_PY}" && -f "${RUN_PROGRESS_TEST_PY}" && -f "${VERBOSE_COMMAND_TEST_PY}" && -f "${TOOLS_CONFIG_TEST_PY}" ]]; then
    if grep -q 'HERMES_SESSION_PLATFORM_CONFIG_KEY' "${SESSION_CONTEXT_PY}" 2>/dev/null &&
        grep -q 'return "feishu_group"' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'platform_key = _platform_config_key_for_source(source)' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'platform_key = _platform_config_key_for_source(event.source)' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        [[ "$(grep -F -c '_platform_config_key(source.platform)' "${GATEWAY_RUN_PY}" 2>/dev/null || true)" -eq 1 ]] &&
        ! grep -F -q '_platform_config_key(event.source.platform)' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        ! grep -F -q '_platform_config_key(source.platform)' "${SLASH_COMMANDS_PY}" 2>/dev/null &&
        ! grep -F -q '_platform_config_key(event.source.platform)' "${SLASH_COMMANDS_PY}" 2>/dev/null &&
        grep -q 'recover_platform_tools' "${TOOLS_CONFIG_PY}" 2>/dev/null &&
        grep -q 'test_set_session_env_sets_feishu_group_config_key' "${SESSION_ENV_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_runtime_scope_hides_progress_and_uses_group_tools' "${RUN_PROGRESS_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_updates_group_scope_without_mutating_dm' "${VERBOSE_COMMAND_TEST_PY}" 2>/dev/null &&
        grep -q 'test_get_platform_tools_feishu_group_uses_independent_config' "${TOOLS_CONFIG_TEST_PY}" 2>/dev/null; then
        ok "PATCH-FEISHU-GROUP-SCOPE active: runtime display/tools use feishu_group, owner DM stays feishu"
        _FEISHU_GROUP_SCOPE_PATCH_OK=true
    else
        warn "PATCH-FEISHU-GROUP-SCOPE inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-GROUP-SCOPE]"
    fi
else
    warn "Could not locate PATCH-FEISHU-GROUP-SCOPE files"
fi

SKILL_UTILS_PY="${HERMES_AGENT}/agent/skill_utils.py"
PROMPT_BUILDER_PY="${HERMES_AGENT}/agent/prompt_builder.py"
SKILLS_TOOL_PY="${HERMES_AGENT}/tools/skills_tool.py"
SKILLS_TOOL_TEST_PY="${HERMES_AGENT}/tests/tools/test_skills_tool.py"
TOOLSETS_PY="${HERMES_AGENT}/toolsets.py"
APPROVAL_PY="${HERMES_AGENT}/tools/approval.py"
APPROVAL_TEST_PY="${HERMES_AGENT}/tests/tools/test_approval.py"

# PATCH-PLATFORM-CAPABILITY-SCOPE: reusable platform capability scoping
# primitives. Group approval is deliberately verified separately.
if [[ -f "${SKILL_UTILS_PY}" && -f "${PROMPT_BUILDER_PY}" && -f "${SKILLS_TOOL_PY}" && -f "${SKILLS_TOOL_TEST_PY}" && -f "${TOOLSETS_PY}" ]]; then
    if grep -q 'get_allowed_skill_names' "${SKILL_UTILS_PY}" 2>/dev/null &&
        grep -q 'get_allowed_skill_names' "${PROMPT_BUILDER_PY}" 2>/dev/null &&
        grep -q 'get_allowed_skill_names' "${SKILLS_TOOL_PY}" 2>/dev/null &&
        grep -q 'test_qualified_local_skill_allowed_by_bare_name' "${SKILLS_TOOL_TEST_PY}" 2>/dev/null &&
        grep -q 'skills_readonly' "${TOOLSETS_PY}" 2>/dev/null &&
        grep -q 'file_readonly' "${TOOLSETS_PY}" 2>/dev/null &&
        (cd "${HERMES_AGENT}" && "${VENV_PY}" -c '
import toolsets as t
assert t.TOOLSETS["skills_readonly"]["tools"] == ["skills_list", "skill_view"], t.TOOLSETS["skills_readonly"]["tools"]
assert t.TOOLSETS["file_readonly"]["tools"] == ["read_file", "search_files"], t.TOOLSETS["file_readonly"]["tools"]
' 2>/dev/null); then
        ok "PATCH-PLATFORM-CAPABILITY-SCOPE active: allowlist + read-only toolsets"
        _PLATFORM_CAPABILITY_SCOPE_PATCH_OK=true
    else
        warn "PATCH-PLATFORM-CAPABILITY-SCOPE inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-PLATFORM-CAPABILITY-SCOPE]"
    fi
else
    warn "Could not locate PATCH-PLATFORM-CAPABILITY-SCOPE files"
fi

# PATCH-FEISHU-GROUP-APPROVAL: group sessions must never turn dangerous-command approval into a
# privilege escalation. Owner Feishu DMs retain the normal manual approval path.
if [[ -f "${APPROVAL_PY}" && -f "${APPROVAL_TEST_PY}" ]]; then
    if grep -q '_is_restricted_feishu_approval_session' "${APPROVAL_PY}" 2>/dev/null &&
        grep -q 'restricted_chat' "${APPROVAL_PY}" 2>/dev/null &&
        grep -q 'PATCH-FEISHU-GROUP-APPROVAL hard floor' "${APPROVAL_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_dangerous_command_does_not_send_approval_card' "${APPROVAL_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_block_precedes_allowlist_and_prior_approvals' "${APPROVAL_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_execute_code_guard_blocked' "${APPROVAL_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_chat_type_from_context_when_key_not_canonical' "${APPROVAL_TEST_PY}" 2>/dev/null; then
        ok "PATCH-FEISHU-GROUP-APPROVAL active: approval escalation hard-blocked"
        _FEISHU_GROUP_APPROVAL_FLOOR_PATCH_OK=true
    else
        warn "PATCH-FEISHU-GROUP-APPROVAL inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-GROUP-APPROVAL]"
    fi
else
    warn "Could not locate PATCH-FEISHU-GROUP-APPROVAL files"
fi

# PATCH-FEISHU-NORMAL-REPLY: replies must never create a topic/thread. Generic
# metadata.thread_id must not become receive_id_type=thread_id.
DISPLAY_CONFIG_PY="${HERMES_AGENT}/gateway/display_config.py"
DISPLAY_CONFIG_TEST_PY="${HERMES_AGENT}/tests/gateway/test_display_config.py"
if [[ -f "${FEISHU_PY}" && -f "${FEISHU_TEST_PY}" ]]; then
    if grep -q 'reply_in_thread = False' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'Ignore generic thread metadata on Feishu' "${FEISHU_PY}" 2>/dev/null &&
        ! grep -q 'reply_in_thread = bool' "${FEISHU_PY}" 2>/dev/null &&
        ! grep -qF '_build_create_message_request("thread_id"' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'test_send_never_replies_in_thread_even_with_thread_metadata' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_send_ignores_thread_metadata_when_no_reply_anchor' "${FEISHU_TEST_PY}" 2>/dev/null; then
        ok "PATCH-FEISHU-NORMAL-REPLY active: replies stay in the normal chat lane"
        _FEISHU_NO_THREAD_PATCH_OK=true
    else
        warn "PATCH-FEISHU-NORMAL-REPLY inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-NORMAL-REPLY]"
    fi
else
    warn "Could not locate PATCH-FEISHU-NORMAL-REPLY files"
fi

# PATCH-FEISHU-FINAL-ONLY: upstream defaults stay final-only. This personal
# config deliberately enables separate `new` tool cards only in the owner DM;
# groups keep every progress/interim/thinking surface off. Provider-side thought
# suppression remains the separate PATCH-VERTEX-HIDDEN-THOUGHTS contract.
if [[ -f "${DISPLAY_CONFIG_PY}" && -f "${DISPLAY_CONFIG_TEST_PY}" && -f "${RUN_PROGRESS_TEST_PY}" && -f "${VERBOSE_COMMAND_TEST_PY}" ]]; then
    if grep -q '"feishu":          {' "${DISPLAY_CONFIG_PY}" 2>/dev/null &&
        grep -q 'test_feishu_defaults_to_final_only' "${DISPLAY_CONFIG_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_runtime_scope_hides_progress_and_uses_group_tools' "${RUN_PROGRESS_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_group_updates_group_scope_without_mutating_dm' "${VERBOSE_COMMAND_TEST_PY}" 2>/dev/null &&
        _verify_feishu_display_policy; then
        ok "PATCH-FEISHU-FINAL-ONLY active: DM new-tool cards; groups final-only; thinking hidden"
        _FEISHU_FINAL_ONLY_PATCH_OK=true
    else
        warn "PATCH-FEISHU-FINAL-ONLY inactive or local DM/group display policy drifted"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-FINAL-ONLY]"
    fi
else
    warn "Could not locate PATCH-FEISHU-FINAL-ONLY files"
fi

# PATCH-LOCAL-PROFILES: per-person + per-group profile injection (people.yaml / groups.yaml
# → system prompt), presentational service-hours intro hint, group tool-limitation
# disclosure, and group-visible private profile redaction. Source-side hooks live
# in gateway/session.py + gateway/run.py; stream guardrails live in
# gateway/stream_consumer.py. The data files ~/.hermes/people.yaml and
# ~/.hermes/groups.yaml are in the config repo and intentionally NOT PATCHED_FILES.
STREAM_CONSUMER_PY="${HERMES_AGENT}/gateway/stream_consumer.py"
STREAM_CONSUMER_TEST_PY="${HERMES_AGENT}/tests/gateway/test_stream_consumer_silence.py"
BACKGROUND_COMMAND_TEST_PY="${HERMES_AGENT}/tests/gateway/test_background_command.py"

_secure_local_profile_files() {
    local profile_name profiles_file mode
    for profile_name in people.yaml groups.yaml; do
        profiles_file="${HERMES_HOME}/${profile_name}"
        [[ -e "${profiles_file}" ]] || continue
        chmod 600 "${profiles_file}" 2>/dev/null || return 1
        mode="$(stat -f '%Lp' "${profiles_file}" 2>/dev/null || stat -c '%a' "${profiles_file}" 2>/dev/null || true)"
        [[ "${mode}" == "600" ]] || return 1
    done
}

_PEOPLE_PROFILE_FILE_OK=false
if _secure_local_profile_files; then
    _PEOPLE_PROFILE_FILE_OK=true
else
    warn "Could not secure people.yaml/groups.yaml to mode 0600"
    add_act "Restrict local profile access: chmod 600 ${HERMES_HOME}/people.yaml ${HERMES_HOME}/groups.yaml"
fi

if [[ -f "${SESSION_PY}" && -f "${GATEWAY_RUN_PY}" && -f "${STREAM_CONSUMER_PY}" && -f "${SESSION_TEST_PY}" && -f "${STREAM_CONSUMER_TEST_PY}" && -f "${BACKGROUND_COMMAND_TEST_PY}" ]]; then
    if grep -q 'people-profile' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'def _load_people_profiles' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'def _lookup_person' "${SESSION_PY}" 2>/dev/null &&
        grep -q '称呼/address' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'redact_private_person_profile_text' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'redact_private_person_profile_text' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'text_filter' "${STREAM_CONSUMER_PY}" 2>/dev/null &&
        grep -q 'group-profile' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'def _load_group_profiles' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'def _lookup_group' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'service_hours' "${SESSION_PY}" 2>/dev/null &&
        grep -q '_GROUP_TOOL_LIMITATION_RULE' "${SESSION_PY}" 2>/dev/null &&
        grep -q '_PEOPLE_SOURCE_SECRECY_RULE' "${SESSION_PY}" 2>/dev/null &&
        grep -q '_PEOPLE_SOURCE_LITERALS' "${SESSION_PY}" 2>/dev/null &&
        grep -q 'test_address_is_public_and_usable_for_reply' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_private_profile_redactor_keeps_public_fields' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_private_profile_redactor_leaves_dm_text_untouched' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_unlisted_fields_are_internal_and_identity_values_are_redacted' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_people_file_remains_owner_editable_while_removing_other_access' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_groups_file_remains_owner_editable_while_removing_other_access' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_people_source_secrecy_rule_present_for_group' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_redactor_hides_roster_file_name_even_without_profile_match' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'class TestPeopleProfileInjection' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'class TestGroupProfileInjection' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'test_service_hours_are_intro_hint_not_reply_gate' "${SESSION_TEST_PY}" 2>/dev/null &&
        grep -q 'def _history_sender_person' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _history_person_qualifier' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'test_history_sender_label_joins_people_profile' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_history_sender_label_survives_profile_lookup_failure' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_text_filter_applies_before_stream_delivery' "${STREAM_CONSUMER_TEST_PY}" 2>/dev/null &&
        grep -q 'test_non_dm_interim_direct_fallback_redacts_private_profile' "${RUN_PROGRESS_TEST_PY}" 2>/dev/null &&
        grep -q 'assert "Prompt:" not in content' "${BACKGROUND_COMMAND_TEST_PY}" 2>/dev/null &&
        grep -q 'redact_private_person_profile_text(source, response)' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q '_stts_consumer_ref.on_delta(_visible_turn_text(text))' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        $_PEOPLE_PROFILE_FILE_OK; then
        ok "People/group profile patch: active (people.yaml + groups.yaml owner-rw mode 0600; profile lookup; final/stream/interim/background/audio redaction; no background prompt replay; roster-source secrecy; public-only history sender join)"
        _PEOPLE_PROFILE_PATCH_OK=true
    else
        warn "People/group profile patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-LOCAL-PROFILES]"
    fi
else
    warn "Could not locate PATCH-LOCAL-PROFILES files"
fi

# PATCH-FEISHU-RESOURCE-ACCESS: Feishu DM/group explicit-quote attachment
# recovery, group sender-window backfill, Drive/doc acquisition, and complete
# bounded delivery of merged-forward transcripts. File-format extraction belongs
# to PATCH-DOCUMENT-EXTRACTION.
FEISHU_DOC_TOOL_PY="${HERMES_AGENT}/tools/feishu_doc_tool.py"
FEISHU_TOOLS_TEST_PY="${HERMES_AGENT}/tests/tools/test_feishu_tools.py"
PLATFORMS_BASE_PY="${HERMES_AGENT}/gateway/platforms/base.py"
if [[ -f "${FEISHU_PY}" && -f "${FEISHU_TEST_PY}" && -f "${FEISHU_DOC_TOOL_PY}" && -f "${FEISHU_TOOLS_TEST_PY}" && -f "${PLATFORMS_BASE_PY}" ]]; then
    if grep -q 'def _backfill_sender_attachments' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _backfill_reply_attachments' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _mark_attachment_backfilled' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_FEISHU_BACKFILL_WINDOW_SECONDS' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_backfilled_attachment_ids' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'if text == "/":' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'can_backfill_group = ' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'source_chat_type == "dm" or can_backfill_group' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'normalized.image_keys or normalized.media_refs' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _download_feishu_drive_file' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_FEISHU_DRIVE_FILE_URL_RE' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'is_forward_child' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'if normalized.raw_type == "merge_forward":' "${FEISHU_PY}" 2>/dev/null &&
        grep -q '_FEISHU_MERGE_FORWARD_REPLY_CONTEXT_MAX_CHARS' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q '_client_from_env' "${FEISHU_DOC_TOOL_PY}" 2>/dev/null &&
        grep -q '"\.odt": "application/vnd.oasis.opendocument.text"' "${PLATFORMS_BASE_PY}" 2>/dev/null &&
        grep -q 'test_backfill_reply_attachments_downloads_post_images' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_explicit_requote_is_not_suppressed_and_media_video_is_preserved' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_quoted_resource_matrix_reaches_event_across_dm_and_group_triggers' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_quoted_merge_forward_expands_children_and_attachments' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_feishu_merge_forward_reply_context_is_not_cut_at_generic_500_chars' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'class TestFeishuDriveFileLinks' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'test_doc_read_builds_env_client_outside_comment_context' "${FEISHU_TOOLS_TEST_PY}" 2>/dev/null; then
        ok "PATCH-FEISHU-RESOURCE-ACCESS active: complete quote/backfill matrix + merged transcripts + Drive/doc access"
        _FEISHU_RESOURCE_ACCESS_PATCH_OK=true
    else
        warn "PATCH-FEISHU-RESOURCE-ACCESS inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-RESOURCE-ACCESS]"
    fi
else
    warn "Could not locate PATCH-FEISHU-RESOURCE-ACCESS files"
fi

# PATCH-DOCUMENT-EXTRACTION: trusted PDF/HTML/Office/OpenDocument parsing before
# content reaches a sandboxed group agent. XLSX/DOCX/IPYNB extraction and its
# read_file wiring were absorbed upstream (read_extract.py + file_tools.py at
# 26e0b1c); the local remainder is the extra formats, the gateway inbound
# extraction wiring, and the pypdf dependency pins.
READ_EXTRACT_PY="${HERMES_AGENT}/tools/read_extract.py"
READ_EXTRACT_TEST_PY="${HERMES_AGENT}/tests/tools/test_read_extract.py"
DOCUMENT_CONTEXT_TEST_PY="${HERMES_AGENT}/tests/gateway/test_document_context_note.py"
if [[ -f "${GATEWAY_RUN_PY}" && -f "${READ_EXTRACT_PY}" && -f "${READ_EXTRACT_TEST_PY}" && -f "${DOCUMENT_CONTEXT_TEST_PY}" && -f "${PYPROJECT}" && -f "${LAZY_DEPS_PY}" ]]; then
    if grep -q 'def _extract_inbound_document' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'def _extract_pdf' "${READ_EXTRACT_PY}" 2>/dev/null &&
        grep -q 'def _extract_html_file' "${READ_EXTRACT_PY}" 2>/dev/null &&
        grep -q 'class TestCommonDocumentExtraction' "${READ_EXTRACT_TEST_PY}" 2>/dev/null &&
        grep -q 'test_native_overlap_formats_remain_extractable_without_anydoc' "${READ_EXTRACT_TEST_PY}" 2>/dev/null &&
        grep -q 'test_anydoc_only_formats_not_extractable_without_anydoc' "${READ_EXTRACT_TEST_PY}" 2>/dev/null &&
        grep -q 'test_extract_inbound_html_without_terminal_access' "${DOCUMENT_CONTEXT_TEST_PY}" 2>/dev/null &&
        grep -q 'pypdf==6.14.2' "${PYPROJECT}" 2>/dev/null &&
        grep -q 'pypdf==6.14.2' "${LAZY_DEPS_PY}" 2>/dev/null; then
        ok "PATCH-DOCUMENT-EXTRACTION active: trusted PDF/HTML/Office/OpenDocument readers + inbound wiring"
        _TRUSTED_DOCUMENT_EXTRACTION_PATCH_OK=true
    else
        warn "PATCH-DOCUMENT-EXTRACTION inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-DOCUMENT-EXTRACTION]"
    fi
else
    warn "Could not locate PATCH-DOCUMENT-EXTRACTION files"
fi

# A group @mention can arrive separately from its media. The two contracts above
# deliberately verify acquisition and parsing independently so either can be
# absorbed upstream without masking the other.

# PATCH-FEISHU-MARKDOWN: Feishu outbound markdown full render. post/md cannot render ATX
# headings (`## h`) or block quotes (`> q`), and its CommonMark flanking
# rules reject `**` spans with punctuation just inside + a word char just
# outside (`到**“x”**的`); _build_outbound_payload promotes headings/quotes
# via _promote_block_markdown and rewrites flanking-invalid strong spans via
# _fix_strong_flanking. The former table→bullets sub-branch was retired
# 2026-07-25 after real-client verification of native GFM table rendering
# (upstream #52786). Source + test live in adapter.py /
# tests/gateway/test_feishu.py.
if [[ -f "${FEISHU_PY}" && -f "${FEISHU_TEST_PY}" ]]; then
    if grep -q 'def _promote_block_markdown' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'def _fix_strong_flanking' "${FEISHU_PY}" 2>/dev/null &&
        ! grep -q 'convert_table_to_bullets' "${FEISHU_PY}" 2>/dev/null &&
        grep -q 'test_promote_block_markdown_fixes_strong_flanking' "${FEISHU_TEST_PY}" 2>/dev/null; then
        ok "Feishu markdown render patch: active (ATX heading/quote promoted, strong flanking fixed)"
        _FEISHU_MARKDOWN_PATCH_OK=true
    else
        warn "Feishu markdown render patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-MARKDOWN]"
    fi
else
    warn "Could not locate PATCH-FEISHU-MARKDOWN files"
fi

# PATCH-FEISHU-SSRF-TEST-SYSPROXY: upstream's connect-time rebind SSRF test only
# blanks proxy ENV vars, but httpx trust_env falls back to
# urllib.request.getproxies() = the macOS scutil / Windows registry SYSTEM
# proxy when the env is empty. With a host proxy (Clash etc.) running, the
# request routes through the proxy, the direct-connect guard is bypassed by
# design, and the test fails with a raw ConnectError — the canonical patch
# regression then cannot reach 0 failed. The patch pins the test hermetic by
# also patching httpx._utils.getproxies to {}.
if [[ -f "${FEISHU_TEST_PY}" ]]; then
    if grep -q 'httpx._utils.getproxies' "${FEISHU_TEST_PY}" 2>/dev/null &&
        grep -q 'def test_download_remote_document_blocks_connect_time_rebind' "${FEISHU_TEST_PY}" 2>/dev/null; then
        ok "Feishu SSRF-test sysproxy patch: active (rebind test hermetic to host system proxy)"
        _FEISHU_SSRF_TEST_SYSPROXY_PATCH_OK=true
    else
        warn "Feishu SSRF-test sysproxy patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FEISHU-SSRF-TEST-SYSPROXY]"
    fi
else
    warn "Could not locate PATCH-FEISHU-SSRF-TEST-SYSPROXY files"
fi

# PATCH-VERTEX-HIDDEN-THOUGHTS: Vertex OpenAI-compatible returns include_thoughts output as normal
# assistant content. Keep model-side Gemini thinking level/budget, but force
# include_thoughts=false so Feishu/dashboard only receive the final answer.
# The suppression MUST return single-level {"google": {...}} (merged into
# extra_body) — a double-wrapped {"extra_body": {"google": {...}}} reaches the
# wire as an unknown top-level field Vertex ignores, re-leaking thoughts.
VERTEX_PROVIDER_PY="${HERMES_AGENT}/plugins/model-providers/vertex/__init__.py"
VERTEX_PROVIDER_TEST_PY="${HERMES_AGENT}/tests/hermes_cli/test_vertex_provider.py"
if [[ -f "${VERTEX_PROVIDER_PY}" && -f "${VERTEX_PROVIDER_TEST_PY}" ]]; then
    if grep -q 'include_thoughts=true' "${VERTEX_PROVIDER_PY}" 2>/dev/null &&
        grep -q 'thinking_config\["include_thoughts"\] = False' "${VERTEX_PROVIDER_PY}" 2>/dev/null &&
        grep -q 'return {"google": {"thinking_config": thinking_config}}' "${VERTEX_PROVIDER_PY}" 2>/dev/null &&
        grep -q 'test_vertex_extra_body_preserves_disabled_reasoning' "${VERTEX_PROVIDER_TEST_PY}" 2>/dev/null &&
        grep -q 'test_vertex_transport_build_kwargs_hides_thoughts_on_wire' "${VERTEX_PROVIDER_TEST_PY}" 2>/dev/null; then
        ok "Vertex hidden-thoughts patch: active (single-level extra_body, thought text hidden from content)"
        _VERTEX_THOUGHTS_PATCH_OK=true
    else
        warn "Vertex hidden-thoughts patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-VERTEX-HIDDEN-THOUGHTS]"
    fi
else
    warn "Could not locate PATCH-VERTEX-HIDDEN-THOUGHTS files"
fi

# PATCH-VERTEX-DOCTOR: doctor must understand the official Vertex provider profile and
# Google-style model slugs so `hermes doctor` stays green after switching the
# main model path from the legacy custom endpoint to provider: vertex.
DOCTOR_TEST_PY="${HERMES_AGENT}/tests/hermes_cli/test_doctor.py"
if [[ -f "${DOCTOR_PY}" && -f "${DOCTOR_TEST_PY}" ]]; then
    if grep -q '_get_provider_profile' "${DOCTOR_PY}" 2>/dev/null &&
        grep -q 'GOOGLE_APPLICATION_CREDENTIALS' "${DOCTOR_PY}" 2>/dev/null &&
        grep -q '"vertex"' "${DOCTOR_PY}" 2>/dev/null &&
        grep -q '"vertex-fallback"' "${DOCTOR_PY}" 2>/dev/null &&
        grep -q 'test_run_doctor_accepts_vertex_provider_and_google_model_slugs' "${DOCTOR_TEST_PY}" 2>/dev/null; then
        ok "Vertex doctor patch: active (provider profile + google/* model slug accepted)"
        _VERTEX_DOCTOR_PATCH_OK=true
    else
        warn "Vertex doctor patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-VERTEX-DOCTOR]"
    fi
else
    warn "Could not locate PATCH-VERTEX-DOCTOR files"
fi

# PATCH-VERTEX-FALLBACK: second Vertex account as fallback provider. Same model/profile via a
# distinct SA file + GCP project (VERTEX_FALLBACK_*), wired as provider
# "vertex-fallback" so the fallback chain doesn't dedup it against primary vertex,
# resolve_provider_client() finds it in PROVIDER_REGISTRY, and the gateway's
# resolve_runtime_provider() mints its token instead of falling through to the
# generic tail with an empty api_key (which broke the whole fallback chain).
VERTEX_ADAPTER_PY="${HERMES_AGENT}/agent/vertex_adapter.py"
AUTH_PY="${HERMES_AGENT}/hermes_cli/auth.py"
AUX_CLIENT_PY="${HERMES_AGENT}/agent/auxiliary_client.py"
RUNTIME_PROVIDER_PY="${HERMES_AGENT}/hermes_cli/runtime_provider.py"
if [[ -f "${VERTEX_ADAPTER_PY}" && -f "${AUTH_PY}" && -f "${AUX_CLIENT_PY}" && -f "${VERTEX_PROVIDER_PY}" && -f "${RUNTIME_PROVIDER_PY}" ]]; then
    if grep -q 'def get_vertex_fallback_config' "${VERTEX_ADAPTER_PY}" 2>/dev/null &&
        grep -q 'apply_global_project_override' "${VERTEX_ADAPTER_PY}" 2>/dev/null &&
        grep -q '"vertex-fallback"' "${AUTH_PY}" 2>/dev/null &&
        grep -q 'has_vertex_fallback_credentials' "${AUX_CLIENT_PY}" 2>/dev/null &&
        grep -q 'name="vertex-fallback"' "${VERTEX_PROVIDER_PY}" 2>/dev/null &&
        grep -q '"vertex-fallback", "vertex2", "vertex-secondary"' "${RUNTIME_PROVIDER_PY}" 2>/dev/null &&
        grep -q 'test_resolve_runtime_provider_vertex_fallback_mints_token' "${VERTEX_PROVIDER_TEST_PY}" 2>/dev/null &&
        grep -q 'test_resolve_provider_client_alias_mints_fallback_credentials' "${VERTEX_PROVIDER_TEST_PY}" 2>/dev/null &&
        grep -q 'test_vertex_fallback_profile_registered' "${VERTEX_PROVIDER_TEST_PY}" 2>/dev/null; then
        ok "Vertex fallback provider patch: active (vertex-fallback = 2nd account, quota failover)"
        _VERTEX_FALLBACK_PATCH_OK=true
    else
        warn "Vertex fallback provider patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-VERTEX-FALLBACK]"
    fi
else
    warn "Could not locate PATCH-VERTEX-FALLBACK files"
fi

# PATCH-VERTEX-IMAGE-ROUTING: Vertex Gemini 3.x is vision-capable even when the
# dynamic model catalog has not learned a preview slug yet.
IMAGE_ROUTING_PY="${HERMES_AGENT}/agent/image_routing.py"
IMAGE_ROUTING_TEST_PY="${HERMES_AGENT}/tests/agent/test_image_routing.py"
IMAGE_ROUTING_RUNTIME_TEST_PY="${HERMES_AGENT}/tests/gateway/test_image_input_routing_runtime.py"
GATEWAY_RUN_PY="${HERMES_AGENT}/gateway/run.py"
if [[ -f "${IMAGE_ROUTING_PY}" && -f "${IMAGE_ROUTING_TEST_PY}" ]]; then
    if grep -q 'def _known_provider_model_supports_vision' "${IMAGE_ROUTING_PY}" 2>/dev/null &&
        grep -q '"vertex-fallback"' "${IMAGE_ROUTING_PY}" 2>/dev/null &&
        grep -q 'gemini-3.1-pro-preview' "${IMAGE_ROUTING_TEST_PY}" 2>/dev/null &&
        grep -q 'test_auto_native_for_vertex_gemini_3_preview_without_catalog_entry' "${IMAGE_ROUTING_TEST_PY}" 2>/dev/null; then
        ok "PATCH-VERTEX-IMAGE-ROUTING active: Gemini 3.x images route natively"
        _VERTEX_IMAGE_ROUTING_PATCH_OK=true
    else
        warn "PATCH-VERTEX-IMAGE-ROUTING inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-VERTEX-IMAGE-ROUTING]"
    fi
else
    warn "Could not locate PATCH-VERTEX-IMAGE-ROUTING files"
fi

# PATCH-VERTEX-VIDEO-ROUTING: user videos use native data-URI parts and bounded
# gateway buffering instead of relying on terminal/ffprobe access.
if [[ -f "${IMAGE_ROUTING_PY}" && -f "${IMAGE_ROUTING_TEST_PY}" && -f "${IMAGE_ROUTING_RUNTIME_TEST_PY}" && -f "${GATEWAY_RUN_PY}" ]]; then
    if grep -q 'def decide_video_input_mode' "${IMAGE_ROUTING_PY}" 2>/dev/null &&
        grep -q '_pending_native_video_paths_by_session' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'return decide_video_input_mode(' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q '_consume_pending_native_video_paths(session_key)' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'test_auto_text_for_non_video_capable_models' "${IMAGE_ROUTING_TEST_PY}" 2>/dev/null &&
        grep -q 'test_gateway_kind_video_routes_through_video_decision_table' "${IMAGE_ROUTING_RUNTIME_TEST_PY}" 2>/dev/null &&
        grep -q 'test_prepare_resets_stale_video_buffer_per_turn' "${IMAGE_ROUTING_RUNTIME_TEST_PY}" 2>/dev/null &&
        grep -q 'test_video_attached_as_data_url_part' "${IMAGE_ROUTING_TEST_PY}" 2>/dev/null; then
        ok "PATCH-VERTEX-VIDEO-ROUTING active: Gemini videos route natively"
        _VERTEX_VIDEO_ROUTING_PATCH_OK=true
    else
        warn "PATCH-VERTEX-VIDEO-ROUTING inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-VERTEX-VIDEO-ROUTING]"
    fi
else
    warn "Could not locate PATCH-VERTEX-VIDEO-ROUTING files"
fi

# PATCH-HISTORY-RETENTION: replay-history retention window (time + count) for shared group
# sessions. Bounds what the MODEL sees per turn (view-level; state.db keeps
# the full transcript) so days-old injected instruction blocks stop steering
# later turns. Config: gateway.history_retention.<platform-key> in config.yaml.
REPLAY_CLEANUP_PY="${HERMES_AGENT}/agent/replay_cleanup.py"
REPLAY_CLEANUP_TEST_PY="${HERMES_AGENT}/tests/agent/test_replay_cleanup.py"
HISTORY_RETENTION_TEST_PY="${HERMES_AGENT}/tests/gateway/test_stale_confirmation_expiry.py"
GATEWAY_RUN_PY="${HERMES_AGENT}/gateway/run.py"
if [[ -f "${REPLAY_CLEANUP_PY}" && -f "${REPLAY_CLEANUP_TEST_PY}" && -f "${GATEWAY_RUN_PY}" ]]; then
    if grep -q 'def apply_history_retention' "${REPLAY_CLEANUP_PY}" 2>/dev/null &&
        grep -q 'def _retention_turn_starts' "${REPLAY_CLEANUP_PY}" 2>/dev/null &&
        grep -q '_history_retention_limits_for_source' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q '_apply_history_retention' "${GATEWAY_RUN_PY}" 2>/dev/null &&
        grep -q 'test_retention_never_splits_tool_call_blocks' "${REPLAY_CLEANUP_TEST_PY}" 2>/dev/null &&
        grep -q 'test_retention_newest_turn_always_kept_even_if_too_old' "${REPLAY_CLEANUP_TEST_PY}" 2>/dev/null &&
        [[ -f "${HISTORY_RETENTION_TEST_PY}" ]] &&
        grep -q 'test_retention_feishu_dm_not_covered_by_group_key' "${HISTORY_RETENTION_TEST_PY}" 2>/dev/null; then
        ok "History retention patch: active (per-platform time+count replay window, turn-boundary safe)"
        _HISTORY_RETENTION_PATCH_OK=true
    else
        warn "History retention patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-HISTORY-RETENTION]"
    fi
else
    warn "Could not locate PATCH-HISTORY-RETENTION files"
fi

# PATCH-APPROVAL-DARWIN-TMP: approval temp-cleanup exemption on Darwin. Upstream 0c8bcd339's
# _is_verification_artifact_cleanup realpath()s the temp dir but not the
# operand, so on Darwin (/tmp -> /private/tmp, /var/folders ->
# /private/var/folders) the runtime's own `rm -f` verify-artifact cleanup
# never matches and always walks the approval flow. The patch accepts the
# raw spelling only for the exact /private system alias; any other
# symlinked temp dir stays non-exempt (fail-closed). Retire when upstream
# normalizes both sides of the comparison.
if [[ -f "${APPROVAL_PY}" && -f "${APPROVAL_TEST_PY}" ]]; then
    if grep -q 'f"/private{raw_temp_dir}"' "${APPROVAL_PY}" 2>/dev/null &&
        grep -q 'allowed_spellings' "${APPROVAL_PY}" 2>/dev/null &&
        grep -q 'test_darwin_private_alias_accepts_raw_temp_spelling' "${APPROVAL_TEST_PY}" 2>/dev/null; then
        ok "Approval temp-cleanup Darwin alias patch: active (raw /private-alias spelling exempt, other symlinks fail-closed)"
        _APPROVAL_TEMP_CLEANUP_PATCH_OK=true
    else
        warn "Approval temp-cleanup Darwin alias patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-APPROVAL-DARWIN-TMP]"
    fi
else
    warn "Could not locate approval files — skipping temp-cleanup patch check"
fi

# PATCH-FTS5-CJK-DARWIN: fts5_cjk extension build on Darwin. Upstream build.sh (PR #65544)
# links with bare `gcc -shared`, which macOS rejects (unresolved sqlite3_*
# symbols), and Apple's SDK sqlite3ext.h leaves several sqlite3_* calls as
# direct symbol references — against the uv-managed CPython (static SQLite,
# no exported sqlite3_* symbols) the loaded extension segfaults. The patch
# forces the vendored amalgamation headers + `-undefined dynamic_lookup` on
# Darwin. The built artifact lives at ~/.hermes/lib/libfts5_cjk.so and
# survives updates; rebuild only needed when upstream changes fts5_cjk.c.
FTS5_CJK_BUILD_SH="${HERMES_AGENT}/native/fts5_cjk/build.sh"
if [[ -f "${FTS5_CJK_BUILD_SH}" ]]; then
    # Anchor the Darwin branch itself: bare upstream already contains a
    # conditional -Ivendor fallback, so "Ivendor exists" cannot discriminate.
    # The patch's invariant is "on Darwin, vendored headers are FORCED and the
    # link defers sqlite3_* resolution" — assert both branch tokens together.
    if grep -q 'uname -s.*Darwin' "${FTS5_CJK_BUILD_SH}" 2>/dev/null &&
        grep -q 'LDFLAGS_EXTRA="-undefined dynamic_lookup"' "${FTS5_CJK_BUILD_SH}" 2>/dev/null &&
        grep -q 'CFLAGS_EXTRA="-Ivendor"' "${FTS5_CJK_BUILD_SH}" 2>/dev/null &&
        grep -q 'o libfts5_cjk.so \$LDFLAGS_EXTRA' "${FTS5_CJK_BUILD_SH}" 2>/dev/null; then
        if [[ -f "${HERMES_HOME}/lib/libfts5_cjk.so" ]]; then
            ok "fts5_cjk Darwin build patch: active (vendored headers + dynamic_lookup; extension installed)"
        else
            ok "fts5_cjk Darwin build patch: active (extension not built — run native/fts5_cjk/build.sh to enable CJK search index)"
        fi
        _FTS5_CJK_BUILD_PATCH_OK=true
    else
        warn "fts5_cjk Darwin build patch inactive or partial"
        add_act "Re-apply: see PATCHES.md § [PATCH-FTS5-CJK-DARWIN]"
    fi
else
    warn "Could not locate native/fts5_cjk/build.sh — skipping fts5_cjk build patch check"
fi

# -- 8c. Refresh saved diff only after full verification -----------------------
# PATCH-REPLAY-BUNDLE-FULL-INDEX + PATCH-UPDATE-GATE-EXIT-STATUS
# Regenerating the diff captures any upstream changes that touched our patched
# files but did not conflict. Only do this once ALL patches are confirmed live
# and the patched files are conflict-marker-free. The canonical bundle/base are
# replaced only after exact managed-file coverage plus byte/cached/reverse replay
# checks all pass.
if $_PATCH_APPLY_OK && $_ARCHIVED_DOCTOR_TOOLSETS_OK && $_ARCHIVED_DASHBOARD_BUILD_CACHE_OK && $_ARCHIVED_DELEGATE_ACP_ROUTING_OK && $_ARCHIVED_GEMINI_THOUGHT_SIGNATURE_OK && $_ARCHIVED_LAZY_ACTIVE_ANCHOR_OK && $_SKILL_PATCH_OK && $_FEISHU_DEPS_PATCH_OK && $_OPENCLAW_GATEWAY_TOKEN_PATCH_OK && $_FEISHU_GROUP_ADMISSION_PATCH_OK && $_FEISHU_MISSED_EVENT_BACKFILL_PATCH_OK && $_FEISHU_GROUP_SCOPE_PATCH_OK && $_PLATFORM_CAPABILITY_SCOPE_PATCH_OK && $_FEISHU_GROUP_APPROVAL_FLOOR_PATCH_OK && $_FEISHU_NO_THREAD_PATCH_OK && $_FEISHU_FINAL_ONLY_PATCH_OK && $_PEOPLE_PROFILE_PATCH_OK && $_FEISHU_RESOURCE_ACCESS_PATCH_OK && $_TRUSTED_DOCUMENT_EXTRACTION_PATCH_OK && $_FEISHU_MARKDOWN_PATCH_OK && $_FEISHU_SSRF_TEST_SYSPROXY_PATCH_OK && $_VERTEX_THOUGHTS_PATCH_OK && $_VERTEX_DOCTOR_PATCH_OK && $_VERTEX_FALLBACK_PATCH_OK && $_VERTEX_IMAGE_ROUTING_PATCH_OK && $_VERTEX_VIDEO_ROUTING_PATCH_OK && $_HISTORY_RETENTION_PATCH_OK && $_APPROVAL_TEMP_CLEANUP_PATCH_OK && $_FTS5_CJK_BUILD_PATCH_OK; then
    cd "${HERMES_AGENT}"
    if _has_conflict_markers "${PATCHED_FILES[@]}"; then
        warn "Patched files contain conflict markers — skipping diff refresh"
        add_warn "patches/local-patches.diff was NOT refreshed because patched files are not clean"
        add_act "Inspect patched files: cd ${HERMES_AGENT} && grep -rnE '^(<{7}|={7}|>{7})' ${PATCHED_FILES[*]}"
        FINAL_RC=1
    else
        _REFRESHED=()
        _UNCHANGED_MANAGED=()
        for _f in "${PATCHED_FILES[@]}"; do
            if ! git --no-pager diff --quiet HEAD -- "${_f}" 2>/dev/null; then
                _REFRESHED+=("${_f}")
            else
                _UNCHANGED_MANAGED+=("${_f}")
            fi
        done
        if [[ ${#_REFRESHED[@]} -eq 0 && -f "${PATCH_FILE}" ]]; then
            # All patches are now upstream — diff is empty but file still exists.
            note "All patched files match upstream HEAD — patches may have been absorbed"
            note "Review PATCHED_FILES list and PATCHES.md for stale entries"
            add_act "If patches are fully upstream, prune PATCHED_FILES in hermes-update.sh and PATCHES.md"
            FINAL_RC=1
        elif [[ ${#_UNCHANGED_MANAGED[@]} -gt 0 ]]; then
            warn "Replay coverage is partial: ${#_REFRESHED[@]}/${#PATCHED_FILES[@]} managed files differ from HEAD"
            for _f in "${_UNCHANGED_MANAGED[@]}"; do
                add_warn "Managed path has no live diff: ${_f}"
            done
            add_act "Classify each zero-diff path as absorbed, stale, or missing; update PATCHED_FILES/PATCHES.md before refreshing the bundle"
            FINAL_RC=1
        elif [[ ${#_REFRESHED[@]} -gt 0 ]]; then
            _REPLAY_VERIFY_OK=false
            if git --no-pager diff --full-index HEAD -- "${_REFRESHED[@]}" >"${PATCH_FILE}.tmp" &&
                _bundle_matches_patched_files "${PATCH_FILE}.tmp" &&
                ! grep -nE '^\+?(<<<<<<<|=======|>>>>>>>)' "${PATCH_FILE}.tmp" >/dev/null 2>&1 &&
                git diff --cached --quiet &&
                git apply --cached --check "${PATCH_FILE}.tmp" 2>/dev/null &&
                git diff --cached --quiet &&
                git apply --check --reverse "${PATCH_FILE}.tmp" 2>/dev/null &&
                cmp -s "${PATCH_FILE}.tmp" <(git --no-pager diff --full-index HEAD -- "${PATCHED_FILES[@]}"); then
                _REPLAY_VERIFY_OK=true
            fi

            if $_REPLAY_VERIFY_OK; then
                # Record upstream base provenance only after the physical
                # bundle has passed every replay gate. Both files use temp+
                # rename so an interrupted write is detectable and recoverable.
                if mv -f "${PATCH_FILE}.tmp" "${PATCH_FILE}" &&
                    printf '%s %s\n' "$(git rev-parse HEAD)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
                        >"${PATCHES_DIR}/.local-patches.base.tmp" &&
                    mv -f "${PATCHES_DIR}/.local-patches.base.tmp" "${PATCHES_DIR}/.local-patches.base"; then
                    ok "patches/local-patches.diff refreshed and replay-verified (${#_REFRESHED[@]} file(s))"
                else
                    rm -f -- "${PATCH_FILE}.tmp" "${PATCHES_DIR}/.local-patches.base.tmp"
                    fail "Could not atomically publish replay bundle provenance"
                    add_act "Check patches/ permissions and reconcile bundle/base before rerunning"
                    FINAL_RC=1
                fi
            else
                rm -f -- "${PATCH_FILE}.tmp"
                fail "Replay bundle failed byte/cached/reverse integrity checks — canonical bundle/base preserved"
                add_act "Inspect managed paths and index, repair the overlay, then run: bash ${HERMES_HOME}/hermes-update.sh --reconcile"
                FINAL_RC=1
            fi
        fi
    fi
    cd - >/dev/null
else
    fail "Patch apply or invariant gate failed"
    add_warn "Replay bundle was not refreshed because one or more engineering patch gates failed"
    add_act "Resolve the PATCH warnings above, then run: bash ${HERMES_HOME}/hermes-update.sh --reconcile"
    FINAL_RC=1
fi

# The full bundled-skill mirror in step 4b runs before local patches are
# re-applied. Re-seed llm-wiki from the now-patched bundled source and rebuild
# its manifest baseline so a future startup/update does not classify this
# maintained patch as an ad-hoc user edit or restore the old ~/wiki guidance.
if $_PATCH_APPLY_OK && $_FEISHU_GROUP_ADMISSION_PATCH_OK && [[ -f "${LLM_WIKI_SKILL_MD}" ]]; then
    step "Syncing patched llm-wiki skill"
    set +e
    _LLM_WIKI_RESET_OUT=$(hermes skills reset llm-wiki --restore --yes 2>&1)
    _LLM_WIKI_RESET_RC=$?
    set -e
    if [[ ${_LLM_WIKI_RESET_RC} -eq 0 ]] &&
        cmp -s "${LLM_WIKI_SKILL_MD}" "${LOCAL_SKILLS_DIR}/research/llm-wiki/SKILL.md"; then
        ok "Patched llm-wiki synced and manifest re-baselined"
    else
        warn "Could not sync patched llm-wiki into the runtime skills mirror"
        if [[ -n "${_LLM_WIKI_RESET_OUT:-}" ]]; then
            add_warn "llm-wiki reset output: ${_LLM_WIKI_RESET_OUT//$'\n'/ | }"
        fi
        add_act "Run: hermes skills reset llm-wiki --restore --yes"
        FINAL_RC=1
    fi
fi

# ── 8d. Gateway restart (PATCH-UPDATE-GATE-EXIT-STATUS) ──────────────────────
# A real upstream advance restarts the gateway before patches are re-applied;
# a changed local overlay can likewise make the current process stale. Persist
# runtime_dirty across failures and restart only when that evidence says a
# reload is required. A no-change --reconcile is therefore genuinely idempotent:
# no fetch, no pull, and no synthetic PID churn.
if $_PATCH_APPLY_OK && [[ "${_TX_RUNTIME_DIRTY}" == "1" ]]; then
    set +e
    _GW_OLD_PID=$(gw_pid)
    if [[ -n "${_GW_OLD_PID:-}" ]]; then
        _GW_RESTART_WAIT=$(gw_restart_wait_seconds)
        if [[ ! "${_GW_RESTART_WAIT}" =~ ^[0-9]+$ ]]; then
            _GW_RESTART_WAIT=930 # keep in sync with gw_restart_wait_seconds fallback
        fi
        step "Restarting gateway after draining in-flight runs (up to ${_GW_RESTART_WAIT}s)"
        hermes gateway restart
        _GW_RESTART_RC=$?
        _GW_NEW_PID=""
        _GW_WAITED=0
        while [[ ${_GW_RESTART_RC} -eq 0 && ${_GW_WAITED} -lt ${_GW_RESTART_WAIT} ]]; do
            sleep 1
            _GW_WAITED=$((_GW_WAITED + 1))
            _GW_NEW_PID=$(gw_pid)
            if [[ -n "${_GW_NEW_PID:-}" && "${_GW_NEW_PID}" != "${_GW_OLD_PID}" ]]; then
                break
            fi
        done
        if [[ ${_GW_RESTART_RC} -eq 0 && -n "${_GW_NEW_PID:-}" && "${_GW_NEW_PID}" != "${_GW_OLD_PID}" ]]; then
            ok "Gateway restarted — patched modules now active (PID ${_GW_OLD_PID} → ${_GW_NEW_PID})"
            _TX_RUNTIME_DIRTY="0"
            _write_transaction
        else
            warn "Gateway did not complete a drain-aware replacement (old PID ${_GW_OLD_PID}, current ${_GW_NEW_PID:-none})"
            if [[ ${_GW_RESTART_RC} -ne 0 ]]; then
                add_warn "gateway restart exited ${_GW_RESTART_RC}"
            fi
            add_act "Inspect in-flight work and gateway logs, then rerun: hermes gateway restart (the replacement PID must differ from ${_GW_OLD_PID})"
            FINAL_RC=1
        fi
    else
        # runtime_dirty with no running gateway: the dirty runtime cannot be
        # verified as replaced. Keep the flag and fail the transaction rather
        # than silently skipping the reload evidence.
        warn "Runtime is dirty but no gateway PID found — patched modules not verified as loaded"
        add_act "Start the gateway (hermes gateway start), then rerun: bash ~/.hermes/hermes-update.sh --reconcile"
        FINAL_RC=1
    fi
    set -e
elif $_PATCH_APPLY_OK; then
    note "Gateway restart skipped — pinned HEAD and patch overlay did not change"
fi

# ── 8e. Verify user plugins ──────────────────────────────────────────────────
# User plugins under ~/.hermes/plugins/ are owned by THIS config repo, not
# upstream hermes-agent. They hook into upstream APIs (VALID_HOOKS, fire
# sites in gateway/run.py + model_tools.py). After an upstream update, run
# each plugin's verify.sh to confirm the contract still holds — if upstream
# renames a hook or changes kwargs, the plugin will silently no-op until
# patched.
#
# Currently active plugins:
#   - PATCH-FEISHU-GROUP-SANDBOX
#     sandbox (per-chat Feishu capability boundary; see README § 用户插件)
#
# Add new plugins here by appending another conditional block.
PLUGIN_VERIFIERS=("${HERMES_HOME}/plugins/sandbox/verify.sh")
for verifier in "${PLUGIN_VERIFIERS[@]}"; do
    plugin_name=$(basename "$(dirname "${verifier}")")
    step "Verifying user plugin: ${plugin_name}"
    if [[ ! -f "${verifier}" ]]; then
        fail "${plugin_name} verifier is missing: ${verifier}"
        add_act "Restore plugins/${plugin_name}/verify.sh from the config repository before using the upgraded gateway"
        FINAL_RC=1
        continue
    fi
    if [[ ! -x "${verifier}" ]]; then
        fail "${plugin_name} verifier is not executable: ${verifier}"
        add_act "Restore its executable bit: chmod +x ${verifier}"
        FINAL_RC=1
        continue
    fi

    set +e
    _PV_OUT=$(bash "${verifier}" 2>&1)
    _PV_RC=$?
    set -e
    echo "${_PV_OUT}"
    if [[ ${_PV_RC} -eq 0 ]]; then
        ok "${plugin_name} compatibility OK"
    else
        fail "${plugin_name} compatibility check failed"
        add_act "Inspect ${verifier} output and repair plugins/${plugin_name}/, config.yaml, or the upstream hook/toolset integration"
        FINAL_RC=1
    fi
done

# ── 9. Verify ─────────────────────────────────────────────────────────────────
step "Verifying"
echo ""

POST_VERSION=$(_local_version)
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
    _DOCTOR_ISSUES=$(printf '%s\n' "$DOCTOR_OUT" | sed -n '/Found [0-9][0-9]* issue(s) to address:/,/Tip:/p' | grep -E '^[[:space:]]+[0-9]+\. ' || true)
    if [[ -n "$_DOCTOR_ISSUES" ]] &&
        ! printf '%s\n' "$_DOCTOR_ISSUES" | grep -Ev 'Browser tools \(agent-browser\) has [0-9]+ npm vulnerabilit(y|ies)|web workspace has [0-9]+ npm vulnerabilit(y|ies)|ui-tui workspace has [0-9]+ npm vulnerabilit(y|ies)' >/dev/null &&
        ! printf '%s\n' "$DOCTOR_OUT" | grep -Eq '[1-9][0-9]* critical'; then
        add_act "Classified: residual npm workspace/tooling advisories are P2 upstream lock/range blockers; report only, do not use --force"
    else
        add_act "hermes doctor found unclassified or locally fixable issues — run: hermes doctor --fix"
    fi
fi
echo ""

GW_FINAL=$(hermes gateway status 2>&1)
echo "$GW_FINAL"
if gw_running; then
    ok "Gateway is running"
else
    note "Gateway not running after verification — attempting one automatic recovery..."
    set +e
    if echo "$GW_FINAL" | grep -q 'not loaded'; then
        hermes gateway install --force >/dev/null 2>&1
    fi
    _GW_FINAL_RECOVER_OUT=$(hermes gateway start 2>&1)
    _GW_FINAL_RECOVER_RC=$?
    for _ in {1..12}; do
        sleep 1
        if gw_running; then
            break
        fi
    done
    set -e
    if gw_running; then
        ok "Gateway recovered after final restart"
    else
        fail "Gateway is not running"
        if [[ -n "${_GW_FINAL_RECOVER_OUT:-}" ]]; then
            add_warn "final gateway restart output: ${_GW_FINAL_RECOVER_OUT//$'\n'/ | }"
        elif [[ ${_GW_FINAL_RECOVER_RC:-0} -ne 0 ]]; then
            add_warn "final gateway restart exited ${_GW_FINAL_RECOVER_RC}"
        fi
        add_act "Start gateway: hermes gateway start  (diagnose: hermes logs)"
        FINAL_RC=1
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
printf '%s══════════════════════════════════════════════%s\n' "${BOLD}" "${NC}"
printf '%s  Hermes update — done%s\n' "${BOLD}" "${NC}"
printf '%s══════════════════════════════════════════════%s\n' "${BOLD}" "${NC}"
echo ""

if [[ ${#WARNS[@]} -gt 0 ]]; then
    printf '%sWarnings:%s\n' "${YLW}" "${NC}"
    for w in "${WARNS[@]}"; do printf "  • %s\n" "$w"; done
    echo ""
fi

if [[ ${#ACTS[@]} -gt 0 ]]; then
    printf '%sRecommended actions:%s\n' "${YLW}" "${NC}"
    for a in "${ACTS[@]}"; do printf "  → %s\n" "$a"; done
else
    printf '%s✓ All systems nominal — no further action required.%s\n' "${GRN}" "${NC}"
fi

echo ""
printf '  Gateway:   %shermes gateway status%s\n' "${BOLD}" "${NC}"
printf '  Logs:      %shermes logs%s\n' "${BOLD}" "${NC}"
printf '  Health:    %shermes doctor%s\n' "${BOLD}" "${NC}"
printf '  Dashboard: %shermes dashboard%s\n' "${BOLD}" "${NC}"
echo ""

exit $FINAL_RC
