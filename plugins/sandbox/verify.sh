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
#      (pre_gateway_dispatch, pre_tool_call, post_tool_call, post_llm_call). HARD FAIL if missing — the
#      plugin's register() will be a no-op when the hook name is gone.
#   2. Fire sites for all hooks still exist in upstream source.
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
GATEWAY_RUN_INBOUND="${HERMES_AGENT}/gateway/run_inbound.py"
MODEL_TOOLS="${HERMES_AGENT}/model_tools.py"
TURN_FINALIZER="${HERMES_AGENT}/agent/turn_finalizer.py"
AGENT_LOG="${HERMES_HOME}/logs/agent.log"
ROOT_CONFIG="${HERMES_HOME}/config.yaml"
PLUGIN_CONFIG="${HERMES_HOME}/plugins/sandbox/config.yaml"
PLUGIN_MANIFEST="${HERMES_HOME}/plugins/sandbox/plugin.yaml"
PLUGIN_TEST="${HERMES_HOME}/plugins/sandbox/test_sandbox.py"
PEOPLE_FILE="${HERMES_HOME}/people.yaml"
GROUPS_FILE="${HERMES_HOME}/groups.yaml"
PEOPLE_TEST="${HERMES_HOME}/scripts/test_pull_feishu_people.py"
DOC_MEDIA_TEST="${HERMES_HOME}/my-skills/productivity/feishu-docs/scripts/test_manage_doc_image.py"
DOC_STAGE_TEST="${HERMES_HOME}/my-skills/productivity/feishu-docs/scripts/test_stage_remote_images.py"
DOC_READ_TEST="${HERMES_HOME}/my-skills/productivity/feishu-docs/scripts/test_read_feishu_url.py"
VENV_PYTHON="${HERMES_AGENT}/venv/bin/python"

fail=0
_SANDBOX_JUNIT=""

cleanup_verify_tmp() {
    if [[ -n "${_SANDBOX_JUNIT}" ]]; then
        rm -f -- "${_SANDBOX_JUNIT}"
    fi
}

trap cleanup_verify_tmp EXIT

echo "=== sandbox plugin compatibility check ==="

# 1. VALID_HOOKS membership (HARD)
for hook in pre_gateway_dispatch pre_tool_call post_tool_call post_llm_call; do
    if [[ -r "${PLUGINS_SRC}" ]] && grep -qF "\"${hook}\"" "${PLUGINS_SRC}"; then
        echo "OK   ${hook} is in VALID_HOOKS"
    else
        echo "FAIL ${hook} NOT in VALID_HOOKS at ${PLUGINS_SRC}"
        echo "     Upstream may have renamed/removed it; check git log and update __init__.py."
        fail=1
    fi
done

# 2. Fire-site presence (HARD)
if [[ -r "${GATEWAY_RUN_INBOUND}" ]] && grep -q 'pre_gateway_dispatch' "${GATEWAY_RUN_INBOUND}"; then
    echo "OK   pre_gateway_dispatch fired from gateway/run_inbound.py"
else
    echo "FAIL pre_gateway_dispatch fire site not found in gateway/run_inbound.py"
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
if [[ -r "${TURN_FINALIZER}" ]] && grep -q 'post_llm_call' "${TURN_FINALIZER}"; then
    echo "OK   post_llm_call fired from agent/turn_finalizer.py"
else
    echo "FAIL post_llm_call fire site not found in agent/turn_finalizer.py"
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
    [[ -r "${PLUGIN_MANIFEST}" ]] &&
    [[ -r "${PEOPLE_FILE}" ]] &&
    [[ -r "${GROUPS_FILE}" ]] &&
    "${VENV_PYTHON}" - "${ROOT_CONFIG}" "${PLUGIN_CONFIG}" "${PEOPLE_FILE}" "${GROUPS_FILE}" "${PLUGIN_MANIFEST}" <<'PY'
import re
import sys
import plistlib
from pathlib import Path

import yaml

root_path = Path(sys.argv[1])
plugin_path = Path(sys.argv[2])
people_path = Path(sys.argv[3])
groups_path = Path(sys.argv[4])
manifest_path = Path(sys.argv[5])
root = yaml.safe_load(root_path.read_text(encoding="utf-8")) or {}
plugin = yaml.safe_load(plugin_path.read_text(encoding="utf-8")) or {}
people = (yaml.safe_load(people_path.read_text(encoding="utf-8")) or {}).get("people") or []
groups = (yaml.safe_load(groups_path.read_text(encoding="utf-8")) or {}).get("groups") or []
manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

env_ref = r"\$\{(?:env:)?[A-Za-z_][A-Za-z0-9_]*\}"
allowed_secret_ref = re.compile(rf"^(?:(?:Bearer|Basic|Token)\s+)?{env_ref}$", re.I)
sensitive_header = re.compile(r"authorization|api[-_]?key|token|secret", re.I)
for server_name, server in (root.get("mcp_servers") or {}).items():
    if not isinstance(server, dict):
        continue
    for header_name, raw_value in (server.get("headers") or {}).items():
        if sensitive_header.search(str(header_name)):
            assert allowed_secret_ref.fullmatch(str(raw_value).strip()), (
                f"mcp_servers.{server_name}.headers.{header_name} must use an environment reference"
            )

assert manifest.get("version") == "0.7.14"

