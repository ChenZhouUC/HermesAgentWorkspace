import json
import importlib.util
import subprocess
import sys
import traceback
from pathlib import Path

import pytest

import plugins.sandbox as sandbox


@pytest.fixture
def group_config(tmp_path, monkeypatch):
    workspace_root = (tmp_path / "tmp" / "group-workspaces").resolve()
    scripts_root = (tmp_path / "my-skills" / "feishu-docs" / "scripts").resolve()
    scripts_root.mkdir(parents=True)
    for filename in sandbox._FEISHU_SCRIPT_FILES.values():
        (scripts_root / filename).write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(sandbox, "_CONFIG_LOADED", True)
    monkeypatch.setattr(sandbox, "_OWNER_CHAT_IDS", frozenset({"owner-dm"}))
    monkeypatch.setattr(
        sandbox,
        "_ALLOWED_TOOLS",
        frozenset({"web_search", "web_extract", "vision_analyze", "image_generate"}),
    )
    monkeypatch.setattr(
        sandbox,
        "_GROUP_ALLOWED_TOOLS",
        frozenset(
            {
                "tool_search",
                "tool_describe",
                "skills_list",
                "skill_view",
                "feishu_doc_read",
                "read_file",
                "search_files",
                "group_cache",
                "feishu_doc_manage",
            }
        ),
    )
    wiki_root = (tmp_path / "wiki").resolve()
    wiki_root.mkdir()
    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_READ_ROOTS", (wiki_root,))
    monkeypatch.setattr(sandbox, "_GROUP_WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(
        sandbox,
        "_GROUP_ALLOWED_SCRIPT_ACTIONS",
        frozenset(sandbox._FEISHU_SCRIPT_FILES),
    )
    monkeypatch.setattr(sandbox, "_FEISHU_DOC_SCRIPTS_ROOT", scripts_root)
    monkeypatch.setattr(sandbox, "_PYTHON_EXECUTABLE", Path(sys.executable).resolve())
    monkeypatch.setattr(sandbox, "_REQUIRE_PROCESS_SANDBOX", True)
    monkeypatch.setattr(sandbox, "_SCRIPT_TIMEOUT_SECONDS", 30)
    sandbox._current_platform.set("feishu")
    sandbox._current_chat_id.set("group-one")
    sandbox._current_chat_type.set("group")
    return {
        "workspace_root": workspace_root,
        "scripts_root": scripts_root,
        "wiki_root": wiki_root,
    }


def _result(payload):
    return json.loads(payload)


def test_group_workspace_is_stable_isolated_and_does_not_leak_chat_id(group_config):
    first = sandbox._workspace_for_chat("oc_secret_group")
    same = sandbox._workspace_for_chat("oc_secret_group")
    other = sandbox._workspace_for_chat("oc_other_group")

    assert first == same
    assert first != other
    assert first.parent == group_config["workspace_root"]
    assert "oc_secret_group" not in str(first)


def test_group_cache_crud_stays_inside_current_workspace(group_config):
    workspace = sandbox._workspace_for_chat("group-one")
    written = _result(
        sandbox._handle_group_cache(
            {"action": "write", "path": "drafts/doc.md", "content": "hello", "overwrite": False}
        )
    )
    assert written["success"] is True
    assert written["path"] == "drafts/doc.md"
    assert str(workspace) not in json.dumps(written)

    sandbox._handle_group_cache({"action": "append", "path": "drafts/doc.md", "content": " world"})
    read = _result(sandbox._handle_group_cache({"action": "read", "path": "drafts/doc.md"}))
    assert read["path"] == "drafts/doc.md"
    assert read["content"] == "hello world"

    sandbox._handle_group_cache({"action": "move", "path": "drafts/doc.md", "destination": "done/final.md"})
    listing = _result(sandbox._handle_group_cache({"action": "list", "path": ".", "recursive": True}))
    assert "workspace" not in listing
    assert listing["workspace_id"] == sandbox._workspace_id("group-one")
    assert str(workspace) not in json.dumps(listing)
    assert any(item["path"] == "done/final.md" for item in listing["entries"])

    sandbox._handle_group_cache({"action": "delete", "path": "done", "recursive": True})
    assert not (workspace / "done").exists()


