"""sandbox plugin — per-chat tool restriction for Feishu.

Owner's main Feishu DM gets the full toolset. Every other Feishu chat
(group chats, DMs with other people) is restricted to a small allowlist
of safe tools. Non-Feishu sources (CLI/TUI, cron-triggered sessions,
internal events) are never gated.

Mechanism:
  - pre_gateway_dispatch  fires once per inbound message; stashes the
    source platform + chat_id + chat_type in ContextVars. ContextVars propagate
    through asyncio create_task / await boundaries, so the same values
    are visible from every downstream tool call spawned for that
    message. Concurrent dispatches each carry their own context.

  - pre_tool_call  reads the ContextVars. If platform != "feishu" OR
    chat_id matches the owner's DM, the call is allowed. Otherwise only
    tools in the configured allowlist pass. Group/channel chats may also
    call the configured group-only allowlist; read_file/search_files are
    additionally constrained to configured read roots. Anything else is
    blocked with the configured user-visible message.
"""

from __future__ import annotations

import contextvars
import logging
import os
import shlex
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Sequence, Set, Tuple

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


_OWNER_CHAT_IDS: FrozenSet[str] = frozenset()
_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_READ_ROOTS: Tuple[Path, ...] = tuple()
_GROUP_ALLOWED_SCRIPT_ROOTS: Tuple[Path, ...] = tuple()
_GROUP_ALLOWED_DOWNLOAD_ROOTS: Tuple[Path, ...] = tuple()
_BLOCK_MESSAGE: str = "This tool is not available in this chat."
_READ_ROOT_BLOCK_MESSAGE: str = "群聊只允许读取配置的只读知识库目录。"
_TERMINAL_BLOCK_MESSAGE: str = "群聊只允许用 terminal 执行下载命令或运行配置目录下已有脚本。"
_READ_PATH_TOOLS: FrozenSet[str] = frozenset({"read_file", "search_files"})
_DOWNLOAD_COMMANDS: FrozenSet[str] = frozenset({"curl", "wget"})
_PYTHON_COMMANDS: FrozenSet[str] = frozenset({"python", "python3"})
_SHELL_CONTROL_TOKENS: FrozenSet[str] = frozenset({";", "|", "||", "&", "&&", "<", "<<", ">", ">>", "2>", "2>>"})
_CURL_SAFE_FLAGS: FrozenSet[str] = frozenset(
    {"-L", "--location", "-s", "--silent", "-S", "--show-error", "-f", "--fail"}
)
_WGET_SAFE_FLAGS: FrozenSet[str] = frozenset({"-q", "--quiet", "-nv", "--no-verbose"})


def _coerce_chat_ids(raw: Any) -> Set[str]:
    """Accept either a single string or a list of strings; ignore empty entries."""
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw.strip()} if raw.strip() else set()
    if isinstance(raw, (list, tuple, set)):
        out: Set[str] = set()
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.add(item.strip())
        return out
    return set()


def _coerce_paths(raw: Any) -> Tuple[Path, ...]:
    """Accept a path string or list of path strings, resolving env vars and ~."""
    if raw is None:
        return tuple()
    values = [raw] if isinstance(raw, str) else raw
    if not isinstance(values, (list, tuple, set)):
        return tuple()

    roots = []
    for item in values:
        if not isinstance(item, str) or not item.strip():
            continue
        expanded = os.path.expandvars(os.path.expanduser(item.strip()))
        path = Path(expanded)
        if not path.is_absolute():
            path = Path.cwd() / path
        roots.append(path.resolve(strict=False))
    return tuple(roots)


def _tool_read_path(tool_name: str, args: Any) -> str:
    """Return the filesystem path argument used by read-only file tools."""
    if not isinstance(args, dict):
        return ""
    if tool_name == "read_file":
        value = args.get("path")
    elif tool_name == "search_files":
        value = args.get("path")
    else:
        value = None
    return value if isinstance(value, str) else ""


def _path_within_roots(path_text: str, roots: Tuple[Path, ...]) -> bool:
    if not path_text or not roots:
        return False
    resolved = _resolve_tool_path(path_text)
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _resolve_tool_path(path_text: str, *, workdir: str = "") -> Path:
    expanded = os.path.expandvars(os.path.expanduser(str(path_text or "").strip()))
    if expanded == "/root/.hermes" or expanded.startswith("/root/.hermes/"):
        hermes_home = Path(os.path.expandvars(os.path.expanduser(os.getenv("HERMES_HOME", "~/.hermes"))))
        suffix = expanded.removeprefix("/root/.hermes").lstrip("/")
        return (hermes_home / suffix).resolve(strict=False)
    candidate = Path(expanded)
    if not candidate.is_absolute():
        base = Path(os.path.expandvars(os.path.expanduser(workdir.strip()))) if workdir else Path.cwd()
        candidate = base / candidate
    return candidate.resolve(strict=False)


