"""Per-chat capability boundary for Feishu.

The owner's main Feishu DM keeps the normal Hermes tool surface. Other
Feishu DMs get a small safe allowlist. Feishu groups additionally get:

* read-only wiki and skill access;
* a per-group data workspace under ``~/.hermes/tmp/group-workspaces``;
* exact, structured entry points to pre-installed Feishu document scripts.
* a narrow image-generation entry point executed inside that workspace's
  process sandbox.

Groups never receive the generic terminal or write-file tools. Trusted script
execution uses argv (never a shell) and, on macOS, ``sandbox-exec`` restricts
the whole process tree to writes inside that group's workspace.

The owner DM and trusted group testers also have a narrow HyperTeX bridge: MCP
calls are pinned to the ``hermes`` Contributor and, for a new case, the
``freestyle`` case type. Execution routing is server-owned and non-observable;
the sandbox discards model-supplied routing hints instead of forwarding or
describing them. Files attached to the current Feishu turn are copied into a
private stable staging directory and injected into create/iterate calls without
exposing cache paths to the model.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
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
_current_user_ids: contextvars.ContextVar[FrozenSet[str]] = contextvars.ContextVar(
    "sandbox_current_user_ids", default=frozenset()
)
_current_resource_refs: contextvars.ContextVar[FrozenSet[str]] = contextvars.ContextVar(
    "sandbox_current_resource_refs", default=frozenset()
)
_current_media_paths: contextvars.ContextVar[Tuple[str, ...]] = contextvars.ContextVar(
    "sandbox_current_media_paths", default=tuple()
)
_current_hypertex_staged_paths: contextvars.ContextVar[Tuple[str, ...]] = contextvars.ContextVar(
    "sandbox_current_hypertex_staged_paths", default=tuple()
)
_current_hypertex_call_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "sandbox_current_hypertex_call_count", default=0
)
_current_image_generation_call_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "sandbox_current_image_generation_call_count", default=0
)
_current_chart_generation_call_count: contextvars.ContextVar[int] = contextvars.ContextVar(
    "sandbox_current_chart_generation_call_count", default=0
)


_CONFIG_LOADED = False
_OWNER_CHAT_IDS: FrozenSet[str] = frozenset()
_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_TOOLS: FrozenSet[str] = frozenset()
_GROUP_MUTATION_USER_IDS: FrozenSet[str] = frozenset()
_GROUP_HYPERTEX_CHAT_IDS: FrozenSet[str] = frozenset()
_GROUP_HYPERTEX_USER_IDS: FrozenSet[str] = frozenset()
_GROUP_IMAGE_CHAT_IDS: FrozenSet[str] = frozenset()
_GROUP_CHART_CHAT_IDS: FrozenSet[str] = frozenset()
_GROUP_ALLOWED_READ_ROOTS: Tuple[Path, ...] = tuple()
_GROUP_WORKSPACE_ROOT: Optional[Path] = None
_PRIVATE_IMAGE_WORKSPACE_ROOT: Optional[Path] = None
_PRIVATE_CHART_WORKSPACE_ROOT: Optional[Path] = None
_GROUP_ALLOWED_SCRIPT_ACTIONS: FrozenSet[str] = frozenset()
_FEISHU_DOC_SCRIPTS_ROOT: Optional[Path] = None
_GROUP_IMAGE_SCRIPT: Optional[Path] = None
_GROUP_CHART_SCRIPT: Optional[Path] = None
_CHART_PYTHON_EXECUTABLE: Optional[Path] = None
_PYTHON_EXECUTABLE: Optional[Path] = None
_HYPERTEX_ASSET_STAGING_ROOT: Optional[Path] = None
_SCRIPT_TIMEOUT_SECONDS = 300
_GROUP_MAX_DOWNLOAD_BYTES = 50_000_000
_HYPERTEX_MAX_ASSET_BYTES = 50_000_000
_HYPERTEX_MAX_ASSETS_PER_TURN = 6
_HYPERTEX_ASSET_STAGING_TTL_SECONDS = 86_400
_GROUP_IMAGE_TIMEOUT_SECONDS = 900
_GROUP_IMAGE_MAX_INPUT_BYTES = 25_000_000
_GROUP_IMAGE_MAX_OUTPUT_BYTES = 10_000_000
_GROUP_IMAGE_MAX_INPUTS = 4
_GROUP_CHART_TIMEOUT_SECONDS = 60
_GROUP_CHART_MAX_OUTPUT_BYTES = 10_000_000
_GROUP_DOC_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_REQUIRE_PROCESS_SANDBOX = True

_BLOCK_MESSAGE = "This tool is not available in this chat."
_READ_ROOT_BLOCK_MESSAGE = "群聊只允许读取 wiki 和当前群自己的临时工作区。"
_CONFIG_BLOCK_MESSAGE = "群聊安全配置未成功加载，工具调用已按设计拒绝。"
_GROUP_CONTEXT_MESSAGE = "This tool is available only inside a configured Feishu group chat."
_RESOURCE_BLOCK_MESSAGE = "群聊只能访问当前消息明确引用的飞书资源。"
_MUTATION_TRUST_BLOCK_MESSAGE = "群聊中的飞书文档删除仅允许受信任的维护者执行。"
_MUTATION_REFERENCE_BLOCK_MESSAGE = "修改飞书文档时，必须在当前消息或显式引用中附上目标文档链接。"

_READ_PATH_TOOLS: FrozenSet[str] = frozenset({"read_file", "search_files"})
_GROUP_CHAT_TYPES: FrozenSet[str] = frozenset({"group", "channel", "forum", "thread"})
_WORKSPACE_TOOL = "group_cache"
_SCRIPT_TOOL = "feishu_doc_manage"
_IMAGE_TOOL = "group_image_generate"
_PRIVATE_IMAGE_TOOL = "secure_image_generate"
_CHART_TOOL = "group_chart_generate"
_PRIVATE_CHART_TOOL = "secure_chart_generate"
_HYPERTEX_CREATE_TOOL = "mcp__hypertex__hypertex_create_case"
_HYPERTEX_ITERATE_TOOL = "mcp__hypertex__hypertex_iterate_case"
_HYPERTEX_TASK_TOOL = "mcp__hypertex__tasks_get"
_HYPERTEX_TOOLS = frozenset(
    {
        _HYPERTEX_CREATE_TOOL,
        _HYPERTEX_ITERATE_TOOL,
        _HYPERTEX_TASK_TOOL,
    }
)
_HYPERTEX_PRIVATE_ROUTING_KEYS = frozenset(
    {"agent", "agent_key", "agent_name", "executor", "execution_backend", "model", "provider", "routing"}
)
_HYPERTEX_USERNAME = "hermes"
_HYPERTEX_CASE_TYPE = "freestyle"
_HYPERTEX_ONE_CALL_MESSAGE = "本轮已经调用过 HyperTeX。请直接根据已有结果回复用户；状态查询或重试请等待用户下一条消息。"
_HYPERTEX_GROUP_CHAT_BLOCK_MESSAGE = "HyperTeX 目前未在本群启用。"
_HYPERTEX_GROUP_BLOCK_MESSAGE = "HyperTeX 群聊内测目前仅对受信任的维护者开放。"
_GROUP_IMAGE_CHAT_BLOCK_MESSAGE = "图片生成目前未在本群启用。"
_GROUP_IMAGE_ONE_CALL_MESSAGE = "本轮已经生成过图片。若需调整，请在下一条消息中继续。"
_GROUP_CHART_CHAT_BLOCK_MESSAGE = "图表生成目前未在本群启用。"
_GROUP_CHART_ONE_CALL_MESSAGE = "本轮已经生成过图表。若需调整，请在下一条消息中继续。"
_MAX_FILE_CONTENT_BYTES = 1_000_000
_MAX_TOOL_OUTPUT_CHARS = 100_000
_DOC_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{5,200}$")
# Stop before Markdown's closing ``]`` so Gateway-normalized links such as
# ``[https://.../docx/TOKEN](https://.../docx/TOKEN)`` yield two valid URLs
# instead of one malformed ``URL](URL`` value. Trailing ``)`` is normalized by
# _resource_ref_candidates(), preserving ordinary bare-link handling.
_FEISHU_URL_RE = re.compile(r"https://[^\s<>\"'\]]+")
_EXPLICIT_TOKEN_RE = re.compile(r"(?i)\b(?:doc_token|file_token)\s*[:=]\s*([A-Za-z0-9_-]{5,200})")
_TRUST_REQUIRED_SCRIPT_ACTIONS = frozenset({"delete"})
_EXPLICIT_TARGET_SCRIPT_ACTIONS = frozenset({"append", "rebuild", "delete", "insert_image", "set_cover"})
_WEB_EXTRACT_PATH_RE = re.compile(r"(?m)^Full text saved to:\s*(.+?)\s*$")
_EPHEMERAL_READ_PATHS_BY_CHAT: Dict[str, Set[Path]] = {}
_EPHEMERAL_READ_PATHS_LOCK = threading.Lock()
_BEARER_OUTPUT_RE = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+")
_SECRET_OUTPUT_RE = re.compile(
    r"""(?ix)
    (\b(?:FEISHU_APP_ID|FEISHU_APP_SECRET|HERMES_IMAGE_GENERATION_API_KEY|tenant_access_token)\b
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
    "insert_image": "manage_doc_image.py",
    "set_cover": "manage_doc_image.py",
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
        "Supports create, append, rebuild, delete, image insertion, cover updates, URL read, and file download. "
        "For create/append/rebuild, provide content or a markdown_path previously written by group_cache."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create",
                    "append",
                    "rebuild",
                    "delete",
                    "read_url",
                    "download_file",
                    "insert_image",
                    "set_cover",
                ],
            },
            "doc_token": {"type": "string", "description": "Feishu docx token or docx URL."},
            "title": {"type": "string"},
            "content": {"type": "string", "description": "Markdown content."},
            "markdown_path": {
                "type": "string",
                "description": "Relative markdown file path in this group's workspace.",
            },
            "url": {"type": "string", "description": "Feishu/Lark URL or file token."},
            "image_path": {
                "type": "string",
                "description": (
                    "Relative image path in this group's workspace, normally returned by "
                    "group_image_generate or group_chart_generate. Mutually exclusive with attachment_index."
                ),
            },
            "attachment_index": {
                "type": "integer",
                "minimum": 0,
                "maximum": 7,
                "description": (
                    "Zero-based index among image attachments from the current message or explicit reply. "
                    "Mutually exclusive with image_path."
                ),
            },
            "insert_index": {
                "type": "integer",
                "minimum": 0,
                "description": "Optional exact top-level child index for insert_image.",
            },
            "position": {
                "type": "string",
                "enum": ["end", "before", "after"],
                "default": "end",
                "description": "Placement relative to anchor_text when inserting an image.",
            },
            "anchor_text": {
                "type": "string",
                "description": "Unique top-level heading or paragraph text used with position=before/after.",
            },
            "align": {
                "type": "string",
                "enum": ["left", "center", "right"],
                "default": "center",
            },
            "caption": {"type": "string", "description": "Optional image caption."},
            "width": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20000,
                "description": "Optional display width; the script derives height when omitted.",
            },
            "height": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20000,
                "description": "Optional display height; the script derives width when omitted.",
            },
            "offset_ratio_x": {"type": "number", "description": "Optional horizontal cover crop offset."},
            "offset_ratio_y": {"type": "number", "description": "Optional vertical cover crop offset."},
        },
        "required": ["action"],
    },
}


