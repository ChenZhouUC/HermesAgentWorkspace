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
#   2. Fire sites for both hooks still exist in upstream source.
#   3. Structured tool registration remains available upstream.
#   4. Root/plugin YAML keeps the owner-DM and group capability contracts,
#      fixed script map, and manual approval posture.
#   5. Real platform toolset resolution keeps owner Feishu DMs unrestricted
#      while Feishu groups receive only the reviewed structured surface.
#   6. The plugin regression tests pass.
#   7. The current gateway PID's runtime trace reports active=True and the new
#      structured tools.
#
# Exit code: 0 = all good, 1 = at least one hard failure.

set -u

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"
PLUGINS_SRC="${HERMES_AGENT}/hermes_cli/plugins.py"
GATEWAY_RUN="${HERMES_AGENT}/gateway/run.py"
MODEL_TOOLS="${HERMES_AGENT}/model_tools.py"
AGENT_LOG="${HERMES_HOME}/logs/agent.log"
ROOT_CONFIG="${HERMES_HOME}/config.yaml"
PLUGIN_CONFIG="${HERMES_HOME}/plugins/sandbox/config.yaml"
PLUGIN_TEST="${HERMES_HOME}/plugins/sandbox/test_sandbox.py"
VENV_PYTHON="${HERMES_AGENT}/venv/bin/python"

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

# 2. Fire-site presence (HARD)
if [[ -r "${GATEWAY_RUN}" ]] && grep -q 'pre_gateway_dispatch' "${GATEWAY_RUN}"; then
    echo "OK   pre_gateway_dispatch fired from gateway/run.py"
else
    echo "FAIL pre_gateway_dispatch fire site not found in gateway/run.py"
    fail=1
fi
if [[ -r "${MODEL_TOOLS}" ]] && grep -q 'pre_tool_call' "${MODEL_TOOLS}"; then
    echo "OK   pre_tool_call fired from model_tools.py"
else
    echo "FAIL pre_tool_call fire site not found in model_tools.py"
    fail=1
fi

# 3. Plugin tool registration API (HARD)
if [[ -r "${PLUGINS_SRC}" ]] && grep -q 'def register_tool(' "${PLUGINS_SRC}"; then
    echo "OK   PluginContext.register_tool is available"
else
    echo "FAIL PluginContext.register_tool is missing at ${PLUGINS_SRC}"
    fail=1
fi

# 4. Root/plugin configuration contract (HARD)
if [[ -x "${VENV_PYTHON}" ]] && [[ -r "${ROOT_CONFIG}" ]] && [[ -r "${PLUGIN_CONFIG}" ]] &&
    "${VENV_PYTHON}" - "${ROOT_CONFIG}" "${PLUGIN_CONFIG}" <<'PY'; then
import re
import sys
import plistlib
from pathlib import Path

import yaml

root_path = Path(sys.argv[1])
plugin_path = Path(sys.argv[2])
root = yaml.safe_load(root_path.read_text(encoding="utf-8")) or {}
plugin = yaml.safe_load(plugin_path.read_text(encoding="utf-8")) or {}

expected_group_toolsets = {
    "web",
    "clarify",
    "feishu_doc",
    "skills_readonly",
    "file_readonly",
    "sandbox_group",
}
platform_toolsets = root.get("platform_toolsets") or {}
assert set(platform_toolsets.get("feishu_group") or []) == expected_group_toolsets
assert "feishu" not in platform_toolsets, "owner Feishu DM must keep the platform default toolsets"
assert (root.get("platform_toolset_options") or {}).get("feishu_group", {}).get(
    "recover_platform_tools"
) is False
for platform in ("cli", "feishu", "feishu_group"):
    assert "sandbox_group" in set((root.get("known_plugin_toolsets") or {}).get(platform) or [])

# Group-readable skills are an explicit, verified allowlist — never inferred.
# excel-processing (2026-08-12) is read-only knowledge: its scripts/ cannot be
# executed from a group (no terminal/process/code_execution in the group
# toolset, and feishu_doc_manage only maps fixed actions under
# feishu_doc_scripts_root), so admitting it does NOT widen the tool surface.
assert (root.get("skills") or {}).get("platform_allowed", {}).get("feishu_group") == [
    "llm-wiki",
    "feishu-docs",
    "excel-processing",
]
assert (root.get("approvals") or {}).get("mode") == "manual"
assert root.get("command_allowlist") == []
assert "sandbox" in set((root.get("plugins") or {}).get("enabled") or [])
feishu = root.get("feishu") or {}
assert feishu.get("default_group_policy") == "open"
assert feishu.get("require_mention") is True

