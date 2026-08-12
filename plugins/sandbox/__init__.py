"""Per-chat capability boundary for Feishu.

The owner's main Feishu DM keeps the normal Hermes tool surface. Other
Feishu DMs get a small safe allowlist. Feishu groups additionally get:

* read-only wiki and skill access;
* a per-group data workspace under ``~/.hermes/tmp/group-workspaces``;
* exact, structured entry points to pre-installed Feishu document scripts.

Groups never receive the generic terminal or write-file tools. Trusted script
execution uses argv (never a shell) and, on macOS, ``sandbox-exec`` restricts
the whole process tree to writes inside that group's workspace.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple
from urllib.parse import urlparse

import yaml

logger = logging.getLogger(__name__)


_current_chat_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_chat_id", default=None
)
_current_platform: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_platform", default=None
)
_current_chat_type: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_chat_type", default=None
)
_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_user_id", default=None
)


_CONFIG_LOADED = False
_OWNER_CHAT_IDS: FrozenSet[str] = frozenset()
_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_READ_ROOTS: Tuple[Path, ...] = tuple()
_GROUP_WORKSPACE_ROOT: Optional[Path] = None
_GROUP_ALLOWED_SCRIPT_ACTIONS: FrozenSet[str] = frozenset()
_FEISHU_DOC_SCRIPTS_ROOT: Optional[Path] = None
_PYTHON_EXECUTABLE: Optional[Path] = None
_SCRIPT_TIMEOUT_SECONDS = 300
_GROUP_MAX_DOWNLOAD_BYTES = 50_000_000
_REQUIRE_PROCESS_SANDBOX = True

_BLOCK_MESSAGE = "This tool is not available in this chat."
_READ_ROOT_BLOCK_MESSAGE = "群聊只允许读取 wiki 和当前群自己的临时工作区。"
_CONFIG_BLOCK_MESSAGE = "群聊安全配置未成功加载，工具调用已按设计拒绝。"
_GROUP_CONTEXT_MESSAGE = "This tool is available only inside a configured Feishu group chat."

_READ_PATH_TOOLS: FrozenSet[str] = frozenset({"read_file", "search_files"})
_GROUP_CHAT_TYPES: FrozenSet[str] = frozenset({"group", "channel", "forum", "thread"})
_WORKSPACE_TOOL = "group_cache"
_SCRIPT_TOOL = "feishu_doc_manage"
_MAX_FILE_CONTENT_BYTES = 1_000_000
_MAX_TOOL_OUTPUT_CHARS = 100_000
_DOC_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{5,200}$")
_BEARER_OUTPUT_RE = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+")
_SECRET_OUTPUT_RE = re.compile(
    r"""(?ix)
    (\b(?:FEISHU_APP_ID|FEISHU_APP_SECRET|tenant_access_token)\b
    ["']?\s*[:=]\s*["']?)
    [^\s,"']+
    """
)
_FEISHU_SCRIPT_FILES = {
    "create": "create_new_doc_from_md.py",
    "append": "append_md_to_doc.py",
    "rebuild": "rebuild_doc_from_md.py",
    "delete": "delete_doc.py",
    "read_url": "read_feishu_url.py",
    "download_file": "download_feishu_file.py",
}


GROUP_CACHE_SCHEMA = {
    "name": _WORKSPACE_TOOL,
    "description": (
        "Manage data files in this Feishu group's isolated temporary workspace. "
        "Paths must be relative. Files here are data only and cannot be executed."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "write", "append", "mkdir", "move", "delete"],
            },
            "path": {"type": "string", "description": "Relative path inside this group's workspace."},
            "destination": {"type": "string", "description": "Relative destination for move."},
            "content": {"type": "string", "description": "UTF-8 text for write or append."},
            "recursive": {"type": "boolean", "default": False},
            "overwrite": {"type": "boolean", "default": False},
        },
        "required": ["action"],
    },
}


FEISHU_DOC_MANAGE_SCHEMA = {
    "name": _SCRIPT_TOOL,
    "description": (
        "Run an operator-approved, pre-installed Feishu document script without a shell. "
        "Supports create, append, rebuild, delete, URL read, and file download. "
        "For create/append/rebuild, provide content or a markdown_path previously written by group_cache."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "append", "rebuild", "delete", "read_url", "download_file"],
            },
            "doc_token": {"type": "string", "description": "Feishu docx token or docx URL."},
            "title": {"type": "string"},
            "content": {"type": "string", "description": "Markdown content."},
            "markdown_path": {
                "type": "string",
                "description": "Relative markdown file path in this group's workspace.",
            },
            "url": {"type": "string", "description": "Feishu/Lark URL or file token."},
        },
        "required": ["action"],
    },
}


def _json_result(**values: Any) -> str:
    return json.dumps(values, ensure_ascii=False)


def _redact_tool_output(value: str) -> str:
    text = _BEARER_OUTPUT_RE.sub(r"\1[REDACTED]", value)
    return _SECRET_OUTPUT_RE.sub(r"\1[REDACTED]", text)


def _coerce_chat_ids(raw: Any) -> Set[str]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw.strip()} if raw.strip() else set()
    if isinstance(raw, (list, tuple, set)):
        return {str(item).strip() for item in raw if isinstance(item, str) and item.strip()}
    return set()


def _coerce_paths(raw: Any) -> Tuple[Path, ...]:
    if raw is None:
        return tuple()
    values = [raw] if isinstance(raw, str) else raw
    if not isinstance(values, (list, tuple, set)):
        return tuple()
    roots = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            continue
        roots.append(_expand_path(item))
    return tuple(roots)


def _expand_path(value: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve(strict=False)


def _resolve_tool_path(path_text: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(path_text or "").strip()))
    if expanded == "/root/.hermes" or expanded.startswith("/root/.hermes/"):
        hermes_home = _expand_path(os.getenv("HERMES_HOME", "~/.hermes"))
        suffix = expanded.removeprefix("/root/.hermes").lstrip("/")
        return (hermes_home / suffix).resolve(strict=False)
    return _expand_path(expanded)


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _tool_read_path(tool_name: str, args: Any) -> str:
    if not isinstance(args, dict) or tool_name not in _READ_PATH_TOOLS:
        return ""
    value = args.get("path")
    return value if isinstance(value, str) else ""


def _is_group_context() -> bool:
    return (
        _current_platform.get() == "feishu"
        and _current_chat_type.get() in _GROUP_CHAT_TYPES
        and bool(_current_chat_id.get())
    )


def _require_group_context() -> str:
    if not _CONFIG_LOADED or not _is_group_context():
        raise PermissionError(_GROUP_CONTEXT_MESSAGE)
    return str(_current_chat_id.get())


def _workspace_for_chat(chat_id: str, *, create: bool = True) -> Path:
    if _GROUP_WORKSPACE_ROOT is None:
        raise RuntimeError("group workspace root is not configured")
    root = _GROUP_WORKSPACE_ROOT.resolve(strict=False)
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    digest = hashlib.sha256(chat_id.encode("utf-8")).hexdigest()[:24]
    workspace = (root / digest).resolve(strict=False)
    if not _path_within(workspace, root):
        raise RuntimeError("invalid group workspace")
    if create:
        workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    return workspace


def _workspace_id(chat_id: str) -> str:
    return hashlib.sha256(chat_id.encode("utf-8")).hexdigest()[:24]


def _relative_workspace_path(path: Path, workspace: Path) -> str:
    if path == workspace:
        return "."
    return str(path.relative_to(workspace))


def _workspace_path(workspace: Path, relative: Any, *, allow_root: bool = False) -> Path:
    text = str(relative or "").strip()
    if not text:
        if allow_root:
            return workspace
        raise ValueError("path is required")
    if "\x00" in text:
        raise ValueError("path contains a NUL byte")
    raw = Path(text)
    if raw.is_absolute() or text.startswith("~") or any(part == ".." for part in raw.parts):
        raise ValueError("path must be relative and cannot contain '..'")
    lexical = workspace / raw
    resolved = lexical.resolve(strict=False)
    if not _path_within(resolved, workspace):
        raise ValueError("path escapes the group workspace")
    if lexical.is_symlink():
        raise ValueError("symbolic links are not supported in the group workspace")
    if resolved == workspace and not allow_root:
        raise ValueError("operation on the workspace root is not allowed")
    return resolved


def _read_path_allowed_for_group(path_text: str, chat_id: str) -> bool:
    if not path_text:
        return False
    resolved = _resolve_tool_path(path_text)
    if _GROUP_WORKSPACE_ROOT and _path_within(resolved, _GROUP_WORKSPACE_ROOT):
        return _path_within(resolved, _workspace_for_chat(chat_id))
    return any(_path_within(resolved, root) for root in _GROUP_ALLOWED_READ_ROOTS)


def _list_workspace(target: Path, workspace: Path, recursive: bool) -> list[dict[str, Any]]:
    if not target.exists():
        raise FileNotFoundError(str(target))
    paths: list[Path]
    if target.is_dir():
        paths = list(target.rglob("*")) if recursive else list(target.iterdir())
    else:
        paths = [target]
    result = []
    for path in sorted(paths, key=lambda item: str(item))[:500]:
        if path.is_symlink():
            kind, size = "symlink", None
        elif path.is_dir():
            kind, size = "directory", None
        elif path.is_file():
            kind, size = "file", path.stat().st_size
        else:
            kind, size = "other", None
        result.append({"path": str(path.relative_to(workspace)), "type": kind, "size": size})
    return result


def _handle_group_cache(args: Dict[str, Any], **_kwargs: Any) -> str:
    chat_id = _require_group_context()
    workspace = _workspace_for_chat(chat_id)
    action = str(args.get("action") or "").strip()
    path = _workspace_path(workspace, args.get("path"), allow_root=action == "list")

    if action == "list":
        return _json_result(
            success=True,
            workspace_id=_workspace_id(chat_id),
            entries=_list_workspace(path, workspace, bool(args.get("recursive"))),
        )

    if action == "read":
        if not path.is_file():
            raise ValueError("path is not a file")
        if path.stat().st_size > _MAX_FILE_CONTENT_BYTES:
            raise ValueError("file exceeds the 1 MB group workspace limit")
        return _json_result(
            success=True,
            path=_relative_workspace_path(path, workspace),
            content=path.read_text(encoding="utf-8"),
        )

    if action in {"write", "append"}:
        content = args.get("content")
        if not isinstance(content, str):
            raise ValueError("content is required")
        if len(content.encode("utf-8")) > _MAX_FILE_CONTENT_BYTES:
            raise ValueError("content exceeds the 1 MB group workspace limit")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if action == "write":
            if path.exists() and not bool(args.get("overwrite")):
                raise FileExistsError("path exists; set overwrite=true to replace it")
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
                handle.write(content)
                staged = Path(handle.name)
            try:
                os.replace(staged, path)
            finally:
                if staged.exists():
                    staged.unlink()
        else:
            if path.exists() and not path.is_file():
                raise ValueError("path is not a file")
            current_size = path.stat().st_size if path.exists() else 0
            if current_size + len(content.encode("utf-8")) > _MAX_FILE_CONTENT_BYTES:
                raise ValueError("append would exceed the 1 MB group workspace limit")
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        return _json_result(
            success=True,
            path=_relative_workspace_path(path, workspace),
            size=path.stat().st_size,
        )

    if action == "mkdir":
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return _json_result(success=True, path=_relative_workspace_path(path, workspace))

    if action == "move":
        if not path.exists():
            raise FileNotFoundError(str(path))
        destination = _workspace_path(workspace, args.get("destination"))
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.exists() and not bool(args.get("overwrite")):
            raise FileExistsError("destination exists; set overwrite=true to replace it")
        os.replace(path, destination)
        return _json_result(
            success=True,
            source=_relative_workspace_path(path, workspace),
            destination=_relative_workspace_path(destination, workspace),
        )

    if action == "delete":
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path.is_dir():
            if not bool(args.get("recursive")):
                path.rmdir()
            else:
                shutil.rmtree(path)
        else:
            path.unlink()
        return _json_result(success=True, deleted=_relative_workspace_path(path, workspace))

    raise ValueError(f"unsupported action: {action!r}")


def _doc_token(value: Any) -> str:
    text = str(value or "").strip()
    if "/docx/" in text or "/docs/" in text:
        marker = "/docx/" if "/docx/" in text else "/docs/"
        text = text.split(marker, 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")
    if not _DOC_TOKEN_RE.fullmatch(text):
        raise ValueError("invalid Feishu document token")
    return text


def _feishu_url(value: Any, *, file_only: bool = False) -> str:
    text = str(value or "").strip()
    if _DOC_TOKEN_RE.fullmatch(text) and file_only:
        return text
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host.endswith(".feishu.cn") or host.endswith(".larksuite.com")):
        raise ValueError("only HTTPS Feishu/Lark URLs are allowed")
    if file_only and "/file/" not in parsed.path:
        raise ValueError("download_file requires a Feishu /file/ URL or file token")
    return text


def _markdown_source(args: Dict[str, Any], workspace: Path) -> Path:
    content = args.get("content")
    relative = args.get("markdown_path")
    if (content is None) == (relative is None):
        raise ValueError("provide exactly one of content or markdown_path")
    if content is not None:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be non-empty markdown")
        if len(content.encode("utf-8")) > _MAX_FILE_CONTENT_BYTES:
            raise ValueError("content exceeds the 1 MB group workspace limit")
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".md", prefix="feishu_", dir=workspace, delete=False
        ) as handle:
            handle.write(content.rstrip() + "\n")
            return Path(handle.name)
    source = _workspace_path(workspace, relative)
    if source.suffix.lower() != ".md" or not source.is_file():
        raise ValueError("markdown_path must name an existing .md file in this group's workspace")
    return source


def _trusted_script_path(action: str) -> Path:
    if action not in _GROUP_ALLOWED_SCRIPT_ACTIONS:
        raise PermissionError(f"script action is not operator-approved: {action}")
    filename = _FEISHU_SCRIPT_FILES.get(action)
    if not filename or _FEISHU_DOC_SCRIPTS_ROOT is None:
        raise ValueError(f"unsupported script action: {action!r}")
    path = (_FEISHU_DOC_SCRIPTS_ROOT / filename).resolve(strict=False)
    if path.parent != _FEISHU_DOC_SCRIPTS_ROOT or not path.is_file():
        raise RuntimeError(f"approved script is missing: {filename}")
    return path


def _build_script_argv(args: Dict[str, Any], workspace: Path) -> tuple[str, Path, list[str]]:
    action = str(args.get("action") or "").strip()
    script = _trusted_script_path(action)

    if action == "create":
        title = str(args.get("title") or "").strip()
        if not title or len(title) > 300:
            raise ValueError("create requires a title of at most 300 characters")
        argv = [str(_markdown_source(args, workspace)), title]
    elif action == "append":
        argv = [_doc_token(args.get("doc_token")), str(_markdown_source(args, workspace))]
    elif action == "rebuild":
        argv = [_doc_token(args.get("doc_token")), str(_markdown_source(args, workspace))]
        title = str(args.get("title") or "").strip()
        if title:
            if len(title) > 300:
                raise ValueError("title exceeds 300 characters")
            argv.append(title)
    elif action == "delete":
        argv = [_doc_token(args.get("doc_token"))]
    elif action == "read_url":
        argv = [_feishu_url(args.get("url"))]
    elif action == "download_file":
        argv = [_feishu_url(args.get("url"), file_only=True), str(workspace)]
    else:
        raise ValueError(f"unsupported script action: {action!r}")
    return action, script, argv


def _seatbelt_quote(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("\\", "\\\\").replace('"', '\\"')


def _seatbelt_profile(workspace: Path) -> str:
    quoted = _seatbelt_quote(workspace)
    return (
        "(version 1)\n"
        "(allow default)\n"
        f'(deny file-write* (require-not (subpath "{quoted}")))\n'
        f'(deny process-exec (subpath "{quoted}"))\n'
    )


def _run_trusted_script(script: Path, argv: list[str], workspace: Path) -> subprocess.CompletedProcess[str]:
    if _PYTHON_EXECUTABLE is None or not _PYTHON_EXECUTABLE.is_file():
        raise RuntimeError("configured Python interpreter is missing")
    command = [str(_PYTHON_EXECUTABLE), str(script), *argv]
    if _REQUIRE_PROCESS_SANDBOX:
        sandbox_exec = Path("/usr/bin/sandbox-exec")
        if not sandbox_exec.is_file():
            raise RuntimeError("required process sandbox is unavailable; refusing to run the script")
        command = [str(sandbox_exec), "-p", _seatbelt_profile(workspace), *command]

    env = os.environ.copy()
    env.update(
        {
            "HERMES_GROUP_WORKSPACE": str(workspace),
            "HERMES_FEISHU_BACKUP_DIR": str(workspace / "feishu-backups"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": str(workspace),
            "HERMES_GROUP_MAX_DOWNLOAD_BYTES": str(_GROUP_MAX_DOWNLOAD_BYTES),
        }
    )
    return subprocess.run(
        command,
        cwd=str(script.parent),
        env=env,
        text=True,
        capture_output=True,
        timeout=_SCRIPT_TIMEOUT_SECONDS,
        check=False,
    )


def _handle_feishu_doc_manage(args: Dict[str, Any], **_kwargs: Any) -> str:
    chat_id = _require_group_context()
    workspace = _workspace_for_chat(chat_id)
    action, script, argv = _build_script_argv(args, workspace)
    actor = str(_current_user_id.get() or "unknown")
    logger.info(
        "sandbox: trusted script start action=%s script=%s python=%s chat=%s actor=%s",
        action,
        script.name,
        _PYTHON_EXECUTABLE,
        chat_id,
        actor,
    )
    result = _run_trusted_script(script, argv, workspace)
    logger.info(
        "sandbox: trusted script end action=%s script=%s python=%s chat=%s actor=%s returncode=%s",
        action,
        script.name,
        _PYTHON_EXECUTABLE,
        chat_id,
        actor,
        result.returncode,
    )
    stdout = _redact_tool_output(result.stdout[-_MAX_TOOL_OUTPUT_CHARS:])
    stderr = _redact_tool_output(result.stderr[-_MAX_TOOL_OUTPUT_CHARS:])
    return _json_result(
        success=result.returncode == 0,
        action=action,
        script=script.name,
        returncode=result.returncode,
        stdout=stdout,
        stderr=stderr,
        workspace_id=_workspace_id(chat_id),
    )


def _group_tools_available() -> bool:
    return bool(
        _CONFIG_LOADED
        and _GROUP_WORKSPACE_ROOT
        and _FEISHU_DOC_SCRIPTS_ROOT
        and _PYTHON_EXECUTABLE
        and (not _REQUIRE_PROCESS_SANDBOX or Path("/usr/bin/sandbox-exec").is_file())
    )


def _load_config() -> bool:
    global _CONFIG_LOADED, _OWNER_CHAT_IDS, _ALLOWED_TOOLS, _GROUP_ALLOWED_TOOLS
    global _GROUP_ALLOWED_READ_ROOTS, _GROUP_WORKSPACE_ROOT, _GROUP_ALLOWED_SCRIPT_ACTIONS
    global _FEISHU_DOC_SCRIPTS_ROOT, _PYTHON_EXECUTABLE, _SCRIPT_TIMEOUT_SECONDS
    global _GROUP_MAX_DOWNLOAD_BYTES
    global _REQUIRE_PROCESS_SANDBOX, _BLOCK_MESSAGE, _READ_ROOT_BLOCK_MESSAGE

    _CONFIG_LOADED = False
    cfg_path = Path(__file__).parent / "config.yaml"
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.error("sandbox: failed to load %s: %s", cfg_path, exc)
        return False

    owners = _coerce_chat_ids(data.get("owner_feishu_chat_ids"))
    owners |= _coerce_chat_ids(data.get("owner_feishu_chat_id"))
    if not owners:
        logger.error("sandbox: owner_feishu_chat_ids is empty; Feishu calls will fail closed")
        return False

    allowed = data.get("allowed_tools_for_outsiders")
    group_allowed = data.get("allowed_tools_for_outsider_groups")
    script_actions = data.get("allowed_feishu_script_actions_for_outsider_groups")
    if not isinstance(allowed, list) or not isinstance(group_allowed, list) or not isinstance(script_actions, list):
        logger.error("sandbox: tool and script allowlists must be YAML lists")
        return False

    workspace_value = data.get("group_workspace_root")
    scripts_value = data.get("feishu_doc_scripts_root")
    python_value = data.get("python_executable")
    if not all(isinstance(value, str) and value.strip() for value in (workspace_value, scripts_value, python_value)):
        logger.error("sandbox: workspace, scripts root, and Python executable must be configured")
        return False

    actions = frozenset(str(item) for item in script_actions)
    if not actions or not actions.issubset(_FEISHU_SCRIPT_FILES):
        logger.error("sandbox: invalid or empty Feishu script action allowlist: %s", sorted(actions))
        return False

    _OWNER_CHAT_IDS = frozenset(owners)
    _ALLOWED_TOOLS = frozenset(str(item) for item in allowed)
    _GROUP_ALLOWED_TOOLS = frozenset(str(item) for item in group_allowed)
    _GROUP_ALLOWED_READ_ROOTS = _coerce_paths(data.get("allowed_read_roots_for_outsider_groups"))
    _GROUP_WORKSPACE_ROOT = _expand_path(workspace_value)
    _GROUP_ALLOWED_SCRIPT_ACTIONS = actions
    _FEISHU_DOC_SCRIPTS_ROOT = _expand_path(scripts_value)
    _PYTHON_EXECUTABLE = _expand_path(python_value)
    _REQUIRE_PROCESS_SANDBOX = bool(data.get("require_process_sandbox", True))
    try:
        _SCRIPT_TIMEOUT_SECONDS = max(1, min(900, int(data.get("script_timeout_seconds", 300))))
        _GROUP_MAX_DOWNLOAD_BYTES = max(
            1_000_000,
            min(500_000_000, int(data.get("group_max_download_bytes", 50_000_000))),
        )
    except (TypeError, ValueError):
        logger.error("sandbox: script timeout and download limit must be integers")
        return False

    if _REQUIRE_PROCESS_SANDBOX and not Path("/usr/bin/sandbox-exec").is_file():
        logger.error("sandbox: required /usr/bin/sandbox-exec is unavailable")
        return False
    if not _FEISHU_DOC_SCRIPTS_ROOT.is_dir() or not _PYTHON_EXECUTABLE.is_file():
        logger.error("sandbox: trusted script root or Python interpreter is missing")
        return False
    for action in actions:
        if not (_FEISHU_DOC_SCRIPTS_ROOT / _FEISHU_SCRIPT_FILES[action]).is_file():
            logger.error("sandbox: configured script action %s is missing its script", action)
            return False

    message = data.get("block_message")
    read_message = data.get("read_root_block_message")
    if isinstance(message, str) and message.strip():
        _BLOCK_MESSAGE = message
    if isinstance(read_message, str) and read_message.strip():
        _READ_ROOT_BLOCK_MESSAGE = read_message

    _CONFIG_LOADED = True
    return True


def _on_pre_gateway_dispatch(event: Any = None, **_kwargs: Any) -> Optional[Dict[str, Any]]:
    if event is None or getattr(event, "source", None) is None:
        return None
    source = event.source
    platform = getattr(source, "platform", None)
    _current_platform.set(platform.value if platform else None)
    _current_chat_id.set(getattr(source, "chat_id", None))
    _current_chat_type.set(str(getattr(source, "chat_type", "") or "").lower() or None)
    _current_user_id.set(getattr(source, "user_id", None))
    return None


def _on_pre_tool_call(tool_name: str = "", args: Any = None, **_kwargs: Any) -> Optional[Dict[str, Any]]:
    if _current_platform.get() != "feishu":
        return None
    if not _CONFIG_LOADED:
        return {"action": "block", "message": _CONFIG_BLOCK_MESSAGE}

    chat_id = str(_current_chat_id.get() or "")
    if chat_id in _OWNER_CHAT_IDS:
        return None
    if tool_name in _ALLOWED_TOOLS:
        return None

    chat_type = _current_chat_type.get()
    if chat_type in _GROUP_CHAT_TYPES and tool_name in _GROUP_ALLOWED_TOOLS:
        if tool_name in _READ_PATH_TOOLS:
            path_text = _tool_read_path(tool_name, args)
            if not _read_path_allowed_for_group(path_text, chat_id):
                logger.info("sandbox: blocked group read tool=%s path=%s chat=%s", tool_name, path_text, chat_id)
                return {"action": "block", "message": _READ_ROOT_BLOCK_MESSAGE}
        return None

    logger.info("sandbox: blocked tool=%s chat=%s chat_type=%s", tool_name, chat_id, chat_type)
    return {"action": "block", "message": _BLOCK_MESSAGE}


def register(ctx: Any) -> None:
    loaded = _load_config()
    ctx.register_tool(
        name=_WORKSPACE_TOOL,
        toolset="sandbox_group",
        schema=GROUP_CACHE_SCHEMA,
        handler=_handle_group_cache,
        check_fn=_group_tools_available,
        description="Manage this Feishu group's isolated temporary data workspace.",
    )
    ctx.register_tool(
        name=_SCRIPT_TOOL,
        toolset="sandbox_group",
        schema=FEISHU_DOC_MANAGE_SCHEMA,
        handler=_handle_feishu_doc_manage,
        check_fn=_group_tools_available,
        description="Run exact operator-approved Feishu document scripts under a process sandbox.",
    )
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.info(
        "sandbox: registered (pid=%s, active=%s, owner_chats=%s, group_allowed=%s, read_roots=%s, "
        "workspace_root=%s, script_actions=%s, process_sandbox=%s)",
        os.getpid(),
        loaded,
        sorted(_OWNER_CHAT_IDS),
        sorted(_GROUP_ALLOWED_TOOLS),
        [str(path) for path in _GROUP_ALLOWED_READ_ROOTS],
        _GROUP_WORKSPACE_ROOT,
        sorted(_GROUP_ALLOWED_SCRIPT_ACTIONS),
        _REQUIRE_PROCESS_SANDBOX,
    )