assert people, "people.yaml must contain the active Feishu roster"
open_ids = [str(person.get("open_id") or "") for person in people if isinstance(person, dict)]
user_ids = [str(person.get("user_id") or "") for person in people if isinstance(person, dict)]
assert len(open_ids) == len(people) == len(user_ids)
assert all(open_ids), "every person must have open_id"
assert all(user_ids), "every person must have tenant user_id"
assert len(set(open_ids)) == len(open_ids), "open_id values must be unique"
assert len(set(user_ids)) == len(user_ids), "tenant user_id values must be unique"
assert (people_path.stat().st_mode & 0o777) == 0o600, "people.yaml must remain owner-only"
owner_open_id = open_ids[0]
group_chat_ids = {
    str(group.get("chat_id") or "")
    for group in groups
    if isinstance(group, dict) and str(group.get("chat_id") or "")
}
assert group_chat_ids, "groups.yaml must contain at least one admitted Feishu group"

mcp_servers = root.get("mcp_servers") or {}
hypertex_mcp = mcp_servers.get("hypertex") or {}
if "hypertex" in mcp_servers:
    assert hypertex_mcp.get("enabled") is not False, (
        "remove mcp_servers.hypertex entirely when the peer machine does not deploy it"
    )
hypertex_enabled = bool(hypertex_mcp)

expected_group_toolsets = {
    "web",
    "clarify",
    "feishu_doc",
    "skills_readonly",
    "file_readonly",
    "sandbox_group",
}
if hypertex_enabled:
    expected_group_toolsets.add("hypertex")
platform_toolsets = root.get("platform_toolsets") or {}
assert set(platform_toolsets.get("feishu_group") or []) == expected_group_toolsets
assert "feishu" not in platform_toolsets, "owner Feishu DM must keep the platform default toolsets"
assert (root.get("platform_toolset_options") or {}).get("feishu_group", {}).get(
    "recover_platform_tools"
) is False
for platform in ("cli", "feishu", "feishu_group"):
    assert "sandbox_group" in set((root.get("known_plugin_toolsets") or {}).get(platform) or [])
    assert "image_gen" in set((root.get("known_plugin_toolsets") or {}).get(platform) or [])

