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
