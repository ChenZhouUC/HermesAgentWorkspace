import json
import importlib.util
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

import pytest

import plugins.sandbox as sandbox


@pytest.fixture
def group_config(tmp_path, monkeypatch):
    workspace_root = (tmp_path / "tmp" / "group-workspaces").resolve()
    hypertex_staging_root = (tmp_path / "tmp" / "hypertex-assets").resolve()
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
                sandbox._HYPERTEX_LIST_TOOL,
                sandbox._HYPERTEX_CREATE_TOOL,
                sandbox._HYPERTEX_ITERATE_TOOL,
                sandbox._HYPERTEX_CASE_TOOL,
                sandbox._HYPERTEX_TASK_TOOL,
                sandbox._HYPERTEX_CANCEL_TOOL,
                sandbox._HYPERTEX_UPDATE_TOOL,
            }
        ),
    )
    monkeypatch.setattr(
        sandbox,
        "_GROUP_MUTATION_USER_IDS",
        frozenset({"trusted-user"}),
    )
    monkeypatch.setattr(
        sandbox,
        "_GROUP_HYPERTEX_CHAT_IDS",
        frozenset({"group-one"}),
    )
    monkeypatch.setattr(
        sandbox,
        "_GROUP_HYPERTEX_USER_IDS",
        frozenset({"trusted-user"}),
    )
    wiki_root = (tmp_path / "wiki").resolve()
    wiki_root.mkdir()
    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_READ_ROOTS", (wiki_root,))
    monkeypatch.setattr(sandbox, "_GROUP_WORKSPACE_ROOT", workspace_root)
    monkeypatch.setattr(sandbox, "_HYPERTEX_ASSET_STAGING_ROOT", hypertex_staging_root)
    monkeypatch.setattr(sandbox, "_HYPERTEX_MAX_ASSET_BYTES", 50_000_000)
    monkeypatch.setattr(sandbox, "_HYPERTEX_MAX_ASSETS_PER_TURN", 6)
    monkeypatch.setattr(sandbox, "_HYPERTEX_ASSET_STAGING_TTL_SECONDS", 86_400)
    monkeypatch.setattr(
        sandbox,
        "_GROUP_ALLOWED_SCRIPT_ACTIONS",
        frozenset(sandbox._FEISHU_SCRIPT_FILES),
    )
    monkeypatch.setattr(sandbox, "_FEISHU_DOC_SCRIPTS_ROOT", scripts_root)
    monkeypatch.setattr(sandbox, "_PYTHON_EXECUTABLE", Path(sys.executable).resolve())
    monkeypatch.setattr(sandbox, "_REQUIRE_PROCESS_SANDBOX", True)
    monkeypatch.setattr(sandbox, "_SCRIPT_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(sandbox, "_EPHEMERAL_READ_PATHS_BY_CHAT", {})
    sandbox._current_platform.set("feishu")
    sandbox._current_chat_id.set("group-one")
    sandbox._current_chat_type.set("group")
    sandbox._current_user_id.set("trusted-user")
    sandbox._current_resource_refs.set(frozenset())
    sandbox._current_media_paths.set(tuple())
    sandbox._current_hypertex_staged_paths.set(tuple())
    sandbox._current_hypertex_call_count.set(0)
    return {
        "workspace_root": workspace_root,
        "hypertex_staging_root": hypertex_staging_root,
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
    sandbox._current_resource_refs.set(sandbox._resource_ref_candidates("doxcnToken_123"))
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


def test_direct_read_rejects_wiki_symlink_escape(group_config, tmp_path):
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = group_config["wiki_root"] / "outside-link.txt"
    link.symlink_to(outside)

    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(link)}) == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }


def test_group_has_no_terminal_or_direct_write_surface(group_config, tmp_path):
    assert sandbox._on_pre_tool_call(tool_name="group_cache", args={"action": "list"}) is None
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args={"action": "create"}) is None
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


def test_group_allows_declared_core_tools_but_not_outsider_dm_vision_tools(group_config):
    for tool in ("clarify", "web_search", "web_extract"):
        assert sandbox._on_pre_tool_call(tool_name=tool, args={}) is None
    for tool in ("vision_analyze", "image_generate"):
        assert sandbox._on_pre_tool_call(tool_name=tool, args={}) == {
            "action": "block",
            "message": sandbox._BLOCK_MESSAGE,
        }