# Group-readable skills are an explicit, verified allowlist — never inferred.
# excel-processing (2026-08-12) is read-only knowledge: its scripts/ cannot be
# executed from a group (no terminal/process/code_execution in the group
# toolset, and feishu_doc_manage only maps fixed actions under
# feishu_doc_scripts_root), so admitting it does NOT widen the tool surface.
assert (root.get("skills") or {}).get("platform_allowed", {}).get("feishu_group") == [
    "llm-wiki",
    "feishu-docs",
    "excel-processing",
    "image-generation",
    "chart-generation",
]
assert (root.get("approvals") or {}).get("mode") == "manual"
assert root.get("command_allowlist") == []
assert "sandbox" in set((root.get("plugins") or {}).get("enabled") or [])
if hypertex_enabled:
    assert int(hypertex_mcp.get("timeout") or 0) == 30
    assert int(hypertex_mcp.get("idle_timeout_seconds") or 0) == 60
    assert set(((hypertex_mcp.get("tools") or {}).get("include") or [])) == {
        "hypertex_create_case",
        "hypertex_iterate_case",
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
if hypertex_enabled:
    assert plugin.get("hypertex_asset_staging_root") == "~/.hermes/tmp/hypertex-assets"
    assert int(plugin.get("hypertex_max_asset_bytes") or 0) == 100000000
    assert int(plugin.get("hypertex_max_assets_per_turn") or 0) == 20
    assert int(plugin.get("hypertex_asset_staging_ttl_seconds") or 0) == 86400
assert int(plugin.get("group_max_download_bytes") or 0) == 100000000
expected_group_tools = {
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
    "group_image_generate",
    "group_chart_generate",
}
if hypertex_enabled:
    expected_group_tools |= {
        "mcp__hypertex__hypertex_create_case",
        "mcp__hypertex__hypertex_iterate_case",
        "mcp__hypertex__tasks_get",
    }
assert set(plugin.get("allowed_tools_for_outsider_groups") or []) == expected_group_tools
# HyperTeX's Feishu contract is intentionally limited to submit, revise, and
# exact task lookup. Case discovery and task mutation stay outside the sandbox
# allowlist even when the MCP client registers protocol-level task utilities.
# ROSTER: open_id only. Tenant-scoped short IDs must not reappear in any
# allowlist — they are unrecoverable from people.yaml and never delivered by
# this app, so they were dead weight that made adding a member guesswork.
# The two grants are independent: document deletion is irreversible, so it
# stays with the configured owner, while HyperTeX trust may widen explicitly.
# people.yaml/groups.yaml establish referential integrity; the plugin trust
# lists remain the authorization source and any widening still requires diff
# review rather than being inferred from roster membership.
mutation_users = set(plugin.get("trusted_feishu_user_ids_for_group_mutations") or [])
expected_mutation_users = {owner_open_id}
assert mutation_users == expected_mutation_users
assert set(feishu.get("assistant_user_ids") or []) == expected_mutation_users, (
    "delete trust must match the configured owner/assistant identity"
)
hypertex_chats = set(plugin.get("trusted_feishu_chat_ids_for_group_hypertex") or [])
hypertex_users = set(plugin.get("trusted_feishu_user_ids_for_group_hypertex") or [])
assert hypertex_chats <= group_chat_ids, "HyperTeX chats must come from groups.yaml"
assert hypertex_users <= set(open_ids), "HyperTeX users must come from people.yaml"
if hypertex_enabled:
    assert hypertex_chats, "enabled HyperTeX must have at least one trusted group"
    assert mutation_users <= hypertex_users, "owner delete trust must stay within HyperTeX trust"
else:
    assert not hypertex_chats and not hypertex_users, (
        "HyperTeX trust lists must be empty when the MCP is not configured"
    )

for key in (
    "trusted_feishu_chat_ids_for_group_image_generation",
    "trusted_feishu_chat_ids_for_group_chart_generation",
):
    admitted_chats = set(plugin.get(key) or [])
    assert admitted_chats, f"{key} must not be empty"
    assert admitted_chats == {"*"} or admitted_chats <= group_chat_ids, (
        f"{key} must be '*' or a subset of groups.yaml"
    )
assert plugin.get("allowed_read_roots_for_outsider_groups") == ["~/.hermes/wiki"]
assert plugin.get("group_workspace_root") == "~/.hermes/tmp/group-workspaces"
assert plugin.get("private_doc_workspace_root") == "~/.hermes/tmp/feishu-doc-assets"
assert set(plugin.get("allowed_feishu_script_actions_for_outsider_groups") or []) == {
    "create",
    "append",
    "rebuild",
    "delete",
    "read_url",
    "download_file",
    "stage_image_urls",
    "insert_image",
    "set_cover",
    "replace_image",
}
assert plugin.get("require_process_sandbox") is True
assert plugin.get("group_image_generation_script") == (
    "~/.hermes/my-skills/creative/image-generation/scripts/generate_image.py"
)
assert plugin.get("private_image_workspace_root") == "~/.hermes/tmp/image-generation"
assert plugin.get("chart_generation_script") == (
    "~/.hermes/my-skills/creative/chart-generation/scripts/render_chart.py"
)
assert plugin.get("chart_python_executable") == "~/.hermes/lib/chart-renderer/venv/bin/python"
assert plugin.get("private_chart_workspace_root") == "~/.hermes/tmp/chart-generation"
assert "image_generation_api_base_url" not in plugin, \
    "image key/base URL must stay paired in the profile .env"
assert int(plugin.get("group_image_generation_timeout_seconds") or 0) == 900
assert int(plugin.get("group_image_max_input_bytes") or 0) == 25000000
assert int(plugin.get("group_image_max_output_bytes") or 0) == 10000000
assert int(plugin.get("group_image_max_inputs") or 0) == 4
assert int(plugin.get("chart_generation_timeout_seconds") or 0) == 60
assert int(plugin.get("chart_max_output_bytes") or 0) == 10000000
assert int(plugin.get("group_doc_image_max_bytes") or 0) == 20 * 1024 * 1024
assert plugin.get("mutation_trust_block_message") == "群聊中的飞书文档删除仅允许受信任的维护者执行。"
assert plugin.get("mutation_reference_block_message") == "修改飞书文档时，必须在当前消息或显式引用中附上目标文档链接。"

scripts_root = Path(plugin["feishu_doc_scripts_root"]).expanduser().resolve()
python_executable = Path(plugin["python_executable"]).expanduser().resolve()
image_script = Path(plugin["group_image_generation_script"]).expanduser().resolve()
chart_script = Path(plugin["chart_generation_script"]).expanduser().resolve()
chart_python = Path(plugin["chart_python_executable"]).expanduser().absolute()
expected_scripts = {
    "create_new_doc_from_md.py",
    "append_md_to_doc.py",
    "rebuild_doc_from_md.py",
    "delete_doc.py",
    "read_feishu_url.py",
    "download_feishu_file.py",
    "stage_remote_images.py",
    "manage_doc_image.py",
    "test_manage_doc_image.py",
    "test_stage_remote_images.py",
    "test_read_feishu_url.py",
    "feishu_common.py",
    # Not a mapped action itself, but read_url's renderer dependency; listed
    # so its absence fails with the friendly message instead of a bare
    # FileNotFoundError from the lazy-import sentinel below.
    "read_docx_to_markdown.py",
}
assert python_executable.is_file(), f"configured Python is missing: {python_executable}"
assert image_script.is_file(), f"configured group image script is missing: {image_script}"
assert chart_script.is_file(), f"configured chart script is missing: {chart_script}"
assert chart_python.is_file(), f"configured chart Python is missing: {chart_python}"
chart_versions = __import__("subprocess").check_output(
    [
        str(chart_python),
        "-c",
        "import importlib.metadata as m; "
        "print(m.version('matplotlib'), m.version('seaborn'), m.version('fonttools'), m.version('pandas'), "
        "m.version('numpy'), m.version('scipy'), m.version('statsmodels'))",
    ],
    text=True,
).strip()
assert chart_versions == "3.10.6 0.13.2 4.63.0 2.3.2 2.3.2 1.16.1 0.15.0", (
    f"unexpected chart renderer versions: {chart_versions}"
)
missing_scripts = sorted(name for name in expected_scripts if not (scripts_root / name).is_file())
assert not missing_scripts, f"configured Feishu scripts are missing: {missing_scripts}"

doc_media = (scripts_root / "manage_doc_image.py").read_text(encoding="utf-8")
for needle in (
    "/drive/v1/medias/upload_all",
    "parent_type=docx_image",
    "drive_route_token",
    'payload={"replace_image": replacement}',
    'payload={"update_cover": {"cover": cover}}',
    "append_version_row(token, doc_token)",
):
    assert needle in doc_media, f"document media write contract is missing {needle!r}"

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
then
    echo "OK   owner-DM/group YAML contract, complete identity roster, and fixed Feishu script map are valid"
else
    echo "FAIL owner-DM/group YAML contract, identity roster, or fixed Feishu script map is invalid"
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
            HERMES_HOME="${HERMES_HOME}" "${VENV_PYTHON}" - <<'PY'
import contextvars
import importlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

# Pre-seed profile variables before importing Hermes modules: some imports read
# config eagerly, before load_hermes_dotenv() can perform its full startup pass.
home = Path(os.environ["HERMES_HOME"])
load_dotenv(home / ".env", override=True)

from hermes_cli.env_loader import load_hermes_dotenv

load_hermes_dotenv(hermes_home=home)

from hermes_cli.config import load_config
from hermes_cli.plugins import _dispatch_pre_tool_call_hooks, discover_plugins
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions, handle_function_call
from toolsets import resolve_toolset
from tools import tool_search
from tools.mcp_tool_discovery import discover_mcp_tools

discover_plugins(force=True)
config = load_config()
discover_mcp_tools()
hypertex_mcp = (config.get("mcp_servers") or {}).get("hypertex") or {}
hypertex_enabled = bool(hypertex_mcp)

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
    "process_manage",
    "read_file",
    "write_file",
    "patch",
    "execute_code",
    "skill_manage",
}.issubset(owner_tools)
assert "secure_image_generate" in owner_tools
assert "secure_chart_generate" in owner_tools