GROUP_IMAGE_GENERATE_SCHEMA = {
    "name": _IMAGE_TOOL,
    "description": (
        "Generate or edit one raster image through the operator-configured image service. "
        "Runs in this Feishu group's process sandbox, stores output in the group's isolated workspace, "
        "and can use only images attached to the current message or explicit reply."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed visual generation or editing instruction.",
            },
            "resolution": {
                "type": "string",
                "description": "Optional requested resolution such as 1K, 2K, or 4K.",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Optional requested aspect ratio such as 1:1, 16:9, or 9:16.",
            },
            "use_attached_images": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Use image attachments from the current message or explicit reply as edit/reference inputs."
                ),
            },
        },
        "required": ["prompt"],
    },
}

PRIVATE_IMAGE_GENERATE_SCHEMA = {
    **GROUP_IMAGE_GENERATE_SCHEMA,
    "name": _PRIVATE_IMAGE_TOOL,
    "description": (
        "Generate or edit one raster image through the operator-configured image service. "
        "Runs in a dedicated process sandbox and returns a media directive for delivery."
    ),
}


GROUP_CHART_GENERATE_SCHEMA = {
    "name": _CHART_TOOL,
    "description": (
        "Render a deterministic PNG chart from conversation-visible data. "
        "Choose business/statistical presets; the sandboxed adapter owns all "
        "Matplotlib and Seaborn implementation details."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "description": "Concise chart title."},
            "subtitle": {"type": "string", "description": "Optional scope or date-range summary."},
            "note": {"type": "string", "description": "Optional methodology/source note below the chart."},
            "chart_type": {
                "type": "string",
                "enum": [
                    "auto",
                    "line",
                    "scatter",
                    "bar",
                    "stacked_bar",
                    "horizontal_bar",
                    "area",
                    "pie",
                    "donut",
                    "waterfall",
                    "lollipop",
                    "hist",
                    "kde",
                    "ecdf",
                    "rug",
                    "count",
                    "point",
                    "box",
                    "violin",
                    "boxen",
                    "strip",
                    "swarm",
                    "regression",
                    "residual",
                    "heatmap",
                    "clustermap",
                    "joint",
                    "pair",
                ],
                "default": "auto",
            },
            "labels": {
                "type": "array",
                "maxItems": 500,
                "items": {"type": ["string", "number"]},
                "description": "Ordered labels or categorical observations.",
            },
            "series": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "values": {
                            "type": "array",
                            "maxItems": 500,
                            "items": {"type": ["number", "string", "null"]},
                        },
                    },
                    "required": ["name", "values"],
                },
                "description": "Series aligned with labels; distribution plots treat each series as samples.",
            },
            "x_values": {
                "type": "array",
                "maxItems": 500,
                "items": {"type": ["number", "string"]},
                "description": "Optional numeric X coordinates aligned with labels.",
            },
            "records": {
                "type": "array",
                "maxItems": 2000,
                "items": {
                    "type": "object",
                    "maxProperties": 20,
                    "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
                },
                "description": "Optional long-form records for advanced Seaborn charts and facets.",
            },
            "x_field": {"type": "string"},
            "y_field": {"type": "string"},
            "value_field": {"type": "string"},
            "hue_field": {"type": "string"},
            "style_field": {"type": "string"},
            "size_field": {"type": "string"},
            "weight_field": {"type": "string"},
            "matrix": {
                "type": "array",
                "maxItems": 120,
                "items": {
                    "type": "array",
                    "maxItems": 120,
                    "items": {"type": ["number", "string"]},
                },
            },
            "row_labels": {"type": "array", "maxItems": 120, "items": {"type": ["string", "number"]}},
            "column_labels": {"type": "array", "maxItems": 120, "items": {"type": ["string", "number"]}},
            "variables": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
            "x_label": {"type": "string"},
            "y_label": {"type": "string"},
            "unit": {"type": "string"},
            "value_format": {
                "type": "string",
                "enum": [
                    "auto",
                    "integer",
                    "decimal",
                    "compact",
                    "percent",
                    "currency_cny",
                    "currency_usd",
                    "currency_eur",
                ],
                "default": "auto",
            },
            "decimals": {"type": "integer", "minimum": 0, "maximum": 4, "default": 1},
            "percent_scale": {"type": "string", "enum": ["ratio", "value"], "default": "ratio"},
            "style_preset": {
                "type": "string",
                "enum": ["hidalgo", "finance", "report", "presentation", "minimal", "statistical"],
                "default": "hidalgo",
                "description": "Visual preset controlling background, grid, spines, fonts, and defaults.",
            },
            "palette_preset": {
                "type": "string",
                "enum": [
                    "auto",
                    "business",
                    "finance",
                    "muted",
                    "pastel",
                    "colorblind",
                    "blue",
                    "green",
                    "warm",
                    "cool",
                    "diverging",
                ],
                "default": "auto",
            },
            "layout_preset": {
                "type": "string",
                "enum": ["auto", "compact", "standard", "wide", "tall", "square"],
                "default": "auto",
            },
            "detail_preset": {
                "type": "string",
                "enum": ["overview", "balanced", "detailed", "smooth"],
                "default": "balanced",
                "description": "Controls bins, KDE grids, contour levels, bootstrap work, and mark density.",
            },
            "aggregation_preset": {
                "type": "string",
                "enum": ["mean", "median", "sum", "min", "max", "count"],
                "default": "mean",
            },
            "uncertainty_preset": {
                "type": "string",
                "enum": ["none", "sd", "se", "ci90", "ci95", "pi90", "pi95"],
                "default": "none",
            },
            "distribution_preset": {
                "type": "string",
                "enum": [
                    "count",
                    "density",
                    "probability",
                    "percent",
                    "comparison",
                    "stacked",
                    "filled",
                    "cumulative",
                    "discrete",
                ],
                "default": "count",
            },
            "categorical_preset": {
                "type": "string",
                "enum": ["summary", "median", "raw", "compact", "detailed"],
                "default": "summary",
            },
            "regression_preset": {
                "type": "string",
                "enum": ["linear", "robust", "lowess", "quadratic", "cubic", "logistic"],
                "default": "linear",
            },
            "matrix_preset": {
                "type": "string",
                "enum": [
                    "standard",
                    "annotated",
                    "diverging",
                    "clustered",
                    "row_normalized",
                    "column_normalized",
                ],
                "default": "standard",
            },
            "annotation_preset": {
                "type": "string",
                "enum": ["auto", "none", "values", "percent", "compact"],
                "default": "auto",
            },
            "sort": {"type": "string", "enum": ["none", "ascending", "descending"], "default": "none"},
            "category_order": {"type": "array", "maxItems": 500, "items": {"type": ["string", "number"]}},
            "highlight_label": {"type": "string"},
            "legend": {"type": "string", "enum": ["auto", "show", "hide"], "default": "auto"},
            "legend_position": {
                "type": "string",
                "enum": ["auto", "right", "bottom", "best"],
                "default": "auto",
                "description": "Auto uses a non-overlapping inside position, else bounded right/bottom fallback.",
            },
            "orientation": {"type": "string", "enum": ["vertical", "horizontal"]},
            "x_scale": {"type": "string", "enum": ["linear", "log", "symlog"], "default": "linear"},
            "y_scale": {"type": "string", "enum": ["linear", "log", "symlog"], "default": "linear"},
            "x_min": {"type": "number"},
            "x_max": {"type": "number"},
            "y_min": {"type": "number"},
            "y_max": {"type": "number"},
            "reference_lines": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "axis": {"type": "string", "enum": ["x", "y"]},
                        "value": {"type": "number"},
                        "label": {"type": "string"},
                        "style": {"type": "string", "enum": ["-", "--", ":", "-."]},
                        "color": {"type": "string"},
                    },
                    "required": ["value"],
                },
            },
            "facet_row": {"type": "string"},
            "facet_col": {"type": "string"},
            "col_wrap": {"type": "integer", "minimum": 1, "maximum": 8},
            "share_x": {"type": "boolean", "default": True},
            "share_y": {"type": "boolean", "default": True},
            "joint_kind": {"type": "string", "enum": ["scatter", "kde", "hist", "hex", "reg", "resid"]},
            "pair_kind": {"type": "string", "enum": ["scatter", "kde", "hist", "reg"]},
            "diag_kind": {"type": "string", "enum": ["auto", "hist", "kde"]},
            "corner": {"type": "boolean", "default": False},
            "quality": {"type": "string", "enum": ["standard", "high", "print"], "default": "standard"},
        },
        "required": ["title"],
    },
}
PRIVATE_CHART_GENERATE_SCHEMA = {
    **GROUP_CHART_GENERATE_SCHEMA,
    "name": _PRIVATE_CHART_TOOL,
    "description": (
        "Render a deterministic PNG chart from numeric values already present in the conversation. "
        "Runs without network access inside a dedicated private workspace."
    ),
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


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _event_user_ids(event: Any) -> FrozenSet[str]:
    """Collect exact Feishu identity variants without relying on display names.

    Feishu may populate both app-scoped ``open_id`` and tenant-scoped
    ``user_id``.  The adapter intentionally prefers ``user_id`` for
    ``SessionSource.user_id``, while operator-managed allowlists use the
    reproducible ``open_id`` values from people.yaml.  Keep both identities
    available to authorization hooks so adding contact scope cannot silently
    revoke an existing grant.
    """
    identities: Set[str] = set()

    source = _field(event, "source")
    for name in ("user_id", "user_id_alt"):
        value = _field(source, name)
        if value is not None and str(value).strip():
            identities.add(str(value).strip())

    raw = _field(event, "raw_message")
    raw_event = _field(raw, "event")
    sender = _field(raw_event, "sender")
    sender_id = _field(sender, "sender_id")
    for name in ("open_id", "user_id", "union_id"):
        value = _field(sender_id, name)
        if value is not None and str(value).strip():
            identities.add(str(value).strip())

    return frozenset(identities)


def _current_actor_ids() -> FrozenSet[str]:
    identities = set(_current_user_ids.get())
    primary = str(_current_user_id.get() or "").strip()
    if primary:
        identities.add(primary)
    return frozenset(identities)


def _current_actor_is_trusted(allowed_ids: FrozenSet[str]) -> bool:
    return bool(_current_actor_ids().intersection(allowed_ids))


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


def _hypertex_asset_name(source: Path) -> str:
    """Recover a safe user-facing filename from Hermes cache naming.

    The stem and the extension are sanitized apart. Folding the whole name in
    one ASCII pass used to eat the suffix of an all-CJK name (``销售培训.pdf``
    became ``pdf``), and HyperTeX types assets by suffix, so such a file was
    staged into the case but never preprocessed. Letters outside ASCII are kept
    so a CJK name stays recognizable in the case's ``assets/`` listing;
    HyperTeX folds its own derived ``_processed``/``_pdf`` paths separately.
    """
    name = Path(source.name).name
    parts = name.split("_", 2)
    if name.startswith("doc_") and len(parts) == 3:
        name = parts[2]
    name = unicodedata.normalize("NFC", name)
    suffix = Path(name).suffix
    stem = name[: len(name) - len(suffix)] if suffix else name
    stem = re.sub(r"[^\w. -]", "_", stem)[:160].strip(" ._") or "attachment"
    suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)[:32]
    return f"{stem}{suffix}" if suffix.strip(".") else stem


