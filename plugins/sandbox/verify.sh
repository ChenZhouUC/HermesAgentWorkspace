#!/usr/bin/env bash
# Sanity-check the sandbox plugin against the currently installed hermes-agent.
#
# Designed to be invoked by hermes-update.sh (step 8e) after an upstream
# update, and runnable standalone any time:
#
#   bash ~/.hermes/plugins/sandbox/verify.sh
#
# What it checks (in order, cheapest first):
#   1. Upstream VALID_HOOKS still declares all hook names we depend on
#      (pre_gateway_dispatch, pre_tool_call, post_tool_call). HARD FAIL if missing — the
#      plugin's register() will be a no-op when the hook name is gone.
#   2. Fire sites for both hooks still exist in upstream source.
#   3. Structured tool registration remains available upstream.
#   4. Root/plugin YAML keeps the owner-DM and group capability contracts,
#      fixed script map, and manual approval posture.
#   5. Real platform toolset resolution keeps owner Feishu DMs unrestricted
#      while Feishu groups receive only the reviewed structured surface.
#   6. The plugin regression tests pass.
#   7. launchd supervises the current wrapper, and the real gateway child PID's
#      runtime trace reports active=True and the structured tools.
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
for hook in pre_gateway_dispatch pre_tool_call post_tool_call; do
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
if [[ -r "${MODEL_TOOLS}" ]] && grep -q 'post_tool_call' "${MODEL_TOOLS}"; then
    echo "OK   post_tool_call fired from model_tools.py"
else
    echo "FAIL post_tool_call fire site not found in model_tools.py"
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
    "hypertex",
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
hypertex_mcp = (root.get("mcp_servers") or {}).get("hypertex") or {}
assert int(hypertex_mcp.get("timeout") or 0) == 30
assert int(hypertex_mcp.get("idle_timeout_seconds") or 0) == 60
assert set(((hypertex_mcp.get("tools") or {}).get("include") or [])) == {
    "hypertex_list_cases",
    "hypertex_create_case",
    "hypertex_iterate_case",
    "hypertex_get_case",
}
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
assert plugin.get("hypertex_asset_staging_root") == "~/.hermes/tmp/hypertex-assets"
assert int(plugin.get("hypertex_max_asset_bytes") or 0) == 50000000
assert int(plugin.get("hypertex_max_assets_per_turn") or 0) == 6
assert int(plugin.get("hypertex_asset_staging_ttl_seconds") or 0) == 86400
assert set(plugin.get("allowed_tools_for_outsider_groups") or []) == {
    "clarify",
    "web_search",
    "web_extract",
    "tool_search",
    "tool_describe",
    "skills_list",
    "skill_view",
    "feishu_doc_read",
    "read_file",
    "search_files",
    "group_cache",
    "feishu_doc_manage",
    "mcp__hypertex__hypertex_list_cases",
    "mcp__hypertex__hypertex_create_case",
    "mcp__hypertex__hypertex_iterate_case",
    "mcp__hypertex__hypertex_get_case",
    "mcp__hypertex__tasks_get",
    "mcp__hypertex__tasks_cancel",
    "mcp__hypertex__tasks_update",
}
mutation_users = set(plugin.get("trusted_feishu_user_ids_for_group_mutations") or [])
assert mutation_users, "trusted group mutation user ids must be configured"
assert mutation_users.issubset(set(feishu.get("assistant_user_ids") or []))
hypertex_users = set(plugin.get("trusted_feishu_user_ids_for_group_hypertex") or [])
assert hypertex_users, "trusted group HyperTeX user ids must be configured"
assert hypertex_users.issubset(set(feishu.get("assistant_user_ids") or []))
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
import importlib

from hermes_cli.config import load_config
from hermes_cli.plugins import discover_plugins
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions, handle_function_call
from toolsets import resolve_toolset
from tools import tool_search
from tools.mcp_tool import discover_mcp_tools

discover_plugins(force=True)
config = load_config()
discover_mcp_tools()

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
assert "hypertex" in group_toolsets
assert {"clarify", "web_search", "web_extract", "group_cache", "feishu_doc_manage", "read_file", "search_files"}.issubset(group_tools)
assert {
    "mcp__hypertex__hypertex_list_cases",
    "mcp__hypertex__hypertex_create_case",
    "mcp__hypertex__hypertex_iterate_case",
    "mcp__hypertex__hypertex_get_case",
    "mcp__hypertex__tasks_get",
    "mcp__hypertex__tasks_cancel",
    "mcp__hypertex__tasks_update",
}.issubset(group_tools)
assert not {
    "terminal",
    "process",
    "write_file",
    "patch",
    "execute_code",
    "skill_manage",
}.intersection(group_tools)
assert not {"vision_analyze", "image_generate"}.intersection(group_tools)