assert "sandbox_group" in group_toolsets
assert ("hypertex" in group_toolsets) is hypertex_enabled
assert {
    "clarify",
    "web_search",
    "web_extract",
    "group_cache",
    "feishu_doc_manage",
    "group_image_generate",
    "group_chart_generate",
    "read_file",
    "search_files",
}.issubset(group_tools)
hypertex_group_tools = {name for name in group_tools if name.startswith("mcp__hypertex__")}
expected_hypertex_group_tools = (
    {
        "mcp__hypertex__hypertex_create_case",
        "mcp__hypertex__hypertex_iterate_case",
        "mcp__hypertex__tasks_get",
        "mcp__hypertex__tasks_cancel",
        "mcp__hypertex__tasks_update",
    }
    if hypertex_enabled
    else set()
)
assert hypertex_group_tools == expected_hypertex_group_tools
assert not {
    "terminal",
    "process",
    "write_file",
    "patch",
    "execute_code",
    "skill_manage",
}.intersection(group_tools)
assert not {
    "vision_analyze",
    "image_generate",
    "secure_image_generate",
    "secure_chart_generate",
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
    {
        "queries": [
            "group cache feishu doc image chart generation"
            + (" hypertex presentation" if hypertex_enabled else "")
        ]
    },
    current_tool_defs=group_defs,
)
assert "group_cache" in search_payload
assert "feishu_doc_manage" in search_payload
assert "group_image_generate" in search_payload
assert "group_chart_generate" in search_payload
if hypertex_enabled:
    hypertex_create_payload = tool_search.dispatch_tool_search(
        {"queries": ["create case"]},
        current_tool_defs=group_defs,
    )
    assert "mcp__hypertex__hypertex_create_case" in hypertex_create_payload
    hypertex_iterate_payload = tool_search.dispatch_tool_search(
        {"queries": ["iterate case"]},
        current_tool_defs=group_defs,
    )
    assert "mcp__hypertex__hypertex_iterate_case" in hypertex_iterate_payload
describe_group = tool_search.dispatch_tool_describe(
    {"names": ["group_cache"]},
    current_tool_defs=group_defs,
)
describe_doc = tool_search.dispatch_tool_describe(
    {"names": ["feishu_doc_manage"]},
    current_tool_defs=group_defs,
)
describe_image = tool_search.dispatch_tool_describe(
    {"names": ["group_image_generate"]},
    current_tool_defs=group_defs,
)
describe_chart = tool_search.dispatch_tool_describe(
    {"names": ["group_chart_generate"]},
    current_tool_defs=group_defs,
)
assert "group_cache" in (json.loads(describe_group).get("tools") or {})
assert "feishu_doc_manage" in (json.loads(describe_doc).get("tools") or {})
assert "group_image_generate" in (json.loads(describe_image).get("tools") or {})
assert "group_chart_generate" in (json.loads(describe_chart).get("tools") or {})
doc_schema = (json.loads(describe_doc).get("tools") or {})["feishu_doc_manage"]
doc_properties = doc_schema["parameters"]["properties"]
assert {"stage_image_urls", "insert_image", "set_cover", "replace_image"}.issubset(
    set(doc_properties["action"]["enum"])
)
assert {
    "urls",
    "image_path",
    "attachment_index",
    "block_id",
    "position",
    "anchor_text",
    "include_images",
}.issubset(doc_properties)

# Also pass through the actual sandbox pre_tool_call hook. The dispatch checks
# above alone can be green while Feishu groups still block the bridge tools.
sandbox = importlib.import_module("hermes_plugins.sandbox")
sandbox._current_platform.set("feishu")
sandbox._current_chat_id.set(next(iter(sandbox._OWNER_CHAT_IDS)))
sandbox._current_chat_type.set("private")
sandbox._current_media_paths.set(tuple())
sandbox._current_hypertex_call_count.set(0)
sandbox._current_image_generation_call_count.set(0)
sandbox._current_chart_generation_call_count.set(0)
owner_hypertex_args = {
    "prompt": "verify",
    "owner_username": "chenzhou",
    "agent": "qwen",
    "model": "private-model",
    "provider": "private-provider",
    "executor": "private-executor",
    "routing": "caller-selected",
    "type": "brochure",
    "asset_paths": [],
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_CREATE_TOOL,
    args=owner_hypertex_args,
) is None
assert owner_hypertex_args == {
    "prompt": "verify",
    "owner_username": "hermes",
    "type": "freestyle",
    "asset_paths": [],
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_TASK_TOOL,
    args={"task_id": 2},
) == {"action": "block", "message": sandbox._HYPERTEX_ONE_CALL_MESSAGE}