def test_group_cache_and_doc_tool_do_not_return_absolute_workspace_paths(group_config, monkeypatch):
    workspace = sandbox._workspace_for_chat("group-one")

    def fake_run(_script, _argv, _workspace):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(sandbox, "_run_trusted_script", fake_run)
    cache_result = _result(
        sandbox._handle_group_cache({"action": "write", "path": "drafts/doc.md", "content": "hello", "overwrite": True})
    )
    doc_result = _result(
        sandbox._handle_feishu_doc_manage(
            {
                "action": "append",
                "doc_token": "doxcnToken_123",
                "markdown_path": "drafts/doc.md",
            }
        )
    )

    assert cache_result["path"] == "drafts/doc.md"
    assert doc_result["workspace_id"] == sandbox._workspace_id("group-one")
    assert str(workspace) not in json.dumps(cache_result)
    assert str(workspace) not in json.dumps(doc_result)


@pytest.mark.parametrize("path", ["../wiki/secret.md", "/etc/passwd", "~/secret", "a/../../secret"])
def test_group_cache_rejects_paths_outside_workspace(group_config, path):
    with pytest.raises(ValueError):
        sandbox._handle_group_cache({"action": "write", "path": path, "content": "x"})


def test_group_cache_rejects_symlink_escape(group_config, tmp_path):
    workspace = sandbox._workspace_for_chat("group-one")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        sandbox._handle_group_cache({"action": "write", "path": "link/payload", "content": "x"})


def test_direct_reads_allow_wiki_and_only_the_current_group_workspace(group_config):
    current = sandbox._workspace_for_chat("group-one")
    other = sandbox._workspace_for_chat("group-two")
    (current / "mine.txt").write_text("mine", encoding="utf-8")
    (other / "theirs.txt").write_text("theirs", encoding="utf-8")

    assert (
        sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(group_config["wiki_root"] / "x.md")}) is None
    )
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(current / "mine.txt")}) is None
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(other / "theirs.txt")}) == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }


def test_group_has_no_terminal_or_direct_write_surface(group_config, tmp_path):
    assert sandbox._on_pre_tool_call(tool_name="group_cache", args={"action": "list"}) is None
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args={"action": "delete"}) is None
    for tool in ("terminal", "process", "write_file", "patch", "skill_manage"):
        assert sandbox._on_pre_tool_call(tool_name=tool, args={}) == {
            "action": "block",
            "message": sandbox._BLOCK_MESSAGE,
        }
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(tmp_path / "skills" / "x.py")}) == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }


def test_group_allows_readonly_tool_discovery_bridge(group_config):
    assert sandbox._on_pre_tool_call(tool_name="tool_search", args={"query": "group cache"}) is None
    assert sandbox._on_pre_tool_call(tool_name="tool_describe", args={"name": "group_cache"}) is None


def test_invalid_config_fails_closed_for_feishu_but_not_cli(group_config, monkeypatch):
    monkeypatch.setattr(sandbox, "_CONFIG_LOADED", False)
    assert sandbox._on_pre_tool_call(tool_name="web_search", args={}) == {
        "action": "block",
        "message": sandbox._CONFIG_BLOCK_MESSAGE,
    }

    sandbox._current_platform.set("local")
    assert sandbox._on_pre_tool_call(tool_name="terminal", args={"command": "echo ok"}) is None


def test_owner_dm_keeps_full_access(group_config):
    sandbox._current_chat_id.set("owner-dm")
    sandbox._current_chat_type.set("private")
    assert sandbox._on_pre_tool_call(tool_name="terminal", args={"command": "echo ok"}) is None