def _unique_hypertex_asset_name(name: str, used: Set[str]) -> str:
    candidate = name
    stem = Path(name).stem or "attachment"
    suffix = Path(name).suffix
    index = 2
    while candidate.casefold() in used:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    used.add(candidate.casefold())
    return candidate


def _cleanup_hypertex_asset_staging(root: Path) -> None:
    cutoff = time.time() - _HYPERTEX_ASSET_STAGING_TTL_SECONDS
    try:
        entries = list(root.iterdir())
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_dir() or entry.stat().st_mtime >= cutoff:
                continue
            resolved = entry.resolve(strict=False)
            if _path_within(resolved, root) and resolved != root:
                shutil.rmtree(resolved)
        except OSError:
            logger.debug("sandbox: failed to clean old HyperTeX staging path %s", entry, exc_info=True)


def _stage_current_hypertex_assets() -> Tuple[str, ...]:
    cached = _current_hypertex_staged_paths.get()
    if cached:
        return cached

    source_paths = _current_media_paths.get()
    if not source_paths:
        return tuple()
    if _HYPERTEX_ASSET_STAGING_ROOT is None:
        raise RuntimeError("HyperTeX asset staging root is not configured")
    if len(source_paths) > _HYPERTEX_MAX_ASSETS_PER_TURN:
        raise ValueError(f"at most {_HYPERTEX_MAX_ASSETS_PER_TURN} attachments are supported")

    root = _HYPERTEX_ASSET_STAGING_ROOT.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    _cleanup_hypertex_asset_staging(root)
    turn_dir = Path(tempfile.mkdtemp(prefix="turn-", dir=root)).resolve(strict=False)
    if not _path_within(turn_dir, root):
        raise RuntimeError("invalid HyperTeX staging directory")
    os.chmod(turn_dir, 0o700)

    staged: list[str] = []
    used_names: Set[str] = set()
    try:
        for raw_path in source_paths:
            source = Path(raw_path).expanduser()
            if source.is_symlink() or not source.is_file():
                raise FileNotFoundError("an attached file is no longer available")
            size = source.stat().st_size
            if size > _HYPERTEX_MAX_ASSET_BYTES:
                raise ValueError(f"attachment exceeds the {_HYPERTEX_MAX_ASSET_BYTES // 1_000_000} MB HyperTeX limit")
            name = _unique_hypertex_asset_name(_hypertex_asset_name(source), used_names)
            destination = (turn_dir / name).resolve(strict=False)
            if not _path_within(destination, turn_dir):
                raise RuntimeError("invalid HyperTeX asset filename")
            shutil.copy2(source, destination)
            staged.append(str(destination))
    except Exception:
        shutil.rmtree(turn_dir, ignore_errors=True)
        raise

    result = tuple(staged)
    _current_hypertex_staged_paths.set(result)
    return result


def _prepare_hypertex_call(tool_name: str, args: Any) -> Optional[Dict[str, Any]]:
    if tool_name not in _HYPERTEX_TOOLS:
        return None
    if not isinstance(args, dict):
        return {"action": "block", "message": "HyperTeX 工具参数格式无效，请重新提交。"}
    if _current_hypertex_call_count.get() >= 1:
        return {"action": "block", "message": _HYPERTEX_ONE_CALL_MESSAGE}
    _current_hypertex_call_count.set(1)

    if tool_name in {_HYPERTEX_CREATE_TOOL, _HYPERTEX_ITERATE_TOOL}:
        try:
            staged_paths = _stage_current_hypertex_assets()
        except Exception as exc:
            logger.warning("sandbox: HyperTeX attachment staging failed: %s", exc, exc_info=True)
            return {
                "action": "block",
                "message": "附件未能安全暂存给 HyperTeX，请重新发送附件后再试。",
            }
        # Execution routing belongs to HyperTeX and is intentionally absent
        # from the MCP contract. Drop defensive caller-side hints so old or
        # hallucinated arguments cannot turn private routing into a public API.
        for key in list(args):
            normalized = str(key).strip().lower().replace("-", "_")
            if "agent" in normalized or normalized in _HYPERTEX_PRIVATE_ROUTING_KEYS:
                args.pop(key, None)
        if tool_name == _HYPERTEX_CREATE_TOOL:
            args["owner_username"] = _HYPERTEX_USERNAME
            args["type"] = _HYPERTEX_CASE_TYPE
        else:
            args["username"] = _HYPERTEX_USERNAME
        args["asset_paths"] = list(staged_paths)
    return None


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


def _group_image_chat_allowed(chat_id: str) -> bool:
    return "*" in _GROUP_IMAGE_CHAT_IDS or chat_id in _GROUP_IMAGE_CHAT_IDS


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
    with _EPHEMERAL_READ_PATHS_LOCK:
        if resolved in _EPHEMERAL_READ_PATHS_BY_CHAT.get(chat_id, set()):
            return True
    return any(_path_within(resolved, root) for root in _GROUP_ALLOWED_READ_ROOTS)