owner_terminal_command = (
    "~/.hermes/hermes-agent/venv/bin/python "
    "~/.hermes/my-skills/productivity/feishu-docs/scripts/manage_doc_image.py "
    "cover doxcnVerifyTarget image.png"
)
owner_block, owner_modified = _dispatch_pre_tool_call_hooks(
    "terminal",
    {"command": owner_terminal_command},
    session_id="sandbox-owner-verify",
    turn_id="sandbox-owner-verify:turn-one",
)
assert owner_block is None
assert owner_modified == {
    "command": (
        "export HERMES_FEISHU_VERSION_TURN_ID=sandbox-owner-verify:turn-one\n"
        + owner_terminal_command
    )
}

sandbox._current_hypertex_call_count.set(0)
owner_task_args = {"task_id": "2"}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_TASK_TOOL,
    args=owner_task_args,
) is None
assert owner_task_args == {"task_id": "2"}

sandbox._current_hypertex_call_count.set(0)
owner_iterate_args = {
    "case_name": "Demo",
    "prompt": "revise",
    "username": "someone-else",
    "agent": "qwen",
    "agent_key": "qwen",
    "model": "private-model",
    "provider": "private-provider",
    "execution_backend": "private-backend",
    "asset_paths": [],
}
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._HYPERTEX_ITERATE_TOOL,
    args=owner_iterate_args,
) is None
assert owner_iterate_args == {
    "case_name": "Demo",
    "prompt": "revise",
    "username": "hermes",
    "asset_paths": [],
}

sandbox._current_platform.set("feishu")
group_test_chat = next(
    (chat_id for chat_id in sandbox._GROUP_IMAGE_CHAT_IDS if chat_id != "*"),
    "oc_verify_any_group",
)
sandbox._current_chat_id.set(group_test_chat)
sandbox._current_chat_type.set("group")
sandbox._current_user_id.set("ou_untrusted_verify")
sandbox._current_user_ids.set(frozenset({"ou_untrusted_verify"}))
sandbox._current_resource_refs.set(frozenset({"doxcnSandboxVerifyTarget"}))
sandbox._current_public_urls.set(frozenset({"https://example.com/source.png"}))

for document_args in (
    {"action": "create"},
    {"action": "append", "doc_token": "doxcnSandboxVerifyTarget"},
    {"action": "rebuild", "doc_token": "doxcnSandboxVerifyTarget"},
    {"action": "stage_image_urls", "urls": ["https://example.com/source.png"]},
    {"action": "insert_image", "doc_token": "doxcnSandboxVerifyTarget"},
    {"action": "set_cover", "doc_token": "doxcnSandboxVerifyTarget"},
    {"action": "replace_image", "doc_token": "doxcnSandboxVerifyTarget"},
):
    assert sandbox._on_pre_tool_call(
        tool_name="feishu_doc_manage",
        args=document_args,
    ) is None
sandbox._current_resource_refs.set(frozenset())
assert sandbox._on_pre_tool_call(tool_name="clarify", args={"question": "pick one"}) is None
assert sandbox._on_pre_tool_call(
    tool_name="tool_search", args={"queries": ["group cache"]}
) is None
assert sandbox._on_pre_tool_call(
    tool_name="tool_describe", args={"names": ["group_cache"]}
) is None
assert sandbox._on_pre_tool_call(tool_name="vision_analyze", args={"image_url": "/tmp/x.png"}) == {
    "action": "block",
    "message": sandbox._BLOCK_MESSAGE,
}
assert sandbox._on_pre_tool_call(tool_name="terminal", args={"command": "id"}) == {
    "action": "block",
    "message": sandbox._BLOCK_MESSAGE,
}
if hypertex_enabled:
    sandbox._current_chat_id.set(next(iter(sandbox._GROUP_HYPERTEX_CHAT_IDS)))
    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_TASK_TOOL,
        args={"task_id": "task-verify"},
    ) == {"action": "block", "message": sandbox._HYPERTEX_GROUP_BLOCK_MESSAGE}

    trusted_open_id = next(iter(sandbox._GROUP_HYPERTEX_USER_IDS))
    sandbox._on_pre_gateway_dispatch(SimpleNamespace(
        source=SimpleNamespace(
            platform=SimpleNamespace(value="feishu"),
            chat_id=next(iter(sandbox._GROUP_HYPERTEX_CHAT_IDS)),
            chat_type="group",
            user_id="tenant_verify_user",
            user_id_alt="union_verify_user",
        ),
        raw_message=SimpleNamespace(
            event=SimpleNamespace(
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(
                        open_id=trusted_open_id,
                        user_id="tenant_verify_user",
                        union_id="union_verify_user",
                    )
                )
            )
        ),
        text="verify identity variants",
        reply_to_text="",
        media_urls=[],
    ))
    assert sandbox._current_actor_ids() == frozenset({
        trusted_open_id,
        "tenant_verify_user",
        "union_verify_user",
    })
    group_hypertex_args = {"task_id": "task-verify"}
    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_TASK_TOOL,
        args=group_hypertex_args,
    ) is None
    assert group_hypertex_args == {"task_id": "task-verify"}

    sandbox._current_chat_id.set("oc_verify_disabled_group")
    sandbox._current_hypertex_call_count.set(0)
    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_TASK_TOOL,
        args={"task_id": "task-verify"},
    ) == {"action": "block", "message": sandbox._HYPERTEX_GROUP_CHAT_BLOCK_MESSAGE}