def test_group_search_default_is_rewritten_to_wiki_root(group_config):
    args = {"pattern": "Hermes"}
    assert sandbox._on_pre_tool_call(tool_name="search_files", args=args) is None
    assert args["path"] == str(group_config["wiki_root"])


def test_group_feishu_reads_require_current_message_reference(group_config):
    token = "doxcnAuditToken_123"
    url = f"https://whales.feishu.cn/docx/{token}"
    event = SimpleNamespace(
        source=SimpleNamespace(
            platform=SimpleNamespace(value="feishu"),
            chat_id="group-one",
            chat_type="group",
            user_id="member-user",
        ),
        text=f"请读取 {url}",
        reply_to_text="",
        channel_context="",
    )
    sandbox._on_pre_gateway_dispatch(event)

    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_read", args={"doc_token": token}) is None
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args={"action": "read_url", "url": url}) is None
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_read", args={"doc_token": "doxcnOtherToken"}) == {
        "action": "block",
        "message": sandbox._RESOURCE_BLOCK_MESSAGE,
    }


def test_group_doc_writes_allow_members_but_delete_requires_trusted_user(group_config):
    token = "doxcnAuditToken_123"
    url = f"https://whales.feishu.cn/docx/{token}"
    sandbox._current_resource_refs.set(sandbox._resource_ref_candidates(url))

    sandbox._current_user_id.set("member-user")
    for args in (
        {"action": "create"},
        {"action": "append", "doc_token": token},
        {"action": "rebuild", "doc_token": token},
    ):
        assert sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args=args) is None
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args={"action": "delete", "doc_token": token}) == {
        "action": "block",
        "message": sandbox._MUTATION_BLOCK_MESSAGE,
    }

    sandbox._current_user_id.set("trusted-user")
    assert (
        sandbox._on_pre_tool_call(tool_name="feishu_doc_manage", args={"action": "delete", "doc_token": token}) is None
    )
    for action in ("append", "rebuild", "delete"):
        assert sandbox._on_pre_tool_call(
            tool_name="feishu_doc_manage",
            args={"action": action, "doc_token": "doxcnOtherToken"},
        ) == {"action": "block", "message": sandbox._MUTATION_BLOCK_MESSAGE}

    sandbox._current_user_id.set("member-user")
    assert sandbox._on_pre_tool_call(
        tool_name="feishu_doc_manage",
        args={"action": "delete", "doc_token": "doxcnOtherToken"},
    ) == {"action": "block", "message": sandbox._MUTATION_BLOCK_MESSAGE}

    with pytest.raises(PermissionError, match="仅允许受信任"):
        sandbox._handle_feishu_doc_manage({"action": "delete", "doc_token": token})


def test_new_gateway_event_clears_stale_resource_references(group_config):
    sandbox._current_resource_refs.set(frozenset({"doxcnStaleToken"}))
    event = SimpleNamespace(
        source=SimpleNamespace(
            platform=SimpleNamespace(value="feishu"),
            chat_id="group-one",
            chat_type="group",
            user_id="member-user",
        ),
        text="普通消息",
        reply_to_text="",
        channel_context="",
    )
    sandbox._on_pre_gateway_dispatch(event)
    assert sandbox._current_resource_refs.get() == frozenset()

    sandbox._current_resource_refs.set(frozenset({"doxcnStaleAgain"}))
    sandbox._on_pre_gateway_dispatch(None)
    assert sandbox._current_platform.get() is None
    assert sandbox._current_resource_refs.get() == frozenset()


def test_channel_history_does_not_grant_feishu_resource_access(group_config):
    token = "doxcnHistoryOnlyToken"
    event = SimpleNamespace(
        source=SimpleNamespace(
            platform=SimpleNamespace(value="feishu"),
            chat_id="group-one",
            chat_type="group",
            user_id="member-user",
        ),
        text="当前消息没有链接",
        reply_to_text="",
        channel_context=f"Earlier: https://whales.feishu.cn/docx/{token}",
    )
    sandbox._on_pre_gateway_dispatch(event)
    assert sandbox._on_pre_tool_call(tool_name="feishu_doc_read", args={"doc_token": token}) == {
        "action": "block",
        "message": sandbox._RESOURCE_BLOCK_MESSAGE,
    }