gateway_plist = Path.home() / "Library/LaunchAgents/ai.hermes.gateway.plist"
assert gateway_plist.is_file(), f"gateway launchd plist is missing: {gateway_plist}"
plist = plistlib.loads(gateway_plist.read_bytes())
program_args = [str(item).lower() for item in plist.get("ProgramArguments", [])]
launch_env = {
    str(key).upper(): str(value).lower()
    for key, value in (plist.get("EnvironmentVariables") or {}).items()
}
assert "--yolo" not in program_args
assert not any(
    "YOLO" in key and value in {"1", "true", "yes", "on"}
    for key, value in launch_env.items()
)

assert plugin.get("owner_feishu_chat_ids"), "owner Feishu chat id must be configured"
assert set(plugin.get("allowed_tools_for_outsider_groups") or []) == {
    "skills_list",
    "skill_view",
    "feishu_doc_read",
    "read_file",
    "search_files",
    "group_cache",
    "feishu_doc_manage",
}
assert plugin.get("allowed_read_roots_for_outsider_groups") == ["~/.hermes/wiki"]
assert plugin.get("group_workspace_root") == "~/.hermes/tmp/group-workspaces"
assert set(plugin.get("allowed_feishu_script_actions_for_outsider_groups") or []) == {
    "create",
    "append",
    "rebuild",
    "delete",
    "read_url",
    "download_file",
}
assert plugin.get("require_process_sandbox") is True

scripts_root = Path(plugin["feishu_doc_scripts_root"]).expanduser().resolve()
python_executable = Path(plugin["python_executable"]).expanduser().resolve()
expected_scripts = {
    "create_new_doc_from_md.py",
    "append_md_to_doc.py",
    "rebuild_doc_from_md.py",
    "delete_doc.py",
    "read_feishu_url.py",
    "download_feishu_file.py",
    "feishu_common.py",
    # Not a mapped action itself, but read_url's renderer dependency; listed
    # so its absence fails with the friendly message instead of a bare
    # FileNotFoundError from the lazy-import sentinel below.
    "read_docx_to_markdown.py",
}
assert python_executable.is_file(), f"configured Python is missing: {python_executable}"
missing_scripts = sorted(name for name in expected_scripts if not (scripts_root / name).is_file())
assert not missing_scripts, f"configured Feishu scripts are missing: {missing_scripts}"

# read_feishu_url imports read_docx_to_markdown only for the pure parse_blocks
# renderer. A module-scope `import requests` there breaks every read_url call
# whenever the running interpreter lacks requests, so keep the dependency
# confined to the two network helpers.
renderer = (scripts_root / "read_docx_to_markdown.py").read_text(encoding="utf-8")
assert re.search(
    r"^import requests\b", renderer, re.MULTILINE
) is None, "read_docx_to_markdown.py must not import requests at module scope"
assert renderer.count("    import requests\n") == 2, (
    "both network helpers (get_tenant_access_token / download_doc_to_md) "
    "must import requests lazily"
)
PY
    echo "OK   owner-DM/group YAML contract and fixed Feishu script map are valid"
else
    echo "FAIL owner-DM/group YAML contract or fixed Feishu script map is invalid"
    fail=1
fi

if [[ -x /usr/bin/sandbox-exec ]]; then
    echo "OK   required process sandbox is available"
else
    echo "FAIL /usr/bin/sandbox-exec is unavailable; trusted scripts must fail closed"
    fail=1
fi