sandbox._current_user_id.set("ou_untrusted_verify")
sandbox._current_user_ids.set(frozenset({"ou_untrusted_verify"}))

image_test_chat = (
    "oc_verify_any_group"
    if "*" in sandbox._GROUP_IMAGE_CHAT_IDS
    else next(iter(sandbox._GROUP_IMAGE_CHAT_IDS))
)
sandbox._current_chat_id.set(image_test_chat)
sandbox._current_image_generation_call_count.set(0)
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._IMAGE_TOOL,
    args={"prompt": "verify group image boundary"},
) is None
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._IMAGE_TOOL,
    args={"prompt": "second call"},
) == {"action": "block", "message": sandbox._GROUP_IMAGE_ONE_CALL_MESSAGE}
chart_test_chat = (
    "oc_verify_any_group"
    if "*" in sandbox._GROUP_CHART_CHAT_IDS
    else next(iter(sandbox._GROUP_CHART_CHAT_IDS))
)
sandbox._current_chat_id.set(chart_test_chat)
sandbox._current_chart_generation_call_count.set(0)
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._CHART_TOOL,
    args={"title": "verify", "labels": ["A"], "series": [{"name": "V", "values": [1]}]},
) is None
assert sandbox._on_pre_tool_call(
    tool_name=sandbox._CHART_TOOL,
    args={"title": "again", "labels": ["A"], "series": [{"name": "V", "values": [2]}]},
) == {"action": "block", "message": sandbox._GROUP_CHART_ONE_CALL_MESSAGE}

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
        "arguments": {"action": "delete", "doc_token": "doxcnSandboxVerifyTarget"},
    },
    task_id="sandbox-verify",
    enabled_toolsets=group_toolsets,
)
assert "受信任的维护者" in doc_mutation_result

# The create result and the follow-up media write execute in separate copied
# worker contexts in production. Prove the exact created token survives that
# ContextVar boundary through the shared (chat, turn_id) grant ledger.
created_token = "doxcnSandboxVerifyCreatedTarget"
created_turn = "sandbox-group-verify:turn-one"
workspace = sandbox._workspace_for_chat(chart_test_chat)
markdown_path = workspace / "same-turn-create.md"
cover_path = workspace / "same-turn-cover.png"
staged_path = workspace / "sourced-images" / "verify-source.png"
markdown_path.write_text("# same-turn verification\n", encoding="utf-8")
cover_path.write_bytes(
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)
original_run_trusted_script = sandbox._run_trusted_script
try:
    def _fake_created_doc_run(script, _argv, _workspace):
        if script.name == "stage_remote_images.py":
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_bytes(cover_path.read_bytes())
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=json.dumps({
                    "success": True,
                    "images": [{
                        "index": 0,
                        "workspace_path": str(staged_path.relative_to(workspace)),
                        "mime_type": "image/png",
                        "size_bytes": staged_path.stat().st_size,
                        "width": 1,
                        "height": 1,
                    }],
                    "total_bytes": staged_path.stat().st_size,
                }),
                stderr="",
            )
        stdout = (
            f"Doc created: {created_token}. Patching title...\n"
            f"DONE: https://whales.feishu.cn/docx/{created_token}\n"
            if script.name == "create_new_doc_from_md.py"
            else "updated"
        )
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    sandbox._run_trusted_script = _fake_created_doc_run
    create_result = contextvars.copy_context().run(
        handle_function_call,
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {
                "action": "create",
                "title": "same-turn verification",
                "markdown_path": markdown_path.name,
            },
        },
        task_id="sandbox-verify",
        session_id="sandbox-group-verify",
        turn_id=created_turn,
        enabled_toolsets=group_toolsets,
    )
    assert '"success": true' in create_result
    source_url = "https://media.example.com/verify-source.png"
    contextvars.copy_context().run(
        sandbox._on_post_tool_call,
        tool_name="web_extract",
        result=json.dumps({"results": [{"url": "https://example.com/page", "content": source_url}]}),
        turn_id=created_turn,
    )
    stage_result = contextvars.copy_context().run(
        handle_function_call,
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {"action": "stage_image_urls", "urls": [source_url]},
        },
        task_id="sandbox-verify",
        session_id="sandbox-group-verify",
        turn_id=created_turn,
        enabled_toolsets=group_toolsets,
    )
    assert '"success": true' in stage_result
    assert '"workspace_path": "sourced-images/verify-source.png"' in stage_result
    unobserved_stage = contextvars.copy_context().run(
        handle_function_call,
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {"action": "stage_image_urls", "urls": ["https://unobserved.example/image.png"]},
        },
        task_id="sandbox-verify",
        session_id="sandbox-group-verify",
        turn_id=created_turn,
        enabled_toolsets=group_toolsets,
    )
    assert "远程图片 URL 必须来自当前消息、显式引用或本轮联网搜索结果" in unobserved_stage
    cover_result = contextvars.copy_context().run(
        handle_function_call,
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {
                "action": "set_cover",
                "doc_token": created_token,
                "image_path": cover_path.name,
            },
        },
        task_id="sandbox-verify",
        session_id="sandbox-group-verify",
        turn_id=created_turn,
        enabled_toolsets=group_toolsets,
    )
    assert '"success": true' in cover_result
    next_turn_result = contextvars.copy_context().run(
        handle_function_call,
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {
                "action": "set_cover",
                "doc_token": created_token,
                "image_path": cover_path.name,
            },
        },
        task_id="sandbox-verify",
        session_id="sandbox-group-verify",
        turn_id="sandbox-group-verify:turn-two",
        enabled_toolsets=group_toolsets,
    )
    assert "必须在当前消息或显式引用中附上目标文档链接" in next_turn_result