# The gray-test group and all Feishu groups share this same platform scope:
# sandbox tools must be discoverable/describable through the deferred-tool
# bridge, not only callable by name after the model guesses the schema.
group_defs = get_tool_definitions(
    enabled_toolsets=group_toolsets,
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
search_payload = tool_search.dispatch_tool_search(
    {"query": "group cache feishu doc hypertex presentation"},
    current_tool_defs=group_defs,
)
assert "group_cache" in search_payload
assert "feishu_doc_manage" in search_payload
assert "mcp__hypertex__hypertex_iterate_case" in search_payload
hypertex_create_payload = tool_search.dispatch_tool_search(
    {"query": "create case"},
    current_tool_defs=group_defs,
)
assert "mcp__hypertex__hypertex_create_case" in hypertex_create_payload
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

# Also pass through the actual sandbox pre_tool_call hook. The dispatch checks
# above alone can be green while Feishu groups still block the bridge tools.
sandbox = importlib.import_module("hermes_plugins.sandbox")
sandbox._current_platform.set("feishu")
sandbox._current_chat_id.set(next(iter(sandbox._OWNER_CHAT_IDS)))
sandbox._current_chat_type.set("private")
sandbox._current_media_paths.set(tuple())
sandbox._current_hypertex_call_count.set(0)
owner_hypertex_args = {
    "prompt": "verify",
    "owner_username": "chenzhou",
    "agent": "qwen",
    "type": "brochure",
    "asset_paths": ["/etc/passwd"],
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_CREATE_TOOL,
    args=owner_hypertex_args,
) is None
assert owner_hypertex_args == {
    "prompt": "verify",
    "owner_username": "hermes",
    "agent": "codex",
    "type": "deck",
    "asset_paths": [],
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_TASK_TOOL,
    args={"task_id": 2},
) == {"action": "block", "message": sandbox._HYPERTEX_ONE_CALL_MESSAGE}

sandbox._current_hypertex_call_count.set(0)
owner_task_args = {"task_id": "2"}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_TASK_TOOL,
    args=owner_task_args,
) is None
assert owner_task_args == {"task_id": "2"}

sandbox._current_platform.set("feishu")
sandbox._current_chat_id.set("oc_verify_group")
sandbox._current_chat_type.set("group")
sandbox._current_user_id.set("ou_untrusted_verify")
sandbox._current_resource_refs.set(frozenset())
assert sandbox._on_pre_tool_call(tool_name="clarify", args={"question": "pick one"}) is None
assert sandbox._on_pre_tool_call(tool_name="tool_search", args={"query": "group cache"}) is None
assert sandbox._on_pre_tool_call(tool_name="tool_describe", args={"name": "group_cache"}) is None
assert sandbox._on_pre_tool_call(tool_name="vision_analyze", args={"image_url": "/tmp/x.png"}) == {
    "action": "block",
    "message": sandbox._BLOCK_MESSAGE,
}
assert sandbox._on_pre_tool_call(tool_name="terminal", args={"command": "id"}) == {
    "action": "block",
    "message": sandbox._BLOCK_MESSAGE,
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_LIST_TOOL,
    args={"username": "hermes"},
) == {"action": "block", "message": sandbox._HYPERTEX_GROUP_BLOCK_MESSAGE}

sandbox._current_user_id.set(next(iter(sandbox._GROUP_HYPERTEX_USER_IDS)))
sandbox._current_hypertex_call_count.set(0)
group_hypertex_args = {"username": "someone-else"}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_LIST_TOOL,
    args=group_hypertex_args,
) is None
assert group_hypertex_args == {"username": "hermes"}
sandbox._current_user_id.set("ou_untrusted_verify")

# Exercise the real deferred bridge: tool_call unwraps to the scoped
# underlying tool, then the sandbox hook sees the real name. Out-of-scope tools
# remain unavailable even if a model guesses their registry name.
cache_result = handle_function_call(
    "tool_call",
    {"name": "group_cache", "arguments": {"action": "list", "path": "."}},
    task_id="sandbox-verify",
    enabled_toolsets=group_toolsets,
)
assert '"success": true' in cache_result
terminal_result = handle_function_call(
    "tool_call",
    {"name": "terminal", "arguments": {"command": "id"}},
    task_id="sandbox-verify",
    enabled_toolsets=group_toolsets,
)
assert "not a deferrable tool" in terminal_result
doc_mutation_result = handle_function_call(
    "tool_call",
    {
        "name": "feishu_doc_manage",
        "arguments": {"action": "create", "title": "audit", "content": "# audit"},
    },
    task_id="sandbox-verify",
    enabled_toolsets=group_toolsets,
)
assert "受信任的维护者" in doc_mutation_result

# Default search_files path is rewritten to the verified wiki root instead of
# the process cwd, so the documented default invocation is both useful and safe.
search_args = {"pattern": "__sandbox_verify_no_match__"}
assert sandbox._on_pre_tool_call(tool_name="search_files", args=search_args) is None
assert search_args["path"] == str(sandbox._GROUP_ALLOWED_READ_ROOTS[0])