def _clear_ephemeral_read_paths(chat_id: Any) -> None:
    text = str(chat_id or "")
    if not text:
        return
    with _EPHEMERAL_READ_PATHS_LOCK:
        _EPHEMERAL_READ_PATHS_BY_CHAT.pop(text, None)


def _record_web_extract_paths(chat_id: str, result: Any) -> None:
    """Allow only exact cache/web files emitted by this group's last extract."""
    if not chat_id:
        return
    payload = result
    if isinstance(result, str):
        try:
            payload = json.loads(result)
        except Exception:
            payload = result
    entries: list[tuple[str, str]] = []
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        for entry in payload["results"]:
            if isinstance(entry, dict) and isinstance(entry.get("url"), str) and isinstance(entry.get("content"), str):
                entries.append((entry["url"], entry["content"]))

    web_root = (_expand_path(os.getenv("HERMES_HOME", "~/.hermes")) / "cache" / "web").resolve(strict=False)
    accepted: Set[Path] = set()
    for url, text in entries:
        parsed = urlparse(url)
        host = (parsed.hostname or "page").replace(":", "_")
        slug = re.sub(r"[^A-Za-z0-9._-]", "-", host)[:60].strip("-") or "page"
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
        expected = (web_root / f"{slug}-{digest}.md").resolve(strict=False)
        for raw in _WEB_EXTRACT_PATH_RE.findall(text):
            path = _resolve_tool_path(raw.strip())
            if path == expected and _path_within(path, web_root) and path.is_file():
                accepted.add(path)
            if len(accepted) >= 5:
                break
    if not accepted:
        return
    with _EPHEMERAL_READ_PATHS_LOCK:
        _EPHEMERAL_READ_PATHS_BY_CHAT[chat_id] = accepted


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


def _image_extension_from_magic(path: Path) -> Optional[str]:
    try:
        with path.open("rb") as handle:
            prefix = handle.read(12)
    except OSError:
        return None
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return ".webp"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if prefix.startswith(b"BM"):
        return ".bmp"
    if prefix.startswith((b"II*\x00", b"MM\x00*")):
        return ".tiff"
    return None


def _stage_current_image_inputs(workspace: Path) -> tuple[list[str], Optional[Path]]:
    """Copy only this turn's image attachments into the current group workspace."""
    sources: list[Path] = []
    for raw in _current_media_paths.get():
        if len(sources) >= _GROUP_IMAGE_MAX_INPUTS:
            break
        try:
            source = Path(raw).expanduser()
            if source.is_symlink():
                continue
            source = source.resolve(strict=True)
            if not source.is_file() or source.stat().st_size > _GROUP_IMAGE_MAX_INPUT_BYTES:
                continue
            extension = _image_extension_from_magic(source)
            if extension is None:
                continue
            sources.append(source)
        except OSError:
            continue

    if not sources:
        return [], None

    staging_parent = workspace / ".image-inputs"
    staging_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging = Path(tempfile.mkdtemp(prefix="turn-", dir=staging_parent)).resolve(strict=True)
    if not _path_within(staging, workspace):
        raise RuntimeError("invalid image staging directory")

    relative_paths: list[str] = []
    for index, source in enumerate(sources, start=1):
        extension = _image_extension_from_magic(source)
        if extension is None:
            continue
        target = staging / f"input-{index}{extension}"
        shutil.copyfile(source, target)
        target.chmod(0o600)
        relative_paths.append(_relative_workspace_path(target, workspace))
    return relative_paths, staging


def _group_image_secret(name: str, default: str = "") -> str:
    """Read one profile-scoped secret without falling across multiplex profiles."""
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        value = os.environ.get(name, default)
    else:
        try:
            value = get_secret(name, default)
        except Exception:
            value = default
    return str(value or "").strip()


def _group_image_subprocess_env(workspace: Path) -> tuple[Dict[str, str], str]:
    api_key = _group_image_secret("HERMES_IMAGE_GENERATION_API_KEY")
    base_url = _group_image_secret("HERMES_IMAGE_GENERATION_BASE_URL")
    if not api_key or not base_url:
        raise RuntimeError("图片生成凭据尚未完整配置，请联系管理员。")
    env: Dict[str, str] = {
        "IMAGE_GENERATION_API_KEY": api_key,
        "IMAGE_GENERATION_API_BASE_URL": base_url,
        "HERMES_GROUP_WORKSPACE": str(workspace),
        "HERMES_GROUP_IMAGE_JOB_TIMEOUT": str(_GROUP_IMAGE_TIMEOUT_SECONDS),
        "HERMES_GROUP_IMAGE_MAX_INPUT_BYTES": str(_GROUP_IMAGE_MAX_INPUT_BYTES),
        "HERMES_GROUP_IMAGE_MAX_OUTPUT_BYTES": str(_GROUP_IMAGE_MAX_OUTPUT_BYTES),
        "HERMES_GROUP_IMAGE_MAX_INPUTS": str(_GROUP_IMAGE_MAX_INPUTS),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(workspace),
    }
    for name in (
        "PATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
    ):
        value = os.environ.get(name)
        if value:
            env[name] = value
    return env, api_key


def _run_group_image_script(payload: Dict[str, Any], workspace: Path) -> subprocess.CompletedProcess[str]:
    if _PYTHON_EXECUTABLE is None or not _PYTHON_EXECUTABLE.is_file():
        raise RuntimeError("configured Python interpreter is missing")
    if _GROUP_IMAGE_SCRIPT is None or not _GROUP_IMAGE_SCRIPT.is_file():
        raise RuntimeError("configured group image generation script is missing")
    command = [str(_PYTHON_EXECUTABLE), str(_GROUP_IMAGE_SCRIPT)]
    if _REQUIRE_PROCESS_SANDBOX:
        sandbox_exec = Path("/usr/bin/sandbox-exec")
        if not sandbox_exec.is_file():
            raise RuntimeError("required process sandbox is unavailable; refusing image generation")
        command = [str(sandbox_exec), "-p", _seatbelt_profile(workspace), *command]

    env, _api_key = _group_image_subprocess_env(workspace)
    return subprocess.run(
        command,
        cwd=str(workspace),
        env=env,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=_GROUP_IMAGE_TIMEOUT_SECONDS + 30,
        check=False,
    )


def _private_image_workspace() -> Path:
    if _PRIVATE_IMAGE_WORKSPACE_ROOT is None:
        raise RuntimeError("private image workspace root is not configured")
    root = _PRIVATE_IMAGE_WORKSPACE_ROOT.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    platform = str(_current_platform.get() or "main")
    chat_id = str(_current_chat_id.get() or "local")
    digest = hashlib.sha256(f"{platform}:{chat_id}".encode("utf-8")).hexdigest()[:24]
    workspace = (root / digest).resolve(strict=False)
    if not _path_within(workspace, root):
        raise RuntimeError("invalid private image workspace")
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    return workspace


def _execute_image_generation(args: Dict[str, Any], workspace: Path, *, scope_label: str) -> str:
    if not isinstance(args, dict):
        raise ValueError("image generation arguments must be an object")

    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > 4000:
        raise ValueError("prompt exceeds 4000 characters")

    payload: Dict[str, Any] = {"prompt": prompt}
    for name, limit in (("resolution", 32), ("aspect_ratio", 32)):
        value = args.get(name)
        if value is None:
            continue
        value = str(value).strip()
        if not value or len(value) > limit or any(char in value for char in "\r\n\x00"):
            raise ValueError(f"invalid {name}")
        payload[name] = value

    staged_paths: list[str] = []
    staging_dir: Optional[Path] = None
    if args.get("use_attached_images", True) is not False:
        staged_paths, staging_dir = _stage_current_image_inputs(workspace)
    if staged_paths:
        payload["image_paths"] = staged_paths

    actor = str(_current_user_id.get() or "unknown")
    logger.info(
        "sandbox: image generation start scope=%s actor=%s inputs=%s",
        scope_label,
        actor,
        len(staged_paths),
    )
    try:
        try:
            result = _run_group_image_script(payload, workspace)
        except Exception as exc:
            logger.warning(
                "sandbox: image generation process failed scope=%s actor=%s detail=%s",
                scope_label,
                actor,
                _redact_tool_output(str(exc))[:2000],
            )
            return _json_result(
                success=False,
                error="图片生成服务暂时不可用，请稍后重试或联系管理员。",
            )
    finally:
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)

    stdout = _redact_tool_output(result.stdout[-_MAX_TOOL_OUTPUT_CHARS:])
    stderr = _redact_tool_output(result.stderr[-_MAX_TOOL_OUTPUT_CHARS:])
    api_key = _group_image_secret("HERMES_IMAGE_GENERATION_API_KEY")
    if api_key:
        stdout = stdout.replace(api_key, "[REDACTED]")
        stderr = stderr.replace(api_key, "[REDACTED]")
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError:
        response = {
            "success": False,
            "error": "image generator returned invalid JSON",
        }
    if not isinstance(response, dict):
        response = {"success": False, "error": "image generator returned an invalid result"}
    if result.returncode != 0 or not response.get("success"):
        logger.warning(
            "sandbox: image generation failed scope=%s actor=%s returncode=%s detail=%s",
            scope_label,
            actor,
            result.returncode,
            str(response.get("error") or stderr or "unknown")[:2000],
        )
        return _json_result(
            success=False,
            error="图片生成服务暂时不可用，请稍后重试或联系管理员。",
        )

    output = _workspace_path(workspace, response.get("image"))
    if output.is_symlink() or not output.is_file():
        raise RuntimeError("image generator did not create a regular workspace file")
    if output.stat().st_size > _GROUP_IMAGE_MAX_OUTPUT_BYTES:
        raise RuntimeError("generated image exceeds the configured output limit")
    if _image_extension_from_magic(output) is None:
        raise RuntimeError("generated output is not a supported raster image")

    logger.info(
        "sandbox: image generation end scope=%s actor=%s backend_model=%s size=%s",
        scope_label,
        actor,
        response.get("model"),
        output.stat().st_size,
    )
    return _json_result(
        success=True,
        size_bytes=output.stat().st_size,
        workspace_path=_relative_workspace_path(output, workspace),
        media_directive=f"MEDIA:{output}",
        instruction="Include media_directive verbatim on its own line in the final response.",
    )


