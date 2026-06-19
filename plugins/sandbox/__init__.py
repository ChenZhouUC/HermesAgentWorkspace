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
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set, Tuple

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
_BLOCK_MESSAGE: str = "This tool is not available in this chat."
_READ_ROOT_BLOCK_MESSAGE: str = "群聊只允许读取配置的只读知识库目录。"
_READ_PATH_TOOLS: FrozenSet[str] = frozenset({"read_file", "search_files"})


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
    expanded = os.path.expandvars(os.path.expanduser(path_text.strip()))
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve(strict=False)
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _load_config() -> bool:
    """Load config.yaml next to this file. Returns True iff at least one owner is set."""
    global _OWNER_CHAT_IDS, _ALLOWED_TOOLS, _GROUP_ALLOWED_TOOLS, _GROUP_ALLOWED_READ_ROOTS, _BLOCK_MESSAGE
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

    msg = data.get("block_message")
    if isinstance(msg, str) and msg.strip():
        _BLOCK_MESSAGE = msg

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
        "sandbox: registered (active=%s, owner_chats=%s, allowed=%s, group_allowed=%s, read_roots=%s)",
        loaded,
        sorted(_OWNER_CHAT_IDS),
        sorted(_ALLOWED_TOOLS),
        sorted(_GROUP_ALLOWED_TOOLS),
        [str(p) for p in _GROUP_ALLOWED_READ_ROOTS],
    )
