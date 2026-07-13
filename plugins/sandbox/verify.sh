#!/usr/bin/env bash
# Sanity-check the sandbox plugin against the currently installed hermes-agent.
#
# Designed to be invoked by hermes-update.sh (step 8e) after an upstream
# update, and runnable standalone any time:
#
#   bash ~/.hermes/plugins/sandbox/verify.sh
#
# What it checks (in order, cheapest first):
#   1. Upstream VALID_HOOKS still declares both hook names we depend on
#      (pre_gateway_dispatch, pre_tool_call). HARD FAIL if missing — the
#      plugin's register() will be a no-op when the hook name is gone.
#   2. Fire sites for both hooks still exist in upstream source. SOFT WARN
#      if the line moves to a different file — the plugin keeps working as
#      long as something fires them, but a missing fire site means the
#      contract is broken.
#   3. Runtime trace: the latest "sandbox: registered" log line in
#      agent.log should report active=True. HARD FAIL if active=False
#      (config drift). WARN if missing entirely (gateway hasn't restarted
#      since plugin install).
#   4. Group wiki contract: read_file/search_files and ~/.hermes/wiki remain
#      explicitly allowlisted, with a recovery hint for wrong paths.
#
# Exit code: 0 = all good, 1 = at least one hard failure.

set -u

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"
PLUGINS_SRC="${HERMES_AGENT}/hermes_cli/plugins.py"
GATEWAY_RUN="${HERMES_AGENT}/gateway/run.py"
MODEL_TOOLS="${HERMES_AGENT}/model_tools.py"
AGENT_LOG="${HERMES_HOME}/logs/agent.log"
PLUGIN_CONFIG="${HERMES_HOME}/plugins/sandbox/config.yaml"

fail=0

echo "=== sandbox plugin compatibility check ==="

# 1. VALID_HOOKS membership (HARD)
for hook in pre_gateway_dispatch pre_tool_call; do
    if [[ -r "${PLUGINS_SRC}" ]] && grep -qF "\"${hook}\"" "${PLUGINS_SRC}"; then
        echo "OK   ${hook} is in VALID_HOOKS"
    else
        echo "FAIL ${hook} NOT in VALID_HOOKS at ${PLUGINS_SRC}"
        echo "     Upstream may have renamed/removed it; check git log and update __init__.py."
        fail=1
    fi
done

# 2. Fire-site presence (SOFT)
if [[ -r "${GATEWAY_RUN}" ]] && grep -q 'pre_gateway_dispatch' "${GATEWAY_RUN}"; then
    echo "OK   pre_gateway_dispatch fired from gateway/run.py"
else
    echo "WARN pre_gateway_dispatch fire site not found in gateway/run.py — may have moved"
fi
if [[ -r "${MODEL_TOOLS}" ]] && grep -q 'pre_tool_call' "${MODEL_TOOLS}"; then
    echo "OK   pre_tool_call fired from model_tools.py"
else
    echo "WARN pre_tool_call fire site not found in model_tools.py — may have moved"
fi

# 3. Runtime trace (HARD when active=False, SOFT when missing)
if [[ -r "${AGENT_LOG}" ]]; then
    last_reg=$(grep "sandbox: registered" "${AGENT_LOG}" | tail -1 || true)
    if [[ -z "${last_reg}" ]]; then
        echo "WARN no 'sandbox: registered' trace in agent.log"
        echo "     Run 'hermes plugins enable sandbox && hermes gateway restart' and re-check."
    elif echo "${last_reg}" | grep -q 'active=True'; then
        # Strip the date+level prefix for readability.
        msg="${last_reg##*INFO }"
        echo "OK   runtime: ${msg}"
    else
        echo "FAIL plugin loaded but inactive: ${last_reg}"
        echo "     Check plugins/sandbox/config.yaml: owner_feishu_chat_ids must be a non-empty list."
        fail=1
    fi
else
    echo "WARN agent.log not readable at ${AGENT_LOG}"
fi

# 4. Group wiki allowlist contract (HARD)
if [[ -r "${PLUGIN_CONFIG}" ]] &&
    grep -qF '  - read_file' "${PLUGIN_CONFIG}" &&
    grep -qF '  - search_files' "${PLUGIN_CONFIG}" &&
    grep -qF '  - ~/.hermes/wiki' "${PLUGIN_CONFIG}" &&
    grep -qF 'read_root_block_message:' "${PLUGIN_CONFIG}"; then
    echo "OK   group wiki read contract is explicit in sandbox config"
else
    echo "FAIL group wiki read contract is missing or partial at ${PLUGIN_CONFIG}"
    echo "     Keep read_file/search_files scoped to ~/.hermes/wiki and preserve the recovery hint."
    fail=1
fi

if ((fail)); then
    echo "=== sandbox check: FAIL ==="
    exit 1
fi
echo "=== sandbox check: OK ==="