def test_web_extract_grants_only_exact_current_group_cache_file(group_config, tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    web_root = hermes_home / "cache" / "web"
    web_root.mkdir(parents=True)
    url = "https://example.com/long-page"
    digest = sandbox.hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    allowed = web_root / f"example.com-{digest}.md"
    denied = web_root / "denied.md"
    allowed.write_text("full page", encoding="utf-8")
    denied.write_text("other page", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    sandbox._on_post_tool_call(
        tool_name="web_extract",
        result=json.dumps(
            {
                "results": [
                    {
                        "url": url,
                        "content": (f"Full text saved to: {denied}\nFull text saved to: {allowed}\n"),
                    }
                ]
            }
        ),
    )
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(allowed)}) is None
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(denied)}) == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }

    # A new message in the same chat revokes the prior turn's cache grant.
    sandbox._on_pre_gateway_dispatch(
        SimpleNamespace(
            source=SimpleNamespace(
                platform=SimpleNamespace(value="feishu"),
                chat_id="group-one",
                chat_type="group",
                user_id="member-user",
            ),
            text="next turn",
            reply_to_text="",
        )
    )
    assert sandbox._on_pre_tool_call(tool_name="read_file", args={"path": str(allowed)}) == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }


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


def test_owner_dm_hypertex_create_is_pinned_and_stages_current_attachments(group_config, tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "doc_aaaaaaaaaaaa_Report.pdf"
    second = second_dir / "doc_bbbbbbbbbbbb_Report.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    event = SimpleNamespace(
        source=SimpleNamespace(
            platform=SimpleNamespace(value="feishu"),
            chat_id="owner-dm",
            chat_type="private",
            user_id="owner-user",
        ),
        text="做一份演示文稿",
        reply_to_text="",
        channel_context="",
        media_urls=[str(first), str(second)],
    )
    sandbox._on_pre_gateway_dispatch(event)
    args = {
        "prompt": "做一份演示文稿",
        "owner_username": "chenzhou",
        "agent": "qwen",
        "type": "brochure",
        "asset_paths": ["/etc/passwd"],
    }

    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_CREATE_TOOL, args=args) is None
    assert args["owner_username"] == "hermes"
    assert args["agent"] == "codex"
    assert args["type"] == "deck"
    staged = [Path(path) for path in args["asset_paths"]]
    assert [path.name for path in staged] == ["Report.pdf", "Report-2.pdf"]
    assert [path.read_bytes() for path in staged] == [b"first", b"second"]
    assert all(path.is_relative_to(group_config["hypertex_staging_root"]) for path in staged)


def test_owner_dm_hypertex_reads_are_pinned_to_contributor(group_config):
    sandbox._current_chat_id.set("owner-dm")
    sandbox._current_chat_type.set("private")
    for tool_name in (
        sandbox._HYPERTEX_LIST_TOOL,
        sandbox._HYPERTEX_CASE_TOOL,
    ):
        sandbox._current_hypertex_call_count.set(0)
        args = {"username": "chenzhou"}
        assert sandbox._on_pre_tool_call(tool_name=tool_name, args=args) is None
        assert args["username"] == "hermes"

    sandbox._current_hypertex_call_count.set(0)
    task_args = {"task_id": "2"}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_TASK_TOOL, args=task_args) is None
    assert task_args == {"task_id": "2"}


def test_owner_dm_hypertex_iterate_is_pinned_and_stages_current_attachments(group_config, tmp_path):
    attachment = tmp_path / "doc_aaaaaaaaaaaa_Update.pptx"
    attachment.write_bytes(b"pptx")
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="owner-dm",
        chat_type="private",
        user_id="owner-user",
    )
    sandbox._on_pre_gateway_dispatch(
        SimpleNamespace(source=source, text="iterate", reply_to_text="", media_urls=[str(attachment)])
    )
    args = {
        "case_name": "Demo",
        "prompt": "更新内容",
        "username": "chenzhou",
        "agent": "qwen",
        "asset_paths": ["/etc/passwd"],
    }

    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_ITERATE_TOOL, args=args) is None
    assert args["username"] == "hermes"
    assert args["agent"] == "codex"
    assert len(args["asset_paths"]) == 1
    assert Path(args["asset_paths"][0]).name == "Update.pptx"


def test_owner_dm_allows_only_one_hypertex_call_per_inbound_turn(group_config):
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="owner-dm",
        chat_type="private",
        user_id="owner-user",
    )
    sandbox._on_pre_gateway_dispatch(SimpleNamespace(source=source, text="create", reply_to_text="", media_urls=[]))
    create_args = {"prompt": "create"}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_CREATE_TOOL, args=create_args) is None

    query_args = {"task_id": 2}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_TASK_TOOL, args=query_args) == {
        "action": "block",
        "message": sandbox._HYPERTEX_ONE_CALL_MESSAGE,
    }

    sandbox._on_pre_gateway_dispatch(SimpleNamespace(source=source, text="query", reply_to_text="", media_urls=[]))
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_TASK_TOOL, args=query_args) is None
    assert query_args == {"task_id": 2}