# 5. Real platform toolset resolution (HARD)
if [[ -x "${VENV_PYTHON}" ]] &&
    (
        cd "${HERMES_AGENT}" &&
            "${VENV_PYTHON}" - <<'PY'
from hermes_cli.config import load_config
from hermes_cli.plugins import discover_plugins
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions
from toolsets import resolve_toolset
from tools import tool_search

discover_plugins(force=True)
config = load_config()

def resolve(platform):
    toolsets = _get_platform_tools(config, platform, include_default_mcp_servers=False)
    tools = {tool for toolset in toolsets for tool in resolve_toolset(toolset)}
    return toolsets, tools

owner_toolsets, owner_tools = resolve("feishu")
group_toolsets, group_tools = resolve("feishu_group")

assert "sandbox_group" not in owner_toolsets
assert {
    "terminal",
    "file",
    "skills",
    "code_execution",
    "browser",
    "cronjob",
    "memory",
}.issubset(owner_toolsets)
assert {
    "terminal",
    "process",
    "read_file",
    "write_file",
    "patch",
    "execute_code",
    "skill_manage",
}.issubset(owner_tools)

assert "sandbox_group" in group_toolsets
assert {"group_cache", "feishu_doc_manage", "read_file", "search_files"}.issubset(group_tools)
assert not {
    "terminal",
    "process",
    "write_file",
    "patch",
    "execute_code",
    "skill_manage",
}.intersection(group_tools)

# The gray-test group and all Feishu groups share this same platform scope:
# sandbox tools must be discoverable/describable through the deferred-tool
# bridge, not only callable by name after the model guesses the schema.
group_defs = get_tool_definitions(
    enabled_toolsets=group_toolsets,
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
search_payload = tool_search.dispatch_tool_search(
    {"query": "group cache feishu doc"},
    current_tool_defs=group_defs,
)
assert "group_cache" in search_payload
assert "feishu_doc_manage" in search_payload
describe_group = tool_search.dispatch_tool_describe(
    {"name": "group_cache"},
    current_tool_defs=group_defs,
)
describe_doc = tool_search.dispatch_tool_describe(
    {"name": "feishu_doc_manage"},
    current_tool_defs=group_defs,
)
assert '"name": "group_cache"' in describe_group
assert '"name": "feishu_doc_manage"' in describe_doc
PY
    ); then
    echo "OK   runtime toolsets keep owner Feishu DM full, Feishu groups restricted, and sandbox tools discoverable"
else
    echo "FAIL runtime platform toolset resolution violates the owner/group boundary"
    fail=1
fi

# 6. Behavioral regression suite (HARD). Pin cwd to HERMES_HOME so the user
# plugin namespace resolves even when hermes-update.sh was launched elsewhere.
if [[ -x "${VENV_PYTHON}" ]] && [[ -r "${PLUGIN_TEST}" ]] &&
    (cd "${HERMES_HOME}" && "${VENV_PYTHON}" -m pytest -q "${PLUGIN_TEST}"); then
    echo "OK   sandbox plugin regression tests passed"
else
    echo "FAIL sandbox plugin regression tests failed"
    fail=1
fi

# 7. Runtime trace for the current gateway process (HARD)
if [[ -r "${AGENT_LOG}" ]]; then
    gateway_status=$(hermes gateway status 2>&1 || true)
    gateway_pid=$(echo "${gateway_status}" | sed -nE 's/.*PID[^0-9]*([0-9]+).*/\1/p' | head -1)
    current_reg=""
    if [[ -n "${gateway_pid}" ]]; then
        current_reg=$(grep "sandbox: registered (pid=${gateway_pid}," "${AGENT_LOG}" | tail -1 || true)
    fi
    if [[ -z "${gateway_pid}" ]]; then
        echo "FAIL current gateway PID is unavailable"
        echo "     ${gateway_status}"
        fail=1
    elif [[ -z "${current_reg}" ]]; then
        echo "FAIL no sandbox registration trace for current gateway PID ${gateway_pid}"
        echo "     Run 'hermes plugins enable sandbox && hermes gateway restart' and re-check."
        fail=1
    elif echo "${current_reg}" | grep -q 'active=True' &&
        echo "${current_reg}" | grep -q 'group_cache' &&
        echo "${current_reg}" | grep -q 'feishu_doc_manage'; then
        # Strip the date+level prefix for readability.
        msg="${current_reg##*INFO }"
        echo "OK   runtime: ${msg}"
    elif echo "${current_reg}" | grep -q 'active=False'; then
        echo "FAIL plugin loaded but inactive: ${current_reg}"
        echo "     Check plugins/sandbox/config.yaml: owner_feishu_chat_ids must be a non-empty list."
        fail=1
    else
        echo "FAIL current gateway PID ${gateway_pid} registered an incompatible sandbox version"
        echo "     Restart the gateway, then re-run this verifier."
        fail=1
    fi
else
    echo "FAIL agent.log not readable at ${AGENT_LOG}"
    fail=1
fi

if ((fail)); then
    echo "=== sandbox check: FAIL ==="
    exit 1
fi
echo "=== sandbox check: OK ==="