def _handle_group_image_generate(args: Dict[str, Any], **_kwargs: Any) -> str:
    chat_id = _require_group_context()
    if not _group_image_chat_allowed(chat_id):
        raise PermissionError(_GROUP_IMAGE_CHAT_BLOCK_MESSAGE)
    return _execute_image_generation(
        args,
        _workspace_for_chat(chat_id),
        scope_label=f"feishu-group:{_workspace_id(chat_id)}",
    )


def _handle_private_image_generate(args: Dict[str, Any], **_kwargs: Any) -> str:
    if _current_platform.get() == "feishu":
        chat_id = str(_current_chat_id.get() or "")
        if chat_id not in _OWNER_CHAT_IDS or _current_chat_type.get() in _GROUP_CHAT_TYPES:
            raise PermissionError(_BLOCK_MESSAGE)
    return _execute_image_generation(
        args,
        _private_image_workspace(),
        scope_label="private",
    )


def _private_chart_workspace() -> Path:
    if _PRIVATE_CHART_WORKSPACE_ROOT is None:
        raise RuntimeError("private chart workspace root is not configured")
    root = _PRIVATE_CHART_WORKSPACE_ROOT.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    platform = str(_current_platform.get() or "main")
    chat_id = str(_current_chat_id.get() or "local")
    digest = hashlib.sha256(f"{platform}:{chat_id}".encode()).hexdigest()[:24]
    workspace = (root / digest).resolve(strict=False)
    if not _path_within(workspace, root):
        raise RuntimeError("invalid private chart workspace")
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    return workspace


def _chart_seatbelt_profile(workspace: Path) -> str:
    quoted = _seatbelt_quote(workspace)
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        f'(deny file-write* (require-not (subpath "{quoted}")))\n'
        f'(deny process-exec (subpath "{quoted}"))\n'
    )