def test_new_owner_dm_turn_drops_previous_hypertex_attachments(group_config, tmp_path):
    attachment = tmp_path / "doc_aaaaaaaaaaaa_Source.pptx"
    attachment.write_bytes(b"pptx")
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="owner-dm",
        chat_type="private",
        user_id="owner-user",
    )
    sandbox._on_pre_gateway_dispatch(
        SimpleNamespace(source=source, text="first", reply_to_text="", media_urls=[str(attachment)])
    )
    first_args = {"prompt": "first"}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_CREATE_TOOL, args=first_args) is None
    assert first_args["asset_paths"]

    sandbox._on_pre_gateway_dispatch(SimpleNamespace(source=source, text="second", reply_to_text="", media_urls=[]))
    second_args = {"prompt": "second"}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_CREATE_TOOL, args=second_args) is None
    assert second_args["asset_paths"] == []


def test_trusted_group_hypertex_create_is_pinned_and_stages_current_attachments(group_config, tmp_path):
    attachment = tmp_path / "doc_aaaaaaaaaaaa_Group.pdf"
    attachment.write_bytes(b"pdf")
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="group-one",
        chat_type="group",
        user_id="trusted-user",
    )
    sandbox._on_pre_gateway_dispatch(
        SimpleNamespace(source=source, text="做一份演示文稿", reply_to_text="", media_urls=[str(attachment)])
    )
    args = {
        "prompt": "做一份演示文稿",
        "owner_username": "someone-else",
        "agent": "qwen",
        "type": "brochure",
        "asset_paths": ["/etc/passwd"],
    }

    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_CREATE_TOOL, args=args) is None
    assert args["owner_username"] == "hermes"
    assert args["agent"] == "codex"
    assert args["type"] == "deck"
    assert len(args["asset_paths"]) == 1
    assert Path(args["asset_paths"][0]).name == "Group.pdf"


def test_group_hypertex_is_limited_to_trusted_testers(group_config):
    sandbox._current_user_id.set("untrusted-user")

    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_LIST_TOOL,
        args={"username": "hermes"},
    ) == {"action": "block", "message": sandbox._HYPERTEX_GROUP_BLOCK_MESSAGE}


def test_group_hypertex_is_limited_to_enabled_chats_even_for_trusted_testers(group_config):
    sandbox._current_chat_id.set("group-two")

    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_LIST_TOOL,
        args={"username": "hermes"},
    ) == {"action": "block", "message": sandbox._HYPERTEX_GROUP_CHAT_BLOCK_MESSAGE}


def test_trusted_group_hypertex_allows_one_call_per_inbound_turn(group_config):
    source = SimpleNamespace(
        platform=SimpleNamespace(value="feishu"),
        chat_id="group-one",
        chat_type="group",
        user_id="trusted-user",
    )
    sandbox._on_pre_gateway_dispatch(SimpleNamespace(source=source, text="query", reply_to_text="", media_urls=[]))
    list_args = {"username": "someone-else"}
    assert sandbox._on_pre_tool_call(tool_name=sandbox._HYPERTEX_LIST_TOOL, args=list_args) is None
    assert list_args == {"username": "hermes"}
    assert sandbox._on_pre_tool_call(
        tool_name=sandbox._HYPERTEX_TASK_TOOL,
        args={"task_id": "7"},
    ) == {"action": "block", "message": sandbox._HYPERTEX_ONE_CALL_MESSAGE}


def test_outsider_dm_keeps_safe_base_allowlist(group_config):
    sandbox._current_chat_id.set("outsider-dm")
    sandbox._current_chat_type.set("private")
    for tool in ("web_search", "web_extract", "vision_analyze", "image_generate"):
        assert sandbox._on_pre_tool_call(tool_name=tool, args={}) is None
    assert sandbox._on_pre_tool_call(tool_name="terminal", args={}) == {
        "action": "block",
        "message": sandbox._BLOCK_MESSAGE,
    }


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
    assert {name for name, _callback in calls["hooks"]} == {
        "pre_gateway_dispatch",
        "pre_tool_call",
        "post_tool_call",
    }

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