def _is_existing_file_within_roots(path_text: str, roots: Tuple[Path, ...], *, workdir: str = "") -> bool:
    if not path_text or not roots:
        return False
    resolved = _resolve_tool_path(path_text, workdir=workdir)
    if not resolved.is_file():
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _first_non_option(tokens: Sequence[str], start: int = 1) -> str:
    skip_next = False
    for token in tokens[start:]:
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            continue
        if token.startswith("-"):
            # Common python options that consume an argument; keep this narrow.
            if token in {"-m", "-c", "-W", "-X"}:
                skip_next = True
            continue
        return token
    return ""


def _terminal_command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _has_shell_control_tokens(command: str) -> bool:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return True
    return any(token in _SHELL_CONTROL_TOKENS or "`" in token for token in tokens)


def _looks_like_existing_script_command(args: Any) -> bool:
    if not isinstance(args, dict):
        return False
    command = str(args.get("command", "") or "").strip()
    if not command:
        return False
    if _has_shell_control_tokens(command):
        return False
    tokens = _terminal_command_tokens(command)
    if not tokens:
        return False
    executable = Path(tokens[0]).name
    if executable not in _PYTHON_COMMANDS:
        return False
    script = _first_non_option(tokens)
    if not script or script in {"-c", "-m"}:
        return False
    if not Path(script).suffix == ".py":
        return False
    return _is_existing_file_within_roots(
        script,
        _GROUP_ALLOWED_SCRIPT_ROOTS,
        workdir=str(args.get("workdir", "") or ""),
    )


def _download_destination(tokens: Sequence[str]) -> str:
    command = Path(tokens[0]).name if tokens else ""
    if command == "curl":
        for i, token in enumerate(tokens[1:], start=1):
            if token in {"-o", "--output", "--output-document"} and i + 1 < len(tokens):
                return tokens[i + 1]
        return ""
    if command == "wget":
        for i, token in enumerate(tokens[1:], start=1):
            if token in {"-O", "--output-document"} and i + 1 < len(tokens):
                return tokens[i + 1]
            if token.startswith("--output-document="):
                return token.split("=", 1)[1]
        return ""
    return ""


def _download_sources_are_http(tokens: Sequence[str]) -> bool:
    if not tokens:
        return False
    command = Path(tokens[0]).name
    sources: list[str] = []
    i = 1
    while i < len(tokens):
        token = tokens[i]
        if command == "curl":
            if token in {"-o", "--output", "--output-document"}:
                i += 2
                continue
            if token in _CURL_SAFE_FLAGS:
                i += 1
                continue
            if token.startswith("-"):
                return False
            sources.append(token)
            i += 1
            continue
        if command == "wget":
            if token in {"-O", "--output-document"}:
                i += 2
                continue
            if token.startswith("--output-document="):
                i += 1
                continue
            if token in _WGET_SAFE_FLAGS:
                i += 1
                continue
            if token.startswith("-"):
                return False
            sources.append(token)
            i += 1
            continue
        return False
    return bool(sources) and all(src.startswith(("http://", "https://")) for src in sources)


def _looks_like_download_command(args: Any) -> bool:
    if not isinstance(args, dict):
        return False
    command = str(args.get("command", "") or "").strip()
    if not command:
        return False
    if _has_shell_control_tokens(command):
        return False
    tokens = _terminal_command_tokens(command)
    if not tokens or Path(tokens[0]).name not in _DOWNLOAD_COMMANDS:
        return False
    if not _download_sources_are_http(tokens):
        return False
    destination = _download_destination(tokens)
    if not destination:
        return False
    return _path_within_roots(
        str(_resolve_tool_path(destination, workdir=str(args.get("workdir", "") or ""))),
        _GROUP_ALLOWED_DOWNLOAD_ROOTS,
    )


def _terminal_allowed_for_group(args: Any) -> bool:
    return _looks_like_download_command(args) or _looks_like_existing_script_command(args)