def _run_chart_script(payload: Dict[str, Any], workspace: Path) -> subprocess.CompletedProcess[str]:
    if _CHART_PYTHON_EXECUTABLE is None or not _CHART_PYTHON_EXECUTABLE.is_file():
        raise RuntimeError("configured chart Python interpreter is missing")
    if _GROUP_CHART_SCRIPT is None or not _GROUP_CHART_SCRIPT.is_file():
        raise RuntimeError("configured chart generation script is missing")
    command = [str(_CHART_PYTHON_EXECUTABLE), str(_GROUP_CHART_SCRIPT)]
    if _REQUIRE_PROCESS_SANDBOX:
        sandbox_exec = Path("/usr/bin/sandbox-exec")
        if not sandbox_exec.is_file():
            raise RuntimeError("required process sandbox is unavailable; refusing chart generation")
        command = [str(sandbox_exec), "-p", _chart_seatbelt_profile(workspace), *command]
    env: Dict[str, str] = {
        "HERMES_CHART_WORKSPACE": str(workspace),
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(workspace / ".matplotlib"),
        "XDG_CACHE_HOME": str(workspace / ".cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(workspace),
    }
    for name in ("PATH", "LANG", "LC_ALL", "TZ"):
        value = os.environ.get(name)
        if value:
            env[name] = value
    return subprocess.run(
        command,
        cwd=str(workspace),
        env=env,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=_GROUP_CHART_TIMEOUT_SECONDS,
        check=False,
    )


def _execute_chart_generation(args: Dict[str, Any], workspace: Path, *, scope_label: str) -> str:
    if not isinstance(args, dict):
        raise ValueError("chart generation arguments must be an object")
    allowed = set(GROUP_CHART_GENERATE_SCHEMA["parameters"]["properties"])
    payload: Dict[str, Any] = {key: value for key, value in args.items() if key in allowed and value is not None}
    if not str(payload.get("title") or "").strip():
        raise ValueError("title is required")
    payload.setdefault("chart_type", "auto")
    if not any(key in payload for key in ("series", "records", "matrix", "labels")):
        raise ValueError("provide labels/series, records, or matrix data")

    actor = str(_current_user_id.get() or "unknown")
    logger.info("sandbox: chart generation start scope=%s actor=%s", scope_label, actor)
    try:
        result = _run_chart_script(payload, workspace)
    except Exception as exc:
        logger.warning(
            "sandbox: chart generation process failed scope=%s actor=%s detail=%s",
            scope_label,
            actor,
            _redact_tool_output(str(exc))[:2000],
        )
        return _json_result(success=False, error="图表生成暂时不可用，请稍后重试或联系管理员。")

    stdout = _redact_tool_output(result.stdout[-_MAX_TOOL_OUTPUT_CHARS:])
    stderr = _redact_tool_output(result.stderr[-_MAX_TOOL_OUTPUT_CHARS:])
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError:
        response = {"success": False, "error": "chart renderer returned invalid JSON"}
    if not isinstance(response, dict):
        response = {"success": False, "error": "chart renderer returned an invalid result"}
    if result.returncode != 0 or not response.get("success"):
        error = str(response.get("error") or stderr or "图表生成失败。")[:1000]
        logger.warning(
            "sandbox: chart generation failed scope=%s actor=%s returncode=%s detail=%s",
            scope_label,
            actor,
            result.returncode,
            error,
        )
        return _json_result(success=False, error=error)

    output = _workspace_path(workspace, response.get("chart"))
    if output.is_symlink() or not output.is_file():
        raise RuntimeError("chart renderer did not create a regular workspace file")
    if output.stat().st_size > _GROUP_CHART_MAX_OUTPUT_BYTES:
        raise RuntimeError("generated chart exceeds the configured output limit")
    if _image_extension_from_magic(output) != ".png":
        raise RuntimeError("generated chart is not a PNG image")
    logger.info(
        "sandbox: chart generation end scope=%s actor=%s type=%s size=%s",
        scope_label,
        actor,
        response.get("chart_type"),
        output.stat().st_size,
    )
    return _json_result(
        success=True,
        chart_type=response.get("chart_type"),
        labels=response.get("labels"),
        series=response.get("series"),
        legend_position=response.get("legend_position"),
        legend_extent_fraction=response.get("legend_extent_fraction"),
        axis_label_layout=response.get("axis_label_layout"),
        size_bytes=output.stat().st_size,
        workspace_path=_relative_workspace_path(output, workspace),
        media_directive=f"MEDIA:{output}",
        instruction="Include media_directive verbatim on its own line in the final response.",
    )


def _group_chart_chat_allowed(chat_id: str) -> bool:
    return "*" in _GROUP_CHART_CHAT_IDS or chat_id in _GROUP_CHART_CHAT_IDS


def _handle_group_chart_generate(args: Dict[str, Any], **_kwargs: Any) -> str:
    chat_id = _require_group_context()
    if not _group_chart_chat_allowed(chat_id):
        raise PermissionError(_GROUP_CHART_CHAT_BLOCK_MESSAGE)
    return _execute_chart_generation(
        args,
        _workspace_for_chat(chat_id),
        scope_label=f"feishu-group:{_workspace_id(chat_id)}",
    )


def _handle_private_chart_generate(args: Dict[str, Any], **_kwargs: Any) -> str:
    if _current_platform.get() == "feishu":
        chat_id = str(_current_chat_id.get() or "")
        if chat_id not in _OWNER_CHAT_IDS or _current_chat_type.get() in _GROUP_CHAT_TYPES:
            raise PermissionError(_BLOCK_MESSAGE)
    return _execute_chart_generation(args, _private_chart_workspace(), scope_label="private")


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


def _resource_ref_candidates(value: Any) -> FrozenSet[str]:
    """Canonical URL/token identities for one Feishu resource argument."""
    text = str(value or "").strip().rstrip(".,;:!?)]}>")
    if not text:
        return frozenset()
    refs = {text}
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https" and (host.endswith(".feishu.cn") or host.endswith(".larksuite.com")):
        refs.add(f"https://{host}{parsed.path.rstrip('/')}")
        for marker in ("/docx/", "/docs/", "/file/"):
            if marker in parsed.path:
                token = parsed.path.split(marker, 1)[1].split("/", 1)[0]
                if _DOC_TOKEN_RE.fullmatch(token):
                    refs.add(token)
    elif _DOC_TOKEN_RE.fullmatch(text):
        refs.add(text)
    return frozenset(refs)


def _event_resource_refs(event: Any) -> FrozenSet[str]:
    refs: set[str] = set()
    # Only the active message and its explicit reply target grant resource
    # provenance. Backfilled channel_context is ambient history: treating URLs
    # there as authorized would let a later participant reuse an unrelated old
    # link without explicitly referencing it.
    for attr in ("text", "reply_to_text"):
        value = getattr(event, attr, None)
        if not isinstance(value, str):
            continue
        for url in _FEISHU_URL_RE.findall(value):
            refs.update(_resource_ref_candidates(url))
        for token in _EXPLICIT_TOKEN_RE.findall(value):
            refs.add(token)
    return frozenset(refs)


def _resource_was_referenced(value: Any) -> bool:
    return bool(_resource_ref_candidates(value).intersection(_current_resource_refs.get()))


def _successful_created_doc_refs(result: Any) -> FrozenSet[str]:
    """Extract only the exact doc created by a successful fixed-script call."""
    payload = result
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return frozenset()
    if not isinstance(payload, dict):
        return frozenset()
    if payload.get("success") is not True or payload.get("action") != "create" or payload.get("returncode") != 0:
        return frozenset()
    stdout = payload.get("stdout")
    if not isinstance(stdout, str):
        return frozenset()
    refs: set[str] = set()
    for token in re.findall(r"(?m)^Doc created:\s*([A-Za-z0-9_-]{5,200})\b", stdout):
        if _DOC_TOKEN_RE.fullmatch(token):
            refs.add(token)
    for url in _FEISHU_URL_RE.findall(stdout):
        parsed = urlparse(url.rstrip(".,;:!?)]}>"))
        if "/docx/" in parsed.path:
            refs.update(_resource_ref_candidates(url))
    return frozenset(refs)


def _group_doc_action_block(args: Any) -> Optional[str]:
    """Return a block message for an unauthorized structured doc action."""
    if not isinstance(args, dict):
        return _MUTATION_REFERENCE_BLOCK_MESSAGE
    action = str(args.get("action") or "")
    if action in _TRUST_REQUIRED_SCRIPT_ACTIONS:
        actor = str(_current_user_id.get() or "")
        if not _current_actor_is_trusted(_GROUP_MUTATION_USER_IDS):
            logger.info(
                "sandbox: blocked group document action=%s reason=untrusted_actor chat=%s actor=%s actor_ids=%s",
                action,
                str(_current_chat_id.get() or ""),
                actor or "unknown",
                sorted(_current_actor_ids()),
            )
            return _MUTATION_TRUST_BLOCK_MESSAGE
    if action in _EXPLICIT_TARGET_SCRIPT_ACTIONS and not _resource_was_referenced(args.get("doc_token")):
        logger.info(
            "sandbox: blocked group document action=%s reason=target_not_referenced chat=%s actor=%s",
            action,
            str(_current_chat_id.get() or ""),
            str(_current_user_id.get() or "unknown"),
        )
        return _MUTATION_REFERENCE_BLOCK_MESSAGE
    if action in {"read_url", "download_file"}:
        if not _resource_was_referenced(args.get("url")):
            return _RESOURCE_BLOCK_MESSAGE
    return None


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


def _doc_image_source(args: Dict[str, Any], workspace: Path) -> Path:
    relative = args.get("image_path")
    attachment_index = args.get("attachment_index")
    if (relative is None) == (attachment_index is None):
        raise ValueError("provide exactly one of image_path or attachment_index")

    if relative is not None:
        source = _workspace_path(workspace, relative)
    else:
        if isinstance(attachment_index, bool) or not isinstance(attachment_index, int):
            raise ValueError("attachment_index must be a zero-based integer")
        if attachment_index < 0:
            raise ValueError("attachment_index must be non-negative")
        image_sources: list[Path] = []
        for raw in _current_media_paths.get():
            try:
                candidate = Path(raw).expanduser()
                if candidate.is_symlink():
                    continue
                candidate = candidate.resolve(strict=True)
                if not candidate.is_file() or _image_extension_from_magic(candidate) is None:
                    continue
                image_sources.append(candidate)
            except OSError:
                continue
        if attachment_index >= len(image_sources):
            raise ValueError("attachment_index does not name an image in the current message or explicit reply")
        source = image_sources[attachment_index]

    if source.is_symlink() or not source.is_file():
        raise ValueError("image source must be a regular file")
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("image source is empty")
    if size > _GROUP_DOC_IMAGE_MAX_BYTES:
        raise ValueError("image source exceeds the configured Feishu document upload limit")
    if _image_extension_from_magic(source) is None:
        raise ValueError("image source must be PNG, JPEG, GIF, WebP, BMP, or TIFF")
    return source


def _bounded_optional_int(args: Dict[str, Any], name: str, *, minimum: int, maximum: int) -> Optional[int]:
    value = args.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _finite_optional_float(args: Dict[str, Any], name: str) -> Optional[float]:
    value = args.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _append_flag(argv: list[str], name: str, value: Any) -> None:
    if value is not None:
        argv.extend([f"--{name.replace('_', '-')}", str(value)])


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
    elif action in {"insert_image", "set_cover"}:
        source = _doc_image_source(args, workspace)
        argv = ["insert" if action == "insert_image" else "cover", _doc_token(args.get("doc_token")), str(source)]
        if action == "insert_image":
            insert_index = _bounded_optional_int(args, "insert_index", minimum=0, maximum=1_000_000)
            width = _bounded_optional_int(args, "width", minimum=1, maximum=20_000)
            height = _bounded_optional_int(args, "height", minimum=1, maximum=20_000)
            position = str(args.get("position") or "end").strip()
            if position not in {"end", "before", "after"}:
                raise ValueError("position must be end, before, or after")
            anchor_text = args.get("anchor_text")
            if anchor_text is not None:
                if not isinstance(anchor_text, str) or not anchor_text.strip() or len(anchor_text) > 500:
                    raise ValueError("anchor_text must be a non-empty string of at most 500 characters")
                anchor_text = anchor_text.strip()
            if insert_index is not None and anchor_text is not None:
                raise ValueError("insert_index cannot be combined with anchor_text")
            if position in {"before", "after"} and anchor_text is None:
                raise ValueError("position=before/after requires anchor_text")
            if position == "end" and anchor_text is not None:
                raise ValueError("anchor_text requires position=before or position=after")
            align = str(args.get("align") or "center").strip()
            if align not in {"left", "center", "right"}:
                raise ValueError("align must be left, center, or right")
            caption = args.get("caption")
            if caption is not None:
                if not isinstance(caption, str) or len(caption) > 1_000 or "\x00" in caption:
                    raise ValueError("caption must be a string of at most 1000 characters")
            _append_flag(argv, "insert_index", insert_index)
            _append_flag(argv, "position", position)
            _append_flag(argv, "anchor_text", anchor_text)
            _append_flag(argv, "align", align)
            _append_flag(argv, "caption", caption)
            _append_flag(argv, "width", width)
            _append_flag(argv, "height", height)
        else:
            _append_flag(argv, "offset_ratio_x", _finite_optional_float(args, "offset_ratio_x"))
            _append_flag(argv, "offset_ratio_y", _finite_optional_float(args, "offset_ratio_y"))
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
    try:
        from gateway.session_context import get_session_env

        turn_id = get_session_env("HERMES_SESSION_MESSAGE_ID", "") or ""
    except Exception:
        turn_id = ""
    env.update(
        {
            "HERMES_GROUP_WORKSPACE": str(workspace),
            "HERMES_FEISHU_BACKUP_DIR": str(workspace / "feishu-backups"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": str(workspace),
            "HERMES_GROUP_MAX_DOWNLOAD_BYTES": str(_GROUP_MAX_DOWNLOAD_BYTES),
            "HERMES_FEISHU_IMAGE_MAX_BYTES": str(_GROUP_DOC_IMAGE_MAX_BYTES),
            "HERMES_FEISHU_VERSION_LEDGER": str(workspace / ".feishu-version-turns.json"),
        }
    )
    if turn_id:
        env["HERMES_FEISHU_VERSION_TURN_ID"] = turn_id
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
    block_message = _group_doc_action_block(args)
    if block_message is not None:
        raise PermissionError(block_message)
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


def _group_image_available() -> bool:
    return bool(
        _CONFIG_LOADED
        and _GROUP_WORKSPACE_ROOT
        and _PRIVATE_IMAGE_WORKSPACE_ROOT
        and _GROUP_IMAGE_SCRIPT
        and _GROUP_IMAGE_SCRIPT.is_file()
        and _PYTHON_EXECUTABLE
        and _PYTHON_EXECUTABLE.is_file()
        and (not _REQUIRE_PROCESS_SANDBOX or Path("/usr/bin/sandbox-exec").is_file())
    )


def _chart_tools_available() -> bool:
    return bool(
        _CONFIG_LOADED
        and _GROUP_WORKSPACE_ROOT
        and _PRIVATE_CHART_WORKSPACE_ROOT
        and _GROUP_CHART_SCRIPT
        and _GROUP_CHART_SCRIPT.is_file()
        and _CHART_PYTHON_EXECUTABLE
        and _CHART_PYTHON_EXECUTABLE.is_file()
        and (not _REQUIRE_PROCESS_SANDBOX or Path("/usr/bin/sandbox-exec").is_file())
    )


def _load_config() -> bool:
    global _CONFIG_LOADED, _OWNER_CHAT_IDS, _ALLOWED_TOOLS, _GROUP_ALLOWED_TOOLS
    global _GROUP_MUTATION_USER_IDS, _GROUP_HYPERTEX_CHAT_IDS, _GROUP_HYPERTEX_USER_IDS
    global _GROUP_IMAGE_CHAT_IDS, _GROUP_IMAGE_SCRIPT
    global _GROUP_CHART_CHAT_IDS, _GROUP_CHART_SCRIPT, _CHART_PYTHON_EXECUTABLE
    global _GROUP_ALLOWED_READ_ROOTS, _GROUP_WORKSPACE_ROOT, _PRIVATE_IMAGE_WORKSPACE_ROOT
    global _PRIVATE_CHART_WORKSPACE_ROOT
    global _GROUP_ALLOWED_SCRIPT_ACTIONS
    global _FEISHU_DOC_SCRIPTS_ROOT, _PYTHON_EXECUTABLE, _SCRIPT_TIMEOUT_SECONDS
    global _GROUP_MAX_DOWNLOAD_BYTES, _HYPERTEX_ASSET_STAGING_ROOT
    global _HYPERTEX_MAX_ASSET_BYTES, _HYPERTEX_MAX_ASSETS_PER_TURN
    global _HYPERTEX_ASSET_STAGING_TTL_SECONDS
    global _GROUP_IMAGE_TIMEOUT_SECONDS, _GROUP_IMAGE_MAX_INPUT_BYTES
    global _GROUP_IMAGE_MAX_OUTPUT_BYTES, _GROUP_IMAGE_MAX_INPUTS
    global _GROUP_CHART_TIMEOUT_SECONDS, _GROUP_CHART_MAX_OUTPUT_BYTES
    global _GROUP_DOC_IMAGE_MAX_BYTES
    global _REQUIRE_PROCESS_SANDBOX, _BLOCK_MESSAGE, _READ_ROOT_BLOCK_MESSAGE
    global _RESOURCE_BLOCK_MESSAGE, _MUTATION_TRUST_BLOCK_MESSAGE
    global _MUTATION_REFERENCE_BLOCK_MESSAGE

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
    private_image_workspace_value = data.get("private_image_workspace_root")
    private_chart_workspace_value = data.get("private_chart_workspace_root")
    scripts_value = data.get("feishu_doc_scripts_root")
    python_value = data.get("python_executable")
    chart_python_value = data.get("chart_python_executable")
    hypertex_staging_value = data.get("hypertex_asset_staging_root")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            workspace_value,
            private_image_workspace_value,
            private_chart_workspace_value,
            scripts_value,
            python_value,
            chart_python_value,
            hypertex_staging_value,
        )
    ):
        logger.error(
            "sandbox: workspace roots, scripts root, Python executable, and HyperTeX staging root must be configured"
        )
        return False

    actions = frozenset(str(item) for item in script_actions)
    if not actions or not actions.issubset(_FEISHU_SCRIPT_FILES):
        logger.error("sandbox: invalid or empty Feishu script action allowlist: %s", sorted(actions))
        return False

    _OWNER_CHAT_IDS = frozenset(owners)
    _ALLOWED_TOOLS = frozenset(str(item) for item in allowed)
    _GROUP_ALLOWED_TOOLS = frozenset(str(item) for item in group_allowed)
    _GROUP_MUTATION_USER_IDS = frozenset(_coerce_chat_ids(data.get("trusted_feishu_user_ids_for_group_mutations")))
    _GROUP_HYPERTEX_CHAT_IDS = frozenset(_coerce_chat_ids(data.get("trusted_feishu_chat_ids_for_group_hypertex")))
    _GROUP_HYPERTEX_USER_IDS = frozenset(_coerce_chat_ids(data.get("trusted_feishu_user_ids_for_group_hypertex")))
    _GROUP_IMAGE_CHAT_IDS = frozenset(_coerce_chat_ids(data.get("trusted_feishu_chat_ids_for_group_image_generation")))
    _GROUP_CHART_CHAT_IDS = frozenset(_coerce_chat_ids(data.get("trusted_feishu_chat_ids_for_group_chart_generation")))
    _GROUP_ALLOWED_READ_ROOTS = _coerce_paths(data.get("allowed_read_roots_for_outsider_groups"))
    _GROUP_WORKSPACE_ROOT = _expand_path(workspace_value)
    _PRIVATE_IMAGE_WORKSPACE_ROOT = _expand_path(private_image_workspace_value)
    _PRIVATE_CHART_WORKSPACE_ROOT = _expand_path(private_chart_workspace_value)
    _GROUP_ALLOWED_SCRIPT_ACTIONS = actions
    _FEISHU_DOC_SCRIPTS_ROOT = _expand_path(scripts_value)
    image_script_value = data.get("group_image_generation_script")
    _GROUP_IMAGE_SCRIPT = (
        _expand_path(image_script_value) if isinstance(image_script_value, str) and image_script_value.strip() else None
    )
    chart_script_value = data.get("chart_generation_script")
    _GROUP_CHART_SCRIPT = (
        _expand_path(chart_script_value) if isinstance(chart_script_value, str) and chart_script_value.strip() else None
    )
    _PYTHON_EXECUTABLE = _expand_path(python_value)
    # Preserve the venv entrypoint path. Path.resolve() follows ``bin/python``
    # to the base interpreter and loses the venv's site-packages.
    _CHART_PYTHON_EXECUTABLE = Path(os.path.abspath(os.path.expanduser(str(chart_python_value))))
    _HYPERTEX_ASSET_STAGING_ROOT = _expand_path(hypertex_staging_value)
    _REQUIRE_PROCESS_SANDBOX = bool(data.get("require_process_sandbox", True))
    try:
        _SCRIPT_TIMEOUT_SECONDS = max(1, min(900, int(data.get("script_timeout_seconds", 300))))
        _GROUP_MAX_DOWNLOAD_BYTES = max(
            1_000_000,
            min(500_000_000, int(data.get("group_max_download_bytes", 50_000_000))),
        )
        _HYPERTEX_MAX_ASSET_BYTES = max(
            1_000_000,
            min(500_000_000, int(data.get("hypertex_max_asset_bytes", 50_000_000))),
        )
        _HYPERTEX_MAX_ASSETS_PER_TURN = max(
            1,
            min(20, int(data.get("hypertex_max_assets_per_turn", 6))),
        )
        _HYPERTEX_ASSET_STAGING_TTL_SECONDS = max(
            3_600,
            min(604_800, int(data.get("hypertex_asset_staging_ttl_seconds", 86_400))),
        )
        _GROUP_IMAGE_TIMEOUT_SECONDS = max(
            30,
            min(1_200, int(data.get("group_image_generation_timeout_seconds", 900))),
        )
        _GROUP_IMAGE_MAX_INPUT_BYTES = max(
            1_000_000,
            min(100_000_000, int(data.get("group_image_max_input_bytes", 25_000_000))),
        )
        _GROUP_IMAGE_MAX_OUTPUT_BYTES = max(
            1_000_000,
            min(20_000_000, int(data.get("group_image_max_output_bytes", 10_000_000))),
        )
        _GROUP_IMAGE_MAX_INPUTS = max(
            1,
            min(8, int(data.get("group_image_max_inputs", 4))),
        )
        _GROUP_CHART_TIMEOUT_SECONDS = max(
            5,
            min(300, int(data.get("chart_generation_timeout_seconds", 60))),
        )
        _GROUP_CHART_MAX_OUTPUT_BYTES = max(
            1_000_000,
            min(20_000_000, int(data.get("chart_max_output_bytes", 10_000_000))),
        )
        _GROUP_DOC_IMAGE_MAX_BYTES = max(
            1_000_000,
            min(20 * 1024 * 1024, int(data.get("group_doc_image_max_bytes", 20 * 1024 * 1024))),
        )
    except (TypeError, ValueError):
        logger.error("sandbox: script, download, and HyperTeX staging limits must be integers")
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
    if _GROUP_IMAGE_CHAT_IDS and (_GROUP_IMAGE_SCRIPT is None or not _GROUP_IMAGE_SCRIPT.is_file()):
        logger.error("sandbox: group image generation is enabled but its fixed script is missing")
    if _GROUP_CHART_CHAT_IDS and (
        _GROUP_CHART_SCRIPT is None
        or not _GROUP_CHART_SCRIPT.is_file()
        or _CHART_PYTHON_EXECUTABLE is None
        or not _CHART_PYTHON_EXECUTABLE.is_file()
    ):
        logger.error("sandbox: group chart generation is enabled but its renderer is missing")

    message = data.get("block_message")
    read_message = data.get("read_root_block_message")
    resource_message = data.get("resource_block_message")
    mutation_trust_message = data.get("mutation_trust_block_message")
    mutation_reference_message = data.get("mutation_reference_block_message")
    legacy_mutation_message = data.get("mutation_block_message")
    if isinstance(message, str) and message.strip():
        _BLOCK_MESSAGE = message
    if isinstance(read_message, str) and read_message.strip():
        _READ_ROOT_BLOCK_MESSAGE = read_message
    if isinstance(resource_message, str) and resource_message.strip():
        _RESOURCE_BLOCK_MESSAGE = resource_message
    if isinstance(mutation_trust_message, str) and mutation_trust_message.strip():
        _MUTATION_TRUST_BLOCK_MESSAGE = mutation_trust_message
    elif isinstance(legacy_mutation_message, str) and legacy_mutation_message.strip():
        _MUTATION_TRUST_BLOCK_MESSAGE = legacy_mutation_message
    if isinstance(mutation_reference_message, str) and mutation_reference_message.strip():
        _MUTATION_REFERENCE_BLOCK_MESSAGE = mutation_reference_message
    elif isinstance(legacy_mutation_message, str) and legacy_mutation_message.strip():
        _MUTATION_REFERENCE_BLOCK_MESSAGE = legacy_mutation_message

    _CONFIG_LOADED = True
    return True