def test_script_tool_schema_has_no_command_script_path_or_raw_argv():
    properties = sandbox.FEISHU_DOC_MANAGE_SCHEMA["parameters"]["properties"]
    assert sandbox.FEISHU_DOC_MANAGE_SCHEMA["parameters"]["additionalProperties"] is False
    assert "command" not in properties
    assert "script" not in properties
    assert "arguments" not in properties


def test_script_actions_map_only_to_fixed_existing_files(group_config):
    workspace = sandbox._workspace_for_chat("group-one")
    action, script, argv = sandbox._build_script_argv(
        {"action": "create", "title": "Test", "content": "# Body"},
        workspace,
    )
    assert action == "create"
    assert script == group_config["scripts_root"] / "create_new_doc_from_md.py"
    assert argv[0].startswith(str(workspace))
    assert Path(argv[0]).read_text(encoding="utf-8") == "# Body\n"
    assert argv[1] == "Test"

    action, script, argv = sandbox._build_script_argv(
        {"action": "delete", "doc_token": "doxcnToken_123"},
        workspace,
    )
    assert (action, script.name, argv) == ("delete", "delete_doc.py", ["doxcnToken_123"])


def test_script_source_must_be_markdown_in_current_workspace(group_config):
    workspace = sandbox._workspace_for_chat("group-one")
    (workspace / "draft.md").write_text("body", encoding="utf-8")
    _, _, argv = sandbox._build_script_argv(
        {"action": "append", "doc_token": "doxcnToken_123", "markdown_path": "draft.md"},
        workspace,
    )
    assert argv == ["doxcnToken_123", str(workspace / "draft.md")]

    for bad_path in ("../outside.md", "/tmp/outside.md", "missing.md"):
        with pytest.raises((ValueError, FileNotFoundError)):
            sandbox._build_script_argv(
                {"action": "append", "doc_token": "doxcnToken_123", "markdown_path": bad_path},
                workspace,
            )


def test_script_arguments_reject_shell_payloads_and_non_feishu_urls(group_config):
    workspace = sandbox._workspace_for_chat("group-one")
    with pytest.raises(ValueError):
        sandbox._build_script_argv({"action": "delete", "doc_token": "token; rm -rf /"}, workspace)
    with pytest.raises(ValueError):
        sandbox._build_script_argv({"action": "read_url", "url": "https://example.com/docx/token"}, workspace)
    with pytest.raises(ValueError):
        sandbox._build_script_argv({"action": "download_file", "url": "https://whales.feishu.cn/docx/token"}, workspace)


def test_script_runner_uses_argv_process_sandbox_and_workspace_env(group_config, monkeypatch):
    workspace = sandbox._workspace_for_chat("group-one")
    script = group_config["scripts_root"] / "delete_doc.py"
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return sandbox.subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(sandbox.subprocess, "run", fake_run)
    sandbox._run_trusted_script(script, ["doxcnToken_123"], workspace)

    command = captured["command"]
    assert command[:2] == ["/usr/bin/sandbox-exec", "-p"]
    assert str(workspace) in command[2]
    assert command[-2:] == [str(script), "doxcnToken_123"]
    assert captured["cwd"] == str(script.parent)
    assert captured["env"]["HERMES_GROUP_WORKSPACE"] == str(workspace)
    assert captured["env"]["TMPDIR"] == str(workspace)
    assert captured["env"]["HERMES_GROUP_MAX_DOWNLOAD_BYTES"] == "50000000"