finally:
    sandbox._run_trusted_script = original_run_trusted_script
    markdown_path.unlink(missing_ok=True)
    cover_path.unlink(missing_ok=True)
    staged_path.unlink(missing_ok=True)

trusted_mutation_user = next(iter(sandbox._GROUP_MUTATION_USER_IDS))
markdown_token = "doxcnSandboxVerifyMarkdownTarget"
markdown_url = f"https://whales.feishu.cn/docx/{markdown_token}"
sandbox._on_pre_gateway_dispatch(SimpleNamespace(
    source=SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="oc_verify_group",
        chat_type="group",
        user_id=trusted_mutation_user,
    ),
    text="delete the referenced document",
    reply_to_text=f"created: [{markdown_url}]({markdown_url})",
    channel_context="",
    media_urls=[],
))
assert markdown_token in sandbox._current_resource_refs.get()
assert markdown_url in sandbox._current_resource_refs.get()

original_run_trusted_script = sandbox._run_trusted_script
try:
    import subprocess

    sandbox._run_trusted_script = lambda _script, _argv, _workspace: subprocess.CompletedProcess(
        args=[], returncode=0, stdout="deleted", stderr=""
    )
    trusted_delete_result = handle_function_call(
        "tool_call",
        {
            "name": "feishu_doc_manage",
            "arguments": {"action": "delete", "doc_token": markdown_token},
        },
        task_id="sandbox-verify",
        enabled_toolsets=group_toolsets,
    )
    assert '"success": true' in trusted_delete_result
    assert '"action": "delete"' in trusted_delete_result
finally:
    sandbox._run_trusted_script = original_run_trusted_script
sandbox._current_user_id.set("ou_untrusted_verify")
sandbox._current_user_ids.set(frozenset({"ou_untrusted_verify"}))

# Default search_files path is rewritten to the verified wiki root instead of
# the process cwd, so the documented default invocation is both useful and safe.
search_args = {"pattern": "__sandbox_verify_no_match__"}
assert sandbox._on_pre_tool_call(tool_name="search_files", args=search_args) is None
assert search_args["path"] == str(sandbox._GROUP_ALLOWED_READ_ROOTS[0])

# Feishu resource reads are bound to URLs/tokens explicitly present in the
# current group message; arbitrary bot-readable documents are not ambient.
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
# A zero pytest exit alone is insufficient: skipped/xfail-only coverage also
# exits zero. Emit one machine-readable receipt only after every JUnit case
# passed cleanly, so Step 8e and the final PATCH evidence consume the same fact.
if [[ -x "${VENV_PYTHON}" ]] && [[ -r "${PLUGIN_TEST}" ]] && [[ -r "${PEOPLE_TEST}" ]] &&
    [[ -r "${DOC_MEDIA_TEST}" ]] && [[ -r "${DOC_STAGE_TEST}" ]] && [[ -r "${DOC_READ_TEST}" ]]; then
    _SANDBOX_JUNIT=$(mktemp -t hermes-sandbox-junit.XXXXXX)
    _SANDBOX_PYTEST_OUT=$(
        cd "${HERMES_HOME}" &&
            "${VENV_PYTHON}" -m pytest -q -p no:cacheprovider -o xfail_strict=true \
                -W error::pytest.PytestUnhandledThreadExceptionWarning \
                -W error::pytest.PytestUnraisableExceptionWarning \
                -W error::RuntimeWarning \
                -W error::pytest.PytestReturnNotNoneWarning \
                -W error::pytest.PytestCollectionWarning \
                --junitxml="${_SANDBOX_JUNIT}" "${PLUGIN_TEST}" "${PEOPLE_TEST}" "${DOC_MEDIA_TEST}" \
                "${DOC_STAGE_TEST}" "${DOC_READ_TEST}" 2>&1
    )
    _SANDBOX_PYTEST_RC=$?
    echo "${_SANDBOX_PYTEST_OUT}"
    if [[ ${_SANDBOX_PYTEST_RC} -eq 0 ]]; then
        _SANDBOX_COUNTS=$(
            "${VENV_PYTHON}" - "${_SANDBOX_JUNIT}" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
cases = list(root.iter("testcase"))
if not cases:
    raise SystemExit("sandbox verifier JUnit contained no test cases")
counts = {
    tag: sum(case.find(tag) is not None for case in cases)
    for tag in ("skipped", "failure", "error")
}
if any(counts.values()):
    raise SystemExit(f"sandbox verifier JUnit contains non-passing outcomes: {counts}")
print(f"{len(cases)} 0 0 0")
PY
        )
        _SANDBOX_COUNTS_RC=$?
        if [[ ${_SANDBOX_COUNTS_RC} -eq 0 ]]; then
            read -r _SANDBOX_PASSED _SANDBOX_SKIPPED _SANDBOX_FAILED _SANDBOX_ERRORS <<<"${_SANDBOX_COUNTS}"
            printf 'PATCH_VERIFY_RESULT sandbox passed=%s skipped=%s failed=%s errors=%s\n' \
                "${_SANDBOX_PASSED}" "${_SANDBOX_SKIPPED}" "${_SANDBOX_FAILED}" "${_SANDBOX_ERRORS}"
            echo "OK   sandbox and Feishu identity-sync regression tests passed"
        else
            echo "FAIL sandbox or Feishu identity-sync JUnit outcomes were incomplete"
            fail=1
        fi
    else
        echo "FAIL sandbox or Feishu identity-sync regression tests failed"
        fail=1
    fi
    rm -f -- "${_SANDBOX_JUNIT}"
    _SANDBOX_JUNIT=""
