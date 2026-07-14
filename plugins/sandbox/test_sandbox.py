import plugins.sandbox as sandbox


def test_group_terminal_allows_existing_script_under_configured_root(tmp_path, monkeypatch):
    script_root = tmp_path / "skills"
    script_root.mkdir()
    script = script_root / "tool.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_SCRIPT_ROOTS", (script_root.resolve(),))

    assert sandbox._terminal_allowed_for_group({"command": "python tool.py --name value", "workdir": str(script_root)})


def test_group_terminal_allows_existing_script_with_quoted_content(tmp_path, monkeypatch):
    script_root = tmp_path / "skills"
    script_root.mkdir()
    script = script_root / "create_doc.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_SCRIPT_ROOTS", (script_root.resolve(),))

    assert sandbox._terminal_allowed_for_group(
        {
            "command": 'python create_doc.py --title "T" --content "line 1; a | b\\nline 2"',
            "workdir": str(script_root),
        }
    )


def test_group_terminal_rejects_new_or_compound_code(tmp_path, monkeypatch):
    script_root = tmp_path / "skills"
    script_root.mkdir()
    script = script_root / "tool.py"
    script.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_SCRIPT_ROOTS", (script_root.resolve(),))

    assert not sandbox._terminal_allowed_for_group({"command": "python -c 'print(1)'", "workdir": str(script_root)})
    assert not sandbox._terminal_allowed_for_group({"command": "python missing.py", "workdir": str(script_root)})
    assert not sandbox._terminal_allowed_for_group(
        {"command": "python tool.py ; rm -rf /tmp/nope", "workdir": str(script_root)}
    )


def test_group_terminal_scripts_outside_allowlisted_skill_dir_are_rejected(tmp_path, monkeypatch):
    # Real config narrows script roots to specific skill dirs (feishu-docs);
    # a sibling skill's script (e.g. feishu-people-search/search_people.py)
    # must NOT run in groups even though it exists under the same my-skills tree.
    my_skills = tmp_path / "my-skills" / "productivity"
    docs_scripts = my_skills / "feishu-docs" / "scripts"
    people_scripts = my_skills / "feishu-people-search" / "scripts"
    docs_scripts.mkdir(parents=True)
    people_scripts.mkdir(parents=True)
    (docs_scripts / "create_doc.py").write_text("print('ok')\n", encoding="utf-8")
    (people_scripts / "search_people.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_SCRIPT_ROOTS", ((my_skills / "feishu-docs").resolve(),))

    assert sandbox._terminal_allowed_for_group({"command": f"python {docs_scripts / 'create_doc.py'} --title T"})
    assert not sandbox._terminal_allowed_for_group({"command": f"python {people_scripts / 'search_people.py'} 张三"})


def test_group_terminal_allows_download_into_configured_root(tmp_path, monkeypatch):
    download_root = tmp_path / "downloads"
    download_root.mkdir()

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_DOWNLOAD_ROOTS", (download_root.resolve(),))

    assert sandbox._terminal_allowed_for_group(
        {"command": f"curl -L 'https://example.com/file?a=1&b=2' -o {download_root / 'file.txt'}"}
    )


def test_group_terminal_allows_agent_visible_hermes_download_path(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    download_root = hermes_home / "tmp" / "downloads"
    download_root.mkdir(parents=True)

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_DOWNLOAD_ROOTS", (download_root.resolve(),))

    assert sandbox._terminal_allowed_for_group(
        {"command": "curl https://example.com/file -o /root/.hermes/tmp/downloads/file.txt"}
    )


def test_read_root_check_accepts_agent_visible_cache_path(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    cache_root = hermes_home / "cache" / "documents"
    cache_root.mkdir(parents=True)

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert sandbox._path_within_roots(
        "/root/.hermes/cache/documents/file.pdf",
        (cache_root.resolve(),),
    )


def test_read_root_check_accepts_tmp_symlink_resolution():
    assert sandbox._path_within_roots(
        "/tmp/hermes-download.txt",
        (sandbox.Path("/tmp").resolve(strict=False),),
    )


def test_group_wiki_reads_require_an_explicit_configured_path(tmp_path, monkeypatch):
    wiki_root = tmp_path / ".hermes" / "wiki"
    wiki_root.mkdir(parents=True)

    monkeypatch.setattr(sandbox, "_OWNER_CHAT_IDS", frozenset({"owner"}))
    monkeypatch.setattr(sandbox, "_ALLOWED_TOOLS", frozenset())
    monkeypatch.setattr(
        sandbox,
        "_GROUP_ALLOWED_TOOLS",
        frozenset({"read_file", "search_files"}),
    )
    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_READ_ROOTS", (wiki_root.resolve(),))
    sandbox._current_platform.set("feishu")
    sandbox._current_chat_id.set("group-chat")
    sandbox._current_chat_type.set("group")

    assert (
        sandbox._on_pre_tool_call(
            tool_name="search_files",
            args={"pattern": "SpaceSight", "path": str(wiki_root)},
        )
        is None
    )
    assert (
        sandbox._on_pre_tool_call(
            tool_name="read_file",
            args={"path": str(wiki_root / "index.md")},
        )
        is None
    )

    missing_path = sandbox._on_pre_tool_call(
        tool_name="search_files",
        args={"pattern": "SpaceSight"},
    )
    wrong_path = sandbox._on_pre_tool_call(
        tool_name="search_files",
        args={"pattern": "SpaceSight", "path": str(tmp_path / "wiki")},
    )

    assert missing_path == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }
    assert wrong_path == {
        "action": "block",
        "message": sandbox._READ_ROOT_BLOCK_MESSAGE,
    }


def test_group_terminal_allows_download_into_tmp(monkeypatch):
    tmp_root = sandbox.Path("/tmp").resolve(strict=False)
    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_DOWNLOAD_ROOTS", (tmp_root,))

    assert sandbox._terminal_allowed_for_group({"command": "wget https://example.com/file -O /tmp/hermes-download.txt"})


def test_group_terminal_rejects_download_outside_configured_root(tmp_path, monkeypatch):
    download_root = tmp_path / "downloads"
    download_root.mkdir()

    monkeypatch.setattr(sandbox, "_GROUP_ALLOWED_DOWNLOAD_ROOTS", (download_root.resolve(),))

    assert not sandbox._terminal_allowed_for_group({"command": "wget https://example.com/file -O /tmp/outside.txt"})
    assert not sandbox._terminal_allowed_for_group(
        {"command": f"curl https://example.com/file -o {download_root / 'file.txt'} | cat"}
    )
    assert not sandbox._terminal_allowed_for_group(
        {"command": f"curl file:///etc/passwd -o {download_root / 'passwd.txt'}"}
    )
    assert not sandbox._terminal_allowed_for_group(
        {"command": f"curl --config /tmp/curlrc https://example.com/file -o {download_root / 'file.txt'}"}
    )