def _on_pre_gateway_dispatch(event: Any = None, **_kwargs: Any) -> Optional[Dict[str, Any]]:
    if event is None or getattr(event, "source", None) is None:
        _current_platform.set(None)
        _current_chat_id.set(None)
        _current_chat_type.set(None)
        _current_user_id.set(None)
        _current_user_ids.set(frozenset())
        _current_resource_refs.set(frozenset())
        _current_media_paths.set(tuple())
        _current_hypertex_staged_paths.set(tuple())
        _current_hypertex_call_count.set(0)
        _current_image_generation_call_count.set(0)
        _current_chart_generation_call_count.set(0)
        return None
    source = event.source
    _clear_ephemeral_read_paths(getattr(source, "chat_id", None))
    platform = getattr(source, "platform", None)
    _current_platform.set(platform.value if platform else None)
    _current_chat_id.set(getattr(source, "chat_id", None))
    _current_chat_type.set(str(getattr(source, "chat_type", "") or "").lower() or None)
    _current_user_id.set(getattr(source, "user_id", None))
    _current_user_ids.set(_event_user_ids(event))
    _current_resource_refs.set(_event_resource_refs(event))
    _current_media_paths.set(
        tuple(str(path) for path in (getattr(event, "media_urls", None) or []) if str(path).strip())
    )
    _current_hypertex_staged_paths.set(tuple())
    _current_hypertex_call_count.set(0)
    _current_image_generation_call_count.set(0)
    _current_chart_generation_call_count.set(0)
    return None