# Feishu resource reads are bound to URLs/tokens explicitly present in the
# current group message; arbitrary bot-readable documents are not ambient.
from types import SimpleNamespace
token = "doxcnSandboxVerifyToken"
url = f"https://whales.feishu.cn/docx/{token}"
sandbox._on_pre_gateway_dispatch(SimpleNamespace(
    source=SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="oc_verify_group",
        chat_type="group",
        user_id="ou_untrusted_verify",
    ),
    text=f"read {url}",
    reply_to_text="",
    channel_context="",
))
assert sandbox._on_pre_tool_call(
    tool_name="feishu_doc_read", args={"doc_token": token}
) is None
assert sandbox._on_pre_tool_call(
    tool_name="feishu_doc_read", args={"doc_token": "doxcnOtherToken"}
) == {"action": "block", "message": sandbox._RESOURCE_BLOCK_MESSAGE}
PY
    ); then
    echo "OK   runtime toolsets keep owner Feishu DM full, Feishu groups restricted, and sandbox tools discoverable through hooks"
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

# 7. Runtime trace for the real gateway child process (HARD). Newer launchd
# plists supervise hermes_cli.stderr_timestamp directly, so `gateway status`
# reports the wrapper PID while plugin registration logs use the child PID.
# Prove both layers: launchd supervisor health from status, runtime identity
# from gateway.status.get_running_pid().
if [[ -r "${AGENT_LOG}" ]]; then
    gateway_status=$(hermes gateway status 2>&1 || true)
    supervisor_pid=$(echo "${gateway_status}" | sed -nE 's/.*supervised by launchd \(PID ([0-9]+)\).*/\1/p' | head -1)
    gateway_pid=""
    if [[ -x "${VENV_PYTHON}" ]]; then
        gateway_pid=$(
            HERMES_HOME="${HERMES_HOME}" "${VENV_PYTHON}" - <<'PY' 2>/dev/null || true
from gateway.status import get_running_pid

print(get_running_pid(cleanup_stale=False) or "")
PY
        )
    fi
    current_reg=""
    current_mcp_tasks=""
    if [[ -n "${gateway_pid}" ]]; then
        current_reg=$(grep "sandbox: registered (pid=${gateway_pid}," "${AGENT_LOG}" | tail -1 || true)
        current_reg_line=$(grep -n "sandbox: registered (pid=${gateway_pid}," "${AGENT_LOG}" | tail -1 | cut -d: -f1 || true)
        if [[ -n "${current_reg_line}" ]]; then
            for _mcp_wait_attempt in {1..20}; do
                current_mcp_tasks=$(tail -n "+${current_reg_line}" "${AGENT_LOG}" | grep "MCP server 'hypertex'.*mcp__hypertex__tasks_get.*mcp__hypertex__tasks_cancel.*mcp__hypertex__tasks_update" | head -1 || true)
                [[ -n "${current_mcp_tasks}" ]] && break
                sleep 0.5
            done
        fi
    fi
    if [[ -z "${supervisor_pid}" ]] || ! echo "${gateway_status}" | grep -q 'Service definition matches the current Hermes install'; then
        echo "FAIL launchd supervisor/current service definition is unavailable"
        echo "     ${gateway_status}"
        fail=1
    elif [[ -z "${gateway_pid}" ]]; then
        echo "FAIL real gateway child PID is unavailable (launchd wrapper PID ${supervisor_pid})"
        fail=1
    elif [[ -z "${current_reg}" ]]; then
        echo "FAIL no sandbox registration trace for gateway child PID ${gateway_pid} (launchd wrapper PID ${supervisor_pid})"
        echo "     Run 'hermes plugins enable sandbox && hermes gateway restart' and re-check."
        fail=1
    elif [[ -z "${current_mcp_tasks}" ]]; then
        echo "FAIL no standard MCP Tasks registration after sandbox trace for gateway child PID ${gateway_pid}"
        fail=1
    elif echo "${current_reg}" | grep -q 'active=True' &&
        echo "${current_reg}" | grep -q 'tool_search' &&
        echo "${current_reg}" | grep -q 'tool_describe' &&
        echo "${current_reg}" | grep -q 'group_cache' &&
        echo "${current_reg}" | grep -q 'feishu_doc_manage' &&
        echo "${current_reg}" | grep -q 'mcp__hypertex__hypertex_create_case' &&
        echo "${current_reg}" | grep -q 'hypertex_users='; then
        # Strip the date+level prefix for readability.
        msg="${current_reg##*INFO }"
        echo "OK   runtime: launchd wrapper pid=${supervisor_pid}; ${msg}"
    elif echo "${current_reg}" | grep -q 'active=False'; then
        echo "FAIL plugin loaded but inactive: ${current_reg}"
        echo "     Check plugins/sandbox/config.yaml: owner_feishu_chat_ids must be a non-empty list."
        fail=1
    else
        echo "FAIL gateway child PID ${gateway_pid} registered an incompatible sandbox version"
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