else
    echo "FAIL sandbox, Feishu identity-sync, or document-media regression inputs are unavailable"
    fail=1
fi

# 7. Runtime trace for the real gateway child process (HARD). Newer launchd
# plists supervise hermes_cli.stderr_timestamp directly, so `gateway status`
# reports the wrapper PID while plugin registration logs use the child PID.
# Prove both layers: launchd supervisor health from status, runtime identity
# from gateway.status.get_running_pid().
if [[ -r "${AGENT_LOG}" ]]; then
    agent_log_files=("${AGENT_LOG}")
    for rotated_log in "${AGENT_LOG}".*; do
        [[ -f "${rotated_log}" ]] && agent_log_files+=("${rotated_log}")
    done
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
    plugin_version=$("${VENV_PYTHON}" -c 'import sys,yaml; print((yaml.safe_load(open(sys.argv[1])) or {})["version"])' "${PLUGIN_MANIFEST}" 2>/dev/null || true)
    hypertex_required=$("${VENV_PYTHON}" -c 'import sys,yaml; c=yaml.safe_load(open(sys.argv[1])) or {}; h=(c.get("mcp_servers") or {}).get("hypertex") or {}; print("true" if h else "false")' "${ROOT_CONFIG}" 2>/dev/null || echo false)
    trusted_runtime_ids=$("${VENV_PYTHON}" -c 'import sys,yaml; c=yaml.safe_load(open(sys.argv[1])) or {}; keys=("trusted_feishu_user_ids_for_group_mutations", "trusted_feishu_user_ids_for_group_hypertex"); print("\n".join(sorted({str(v) for k in keys for v in (c.get(k) or []) if str(v)})))' "${PLUGIN_CONFIG}" 2>/dev/null || true)
    current_mcp_tasks=""
    if [[ -n "${gateway_pid}" ]]; then
        current_reg=$(grep -h "sandbox: registered (pid=${gateway_pid}," "${agent_log_files[@]}" | sort | tail -1 || true)
        if [[ -n "${current_reg}" ]]; then
            current_reg_timestamp=${current_reg:0:23}
            for _mcp_wait_attempt in {1..20}; do
                current_mcp_tasks=$(
                    grep -h "MCP server 'hypertex'.*pid=${gateway_pid}.*mcp__hypertex__tasks_get.*mcp__hypertex__tasks_cancel.*mcp__hypertex__tasks_update" "${agent_log_files[@]}" |
                        awk -v started="${current_reg_timestamp}" 'substr($0, 1, 23) >= started' |
                        sort | head -1 || true
                )
                [[ -n "${current_mcp_tasks}" ]] && break
                sleep 0.5
            done
        fi
    fi
    runtime_trust_ok=true
    while IFS= read -r trusted_user_id; do
        [[ -z "${trusted_user_id}" ]] && continue
        if ! echo "${current_reg}" | grep -q "${trusted_user_id}"; then
            runtime_trust_ok=false
            break
        fi
    done <<<"${trusted_runtime_ids}"
    runtime_hypertex_ok=true
    if [[ "${hypertex_required}" == true ]]; then
        if [[ -z "${current_mcp_tasks}" ]] ||
            ! echo "${current_reg}" | grep -q 'mcp__hypertex__hypertex_create_case' ||
            ! echo "${current_reg}" | grep -q 'mcp__hypertex__tasks_get'; then
            runtime_hypertex_ok=false
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
    elif [[ "${hypertex_required}" == true && -z "${current_mcp_tasks}" ]]; then
        echo "FAIL no standard MCP Tasks registration after sandbox trace for gateway child PID ${gateway_pid}"
        fail=1
    elif [[ -n "${plugin_version}" ]] &&
        echo "${current_reg}" | grep -q "version=${plugin_version}" &&
        echo "${current_reg}" | grep -q 'active=True' &&
        echo "${current_reg}" | grep -q 'tool_search' &&
        echo "${current_reg}" | grep -q 'tool_describe' &&
        echo "${current_reg}" | grep -q 'group_cache' &&
        echo "${current_reg}" | grep -q 'feishu_doc_manage' &&
        echo "${current_reg}" | grep -q 'group_image_generate' &&
        echo "${current_reg}" | grep -q 'group_chart_generate' &&
        echo "${current_reg}" | grep -q 'doc_delete_only=True' &&
        echo "${current_reg}" | grep -q "doc_media_actions=\['insert_image', 'replace_image', 'set_cover', 'stage_image_urls'\]" &&
        echo "${current_reg}" | grep -q 'doc_image_max_bytes=20971520' &&
        echo "${current_reg}" | grep -q 'hypertex_routing_policy=server-owned/non-observable' &&
        echo "${current_reg}" | grep -q 'hypertex_chats=' &&
        echo "${current_reg}" | grep -q 'hypertex_users=' &&
        echo "${current_reg}" | grep -q 'image_chats=' &&
        echo "${current_reg}" | grep -q 'image_script=' &&
        echo "${current_reg}" | grep -q 'chart_chats=' &&
        echo "${current_reg}" | grep -q 'chart_script=' &&
        [[ "${runtime_hypertex_ok}" == true ]] &&
        [[ "${runtime_trust_ok}" == true ]]; then
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