def _on_post_tool_call(
    tool_name: str = "",
    result: Any = None,
    **_kwargs: Any,
) -> None:
    if not _CONFIG_LOADED or not _is_group_context():
        return None
    if tool_name == "web_extract":
        _record_web_extract_paths(str(_current_chat_id.get() or ""), result)
    elif tool_name == _SCRIPT_TOOL:
        created_refs = _successful_created_doc_refs(result)
        if created_refs:
            _current_resource_refs.set(frozenset(set(_current_resource_refs.get()) | set(created_refs)))
            logger.info(
                "sandbox: granted same-turn access to created document chat=%s refs=%s",
                str(_current_chat_id.get() or ""),
                sorted(ref for ref in created_refs if _DOC_TOKEN_RE.fullmatch(ref)),
            )
    return None


def _on_pre_tool_call(tool_name: str = "", args: Any = None, **_kwargs: Any) -> Optional[Dict[str, Any]]:
    if _current_platform.get() != "feishu":
        return None
    if not _CONFIG_LOADED:
        return {"action": "block", "message": _CONFIG_BLOCK_MESSAGE}

    chat_id = str(_current_chat_id.get() or "")
    if chat_id in _OWNER_CHAT_IDS:
        return _prepare_hypertex_call(tool_name, args)

    chat_type = _current_chat_type.get()
    if chat_type in _GROUP_CHAT_TYPES:
        if tool_name not in _GROUP_ALLOWED_TOOLS:
            logger.info(
                "sandbox: blocked group tool=%s chat=%s chat_type=%s",
                tool_name,
                chat_id,
                chat_type,
            )
            return {"action": "block", "message": _BLOCK_MESSAGE}
        if tool_name in _HYPERTEX_TOOLS:
            if chat_id not in _GROUP_HYPERTEX_CHAT_IDS:
                return {"action": "block", "message": _HYPERTEX_GROUP_CHAT_BLOCK_MESSAGE}
            if not _current_actor_is_trusted(_GROUP_HYPERTEX_USER_IDS):
                logger.info(
                    "sandbox: blocked group HyperTeX reason=untrusted_actor chat=%s actor=%s actor_ids=%s",
                    chat_id,
                    str(_current_user_id.get() or "unknown"),
                    sorted(_current_actor_ids()),
                )
                return {"action": "block", "message": _HYPERTEX_GROUP_BLOCK_MESSAGE}
            return _prepare_hypertex_call(tool_name, args)
        if tool_name == _IMAGE_TOOL:
            if not _group_image_chat_allowed(chat_id):
                return {"action": "block", "message": _GROUP_IMAGE_CHAT_BLOCK_MESSAGE}
            if _current_image_generation_call_count.get() >= 1:
                return {"action": "block", "message": _GROUP_IMAGE_ONE_CALL_MESSAGE}
            _current_image_generation_call_count.set(1)
            return None
        if tool_name == _CHART_TOOL:
            if not _group_chart_chat_allowed(chat_id):
                return {"action": "block", "message": _GROUP_CHART_CHAT_BLOCK_MESSAGE}
            if _current_chart_generation_call_count.get() >= 1:
                return {"action": "block", "message": _GROUP_CHART_ONE_CALL_MESSAGE}
            _current_chart_generation_call_count.set(1)
            return None
        if tool_name in _READ_PATH_TOOLS:
            if (
                tool_name == "search_files"
                and isinstance(args, dict)
                and str(args.get("path") or ".").strip() in {"", "."}
                and _GROUP_ALLOWED_READ_ROOTS
            ):
                args["path"] = str(_GROUP_ALLOWED_READ_ROOTS[0])
            path_text = _tool_read_path(tool_name, args)
            if not _read_path_allowed_for_group(path_text, chat_id):
                logger.info("sandbox: blocked group read tool=%s path=%s chat=%s", tool_name, path_text, chat_id)
                return {"action": "block", "message": _READ_ROOT_BLOCK_MESSAGE}
        if tool_name == "feishu_doc_read":
            token = args.get("doc_token") if isinstance(args, dict) else None
            if not _resource_was_referenced(token):
                return {"action": "block", "message": _RESOURCE_BLOCK_MESSAGE}
        if tool_name == _SCRIPT_TOOL:
            block_message = _group_doc_action_block(args)
            if block_message is not None:
                return {"action": "block", "message": block_message}
        return None

    if tool_name in _ALLOWED_TOOLS:
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
    ctx.register_tool(
        name=_IMAGE_TOOL,
        toolset="sandbox_group",
        schema=GROUP_IMAGE_GENERATE_SCHEMA,
        handler=_handle_group_image_generate,
        check_fn=_group_image_available,
        description="Generate or edit an image inside an allowlisted Feishu group sandbox.",
    )
    ctx.register_tool(
        name=_PRIVATE_IMAGE_TOOL,
        toolset="image_gen",
        schema=PRIVATE_IMAGE_GENERATE_SCHEMA,
        handler=_handle_private_image_generate,
        check_fn=_group_image_available,
        description="Generate or edit an image inside a dedicated private workspace sandbox.",
    )
    ctx.register_tool(
        name=_CHART_TOOL,
        toolset="sandbox_group",
        schema=GROUP_CHART_GENERATE_SCHEMA,
        handler=_handle_group_chart_generate,
        check_fn=_chart_tools_available,
        description="Render a chart inside an allowlisted Feishu group sandbox.",
    )
    ctx.register_tool(
        name=_PRIVATE_CHART_TOOL,
        toolset="image_gen",
        schema=PRIVATE_CHART_GENERATE_SCHEMA,
        handler=_handle_private_chart_generate,
        check_fn=_chart_tools_available,
        description="Render a chart inside a dedicated private workspace sandbox.",
    )
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    logger.info(
        "sandbox: registered (pid=%s, active=%s, owner_chats=%s, group_allowed=%s, read_roots=%s, "
        "workspace_root=%s, script_actions=%s, mutation_users=%s, doc_delete_only=%s, "
        "doc_media_actions=%s, doc_image_max_bytes=%s, hypertex_chats=%s, "
        "hypertex_users=%s, hypertex_routing_policy=%s, image_chats=%s, image_script=%s, "
        "chart_chats=%s, chart_script=%s, process_sandbox=%s)",
        os.getpid(),
        loaded,
        sorted(_OWNER_CHAT_IDS),
        sorted(_GROUP_ALLOWED_TOOLS),
        [str(path) for path in _GROUP_ALLOWED_READ_ROOTS],
        _GROUP_WORKSPACE_ROOT,
        sorted(_GROUP_ALLOWED_SCRIPT_ACTIONS),
        sorted(_GROUP_MUTATION_USER_IDS),
        _TRUST_REQUIRED_SCRIPT_ACTIONS == frozenset({"delete"}),
        sorted({"insert_image", "set_cover"}.intersection(_GROUP_ALLOWED_SCRIPT_ACTIONS)),
        _GROUP_DOC_IMAGE_MAX_BYTES,
        sorted(_GROUP_HYPERTEX_CHAT_IDS),
        sorted(_GROUP_HYPERTEX_USER_IDS),
        "server-owned/non-observable",
        sorted(_GROUP_IMAGE_CHAT_IDS),
        _GROUP_IMAGE_SCRIPT,
        sorted(_GROUP_CHART_CHAT_IDS),
        _GROUP_CHART_SCRIPT,
        _REQUIRE_PROCESS_SANDBOX,
    )