def _load_config() -> bool:
    """Load config.yaml next to this file. Returns True iff at least one owner is set."""
    global _OWNER_CHAT_IDS, _ALLOWED_TOOLS, _GROUP_ALLOWED_TOOLS, _GROUP_ALLOWED_READ_ROOTS
    global \
        _GROUP_ALLOWED_SCRIPT_ROOTS, \
        _GROUP_ALLOWED_DOWNLOAD_ROOTS, \
        _BLOCK_MESSAGE, \
        _READ_ROOT_BLOCK_MESSAGE, \
        _TERMINAL_BLOCK_MESSAGE
    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        logger.warning("sandbox: %s missing — plugin will stay inactive", cfg_path)
        return False
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.error("sandbox: failed to parse %s: %s — plugin will stay inactive", cfg_path, e)
        return False

    owners = _coerce_chat_ids(data.get("owner_feishu_chat_ids"))
    # Backward-compat: accept legacy singular key too.
    owners |= _coerce_chat_ids(data.get("owner_feishu_chat_id"))
    if not owners:
        logger.warning("sandbox: no owner_feishu_chat_ids set — plugin will stay inactive")
        return False
    _OWNER_CHAT_IDS = frozenset(owners)

    allowed = data.get("allowed_tools_for_outsiders") or []
    if not isinstance(allowed, list):
        logger.warning("sandbox: allowed_tools_for_outsiders not a list — using default")
        allowed = ["web_search", "web_extract", "vision_analyze", "image_generate"]
    _ALLOWED_TOOLS = frozenset(str(x) for x in allowed)

    group_allowed = data.get("allowed_tools_for_outsider_groups") or []
    if not isinstance(group_allowed, list):
        logger.warning("sandbox: allowed_tools_for_outsider_groups not a list — using empty default")
        group_allowed = []
    _GROUP_ALLOWED_TOOLS = frozenset(str(x) for x in group_allowed)

    _GROUP_ALLOWED_READ_ROOTS = _coerce_paths(data.get("allowed_read_roots_for_outsider_groups"))
    _GROUP_ALLOWED_SCRIPT_ROOTS = _coerce_paths(data.get("allowed_script_roots_for_outsider_groups"))
    _GROUP_ALLOWED_DOWNLOAD_ROOTS = _coerce_paths(
        data.get("allowed_download_roots_for_outsider_groups") or data.get("allowed_read_roots_for_outsider_groups")
    )

    msg = data.get("block_message")
    if isinstance(msg, str) and msg.strip():
        _BLOCK_MESSAGE = msg
    read_msg = data.get("read_root_block_message")
    if isinstance(read_msg, str) and read_msg.strip():
        _READ_ROOT_BLOCK_MESSAGE = read_msg
    terminal_msg = data.get("terminal_block_message")
    if isinstance(terminal_msg, str) and terminal_msg.strip():
        _TERMINAL_BLOCK_MESSAGE = terminal_msg

    return True


def _on_pre_gateway_dispatch(
    event: Any = None,
    gateway: Any = None,
    session_store: Any = None,
    **kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """Tag the current asyncio context with the message's platform + chat_id."""
    if event is None or getattr(event, "source", None) is None:
        return None
    src = event.source
    plat = src.platform.value if getattr(src, "platform", None) else None
    _current_platform.set(plat)
    _current_chat_id.set(getattr(src, "chat_id", None))
    _current_chat_type.set(str(getattr(src, "chat_type", "") or "").lower() or None)
    return None  # never alter dispatch flow


def _on_pre_tool_call(
    tool_name: str = "",
    args: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """Block restricted tools for non-owner Feishu chats."""
    if not _OWNER_CHAT_IDS:
        return None  # plugin not configured — fail open, with a warning logged at load time

    platform = _current_platform.get()
    if platform != "feishu":
        # Cron, TUI/CLI, internal events — never gated.
        return None

    chat_id = _current_chat_id.get()
    if chat_id in _OWNER_CHAT_IDS:
        return None  # privileged chat — full access

    if tool_name in _ALLOWED_TOOLS:
        return None

    chat_type = _current_chat_type.get()
    if chat_type in {"group", "channel", "forum", "thread"} and tool_name in _GROUP_ALLOWED_TOOLS:
        if tool_name in _READ_PATH_TOOLS:
            path_text = _tool_read_path(tool_name, args)
            if not _path_within_roots(path_text, _GROUP_ALLOWED_READ_ROOTS):
                logger.info(
                    "sandbox: blocked tool=%s path=%s chat=%s chat_type=%s read_roots=%s",
                    tool_name,
                    path_text,
                    chat_id,
                    chat_type,
                    [str(p) for p in _GROUP_ALLOWED_READ_ROOTS],
                )
                return {"action": "block", "message": _READ_ROOT_BLOCK_MESSAGE}
        if tool_name == "terminal" and not _terminal_allowed_for_group(args):
            logger.info(
                "sandbox: blocked terminal args=%s chat=%s chat_type=%s script_roots=%s download_roots=%s",
                args,
                chat_id,
                chat_type,
                [str(p) for p in _GROUP_ALLOWED_SCRIPT_ROOTS],
                [str(p) for p in _GROUP_ALLOWED_DOWNLOAD_ROOTS],
            )
            return {"action": "block", "message": _TERMINAL_BLOCK_MESSAGE}
        return None

    logger.info(
        "sandbox: blocked tool=%s chat=%s chat_type=%s (allowed=%s group_allowed=%s read_roots=%s)",
        tool_name,
        chat_id,
        chat_type,
        sorted(_ALLOWED_TOOLS),
        sorted(_GROUP_ALLOWED_TOOLS),
        [str(p) for p in _GROUP_ALLOWED_READ_ROOTS],
    )
    return {"action": "block", "message": _BLOCK_MESSAGE}


def register(ctx: Any) -> None:
    loaded = _load_config()
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.info(
        "sandbox: registered (active=%s, owner_chats=%s, allowed=%s, group_allowed=%s, read_roots=%s, script_roots=%s, download_roots=%s)",
        loaded,
        sorted(_OWNER_CHAT_IDS),
        sorted(_ALLOWED_TOOLS),
        sorted(_GROUP_ALLOWED_TOOLS),
        [str(p) for p in _GROUP_ALLOWED_READ_ROOTS],
        [str(p) for p in _GROUP_ALLOWED_SCRIPT_ROOTS],
        [str(p) for p in _GROUP_ALLOWED_DOWNLOAD_ROOTS],
    )
