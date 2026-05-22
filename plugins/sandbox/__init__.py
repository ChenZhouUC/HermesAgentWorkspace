"""sandbox plugin — per-chat tool restriction for Feishu.

Owner's main Feishu DM gets the full toolset. Every other Feishu chat
(group chats, DMs with other people) is restricted to a small allowlist
of safe tools. Non-Feishu sources (CLI/TUI, cron-triggered sessions,
internal events) are never gated.

Mechanism:
  - pre_gateway_dispatch  fires once per inbound message; stashes the
    source platform + chat_id in ContextVars. ContextVars propagate
    through asyncio create_task / await boundaries, so the same values
    are visible from every downstream tool call spawned for that
    message. Concurrent dispatches each carry their own context.

  - pre_tool_call  reads the ContextVars. If platform != "feishu" OR
    chat_id matches the owner's DM, the call is allowed. Otherwise
    only tools in the configured allowlist pass; anything else is
    blocked with the configured user-visible message.
"""

from __future__ import annotations

import contextvars
import logging
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set

import yaml

logger = logging.getLogger(__name__)


_current_chat_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_chat_id", default=None
)
_current_platform: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "sandbox_current_platform", default=None
)


_OWNER_CHAT_IDS: FrozenSet[str] = frozenset()
_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_BLOCK_MESSAGE: str = "This tool is not available in this chat."


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


def _load_config() -> bool:
    """Load config.yaml next to this file. Returns True iff at least one owner is set."""
    global _OWNER_CHAT_IDS, _ALLOWED_TOOLS, _BLOCK_MESSAGE
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

    logger.info(
        "sandbox: blocked tool=%s chat=%s (allowed=%s)",
        tool_name,
        chat_id,
        sorted(_ALLOWED_TOOLS),
    )
    return {"action": "block", "message": _BLOCK_MESSAGE}


def register(ctx: Any) -> None:
    loaded = _load_config()
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    logger.info(
        "sandbox: registered (active=%s, owner_chats=%s, allowed=%s)",
        loaded,
        sorted(_OWNER_CHAT_IDS),
        sorted(_ALLOWED_TOOLS),
    )