def test_trusted_script_output_redacts_feishu_credentials():
    raw = (
        "Authorization: Bearer tenant-token-123\n"
        "FEISHU_APP_SECRET=app-secret-456\n"
        "tenant_access_token: access-token-789"
    )
    redacted = sandbox._redact_tool_output(raw)
    assert "tenant-token-123" not in redacted
    assert "app-secret-456" not in redacted
    assert "access-token-789" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_upload_failure_traceback_does_not_leak_tenant_token(monkeypatch, tmp_path):
    scripts_root = Path(__file__).resolve().parents[2] / "my-skills/productivity/feishu-docs/scripts"
    monkeypatch.syspath_prepend(str(scripts_root))
    spec = importlib.util.spec_from_file_location("sandbox_test_feishu_common", scripts_root / "feishu_common.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    markdown = tmp_path / "draft.md"
    markdown.write_text("body", encoding="utf-8")
    secret = "tenant-token-must-not-leak"

    def fail(command):
        raise subprocess.CalledProcessError(7, command, output=b"upload failed")

    monkeypatch.setattr(module.subprocess, "check_output", fail)
    try:
        module.upload_md(secret, str(markdown))
    except RuntimeError:
        rendered = traceback.format_exc()
    else:  # pragma: no cover - the stub always fails
        raise AssertionError("upload_md unexpectedly succeeded")

    assert secret not in rendered
    assert "curl upload failed (exit 7)" in rendered


def test_group_download_helper_rejects_declared_and_streamed_oversize(monkeypatch):
    scripts_root = Path(__file__).resolve().parents[2] / "my-skills/productivity/feishu-docs/scripts"
    monkeypatch.syspath_prepend(str(scripts_root))
    spec = importlib.util.spec_from_file_location(
        "sandbox_test_download_feishu_file", scripts_root / "download_feishu_file.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setenv("HERMES_GROUP_MAX_DOWNLOAD_BYTES", "4")

    class DeclaredLarge:
        headers = {"Content-Length": "5"}

        def read(self, _size=None):
            raise AssertionError("oversized response must be rejected before reading")

    class StreamedLarge:
        headers = {}

        def read(self, size=None):
            assert size == 5
            return b"12345"

    with pytest.raises(RuntimeError, match="download limit"):
        module._read_response_data(DeclaredLarge())
    with pytest.raises(RuntimeError, match="download limit"):
        module._read_response_data(StreamedLarge())


@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").is_file(), reason="macOS sandbox-exec is unavailable")
def test_process_sandbox_allows_workspace_write_and_denies_external_write(group_config, tmp_path):
    workspace = sandbox._workspace_for_chat("group-one")
    script = group_config["scripts_root"] / "sandbox_probe.py"
    script.write_text(
        "import os, pathlib, sys\n"
        "pathlib.Path(os.environ['HERMES_GROUP_WORKSPACE'], 'allowed.txt').write_text('ok')\n"
        "pathlib.Path(sys.argv[1]).write_text('blocked')\n",
        encoding="utf-8",
    )
    outside = tmp_path / "must-not-exist.txt"

    result = sandbox._run_trusted_script(script, [str(outside)], workspace)

    assert result.returncode != 0
    assert (workspace / "allowed.txt").read_text(encoding="utf-8") == "ok"
    assert not outside.exists()


def test_actual_config_loads_and_registers_structured_tools(monkeypatch):
    assert sandbox._load_config() is True
    assert sandbox._OWNER_CHAT_IDS
    calls = {"tools": [], "hooks": []}

    class Context:
        def register_tool(self, **kwargs):
            calls["tools"].append(kwargs)

        def register_hook(self, name, callback):
            calls["hooks"].append((name, callback))

    sandbox.register(Context())

    assert {item["name"] for item in calls["tools"]} == {"group_cache", "feishu_doc_manage"}
    assert {item["toolset"] for item in calls["tools"]} == {"sandbox_group"}
    assert {name for name, _callback in calls["hooks"]} == {"pre_gateway_dispatch", "pre_tool_call"}

    sandbox._current_platform.set("feishu")
    sandbox._current_chat_id.set(next(iter(sandbox._OWNER_CHAT_IDS)))
    sandbox._current_chat_type.set("private")
    assert sandbox._on_pre_tool_call(tool_name="terminal", args={}) is None

    sandbox._current_chat_id.set("oc_non_owner_regression_probe")
    sandbox._current_chat_type.set("group")
    assert sandbox._on_pre_tool_call(tool_name="terminal", args={}) == {
        "action": "block",
        "message": sandbox._BLOCK_MESSAGE,
    }
