#!/usr/bin/env python3
"""Safely update one configured Feishu group's avatar.

The helper deliberately accepts only a configured group name/chat ID and a
local raster image. It uses the official Feishu SDK, reads credentials from the
process environment or ``~/.hermes/.env``, and never prints credentials, local
paths, or the uploaded image key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from lark_oapi.api.im.v1 import (
    CreateImageRequest,
    CreateImageRequestBody,
    GetChatRequest,
    UpdateChatRequest,
    UpdateChatRequestBody,
)
from lark_oapi.client import Client
from lark_oapi.core.enum import LogLevel
from PIL import Image, UnidentifiedImageError

MAX_AVATAR_BYTES = 10 * 1024 * 1024
MAX_AVATAR_SIDE = 4096
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
CHAT_ID_RE = re.compile(r"^oc_[A-Za-z0-9]{16,64}$")


class AvatarUpdateError(RuntimeError):
    """A safe, user-actionable avatar update failure."""


@dataclass(frozen=True)
class GroupTarget:
    name: str
    chat_id: str


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    format: str
    width: int
    height: int
    size_bytes: int


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser().resolve()


def _clean_text(value: object, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    return "".join(char for char in text if char in "\n\t" or ord(char) >= 32)[:limit]


def _load_groups(groups_file: Path) -> list[dict[str, Any]]:
    try:
        raw = yaml.safe_load(groups_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AvatarUpdateError("configured Feishu group roster could not be read") from exc
    groups = raw.get("groups") if isinstance(raw, dict) else None
    if not isinstance(groups, list):
        raise AvatarUpdateError("configured Feishu group roster is invalid")
    return [group for group in groups if isinstance(group, dict)]


def _resolve_group(query: str, groups_file: Path) -> GroupTarget:
    requested = query.strip()
    if not requested:
        raise AvatarUpdateError("group name or chat ID is required")

    matches: list[GroupTarget] = []
    folded = requested.casefold()
    for group in _load_groups(groups_file):
        chat_id = _clean_text(group.get("chat_id"), limit=80)
        name = _clean_text(group.get("name"), limit=160)
        aliases = group.get("aliases")
        names = [name]
        if isinstance(aliases, list):
            names.extend(_clean_text(alias, limit=160) for alias in aliases)
        if requested == chat_id or any(candidate.casefold() == folded for candidate in names if candidate):
            if not name or not CHAT_ID_RE.fullmatch(chat_id):
                raise AvatarUpdateError("matched group has an invalid name or chat ID")
            matches.append(GroupTarget(name=name, chat_id=chat_id))

    unique = {(match.name, match.chat_id): match for match in matches}
    if not unique:
        raise AvatarUpdateError("group is not present in the configured roster")
    if len(unique) != 1:
        raise AvatarUpdateError("group name or alias is ambiguous; use the exact chat ID")
    return next(iter(unique.values()))


def _allowed_image_roots(home: Path) -> tuple[Path, ...]:
    return tuple(path.resolve(strict=False) for path in (home / "cache" / "images", home / "image_cache", home / "tmp"))


def _validate_image(raw_path: str, *, allowed_roots: tuple[Path, ...] = ()) -> ImageInfo:
    unresolved = Path(raw_path).expanduser()
    if unresolved.is_symlink():
        raise AvatarUpdateError("avatar image must not be a symbolic link")
    try:
        path = unresolved.resolve(strict=True)
    except OSError as exc:
        raise AvatarUpdateError("avatar image does not exist") from exc
    if not path.is_file():
        raise AvatarUpdateError("avatar image must be a regular file")
    if allowed_roots and not any(path.is_relative_to(root) for root in allowed_roots):
        raise AvatarUpdateError("avatar image is outside the trusted Hermes media workspaces")
    size_bytes = path.stat().st_size
    if size_bytes <= 0 or size_bytes > MAX_AVATAR_BYTES:
        raise AvatarUpdateError("avatar image must be non-empty and no larger than 10 MiB")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image_format = str(image.format or "").upper()
                width, height = image.size
                frames = int(getattr(image, "n_frames", 1))
                image.verify()
    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise AvatarUpdateError("avatar image is invalid or unsafe to decode") from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_FORMATS))
        raise AvatarUpdateError(f"avatar image format must be one of: {allowed}")
    if frames != 1:
        raise AvatarUpdateError("animated images are not accepted as group avatars")
    if width <= 0 or height <= 0 or width > MAX_AVATAR_SIDE or height > MAX_AVATAR_SIDE:
        raise AvatarUpdateError("avatar image dimensions must be at most 4096 x 4096")
    return ImageInfo(
        path=path,
        format=image_format,
        width=width,
        height=height,
        size_bytes=size_bytes,
    )


def _credentials(env_file: Path) -> tuple[str, str]:
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if app_id or app_secret:
        if not app_id or not app_secret:
            raise AvatarUpdateError("FEISHU_APP_ID and FEISHU_APP_SECRET must be configured together")
        return app_id, app_secret

    values = dotenv_values(env_file) if env_file.is_file() else {}
    app_id = str(values.get("FEISHU_APP_ID") or "").strip()
    app_secret = str(values.get("FEISHU_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        raise AvatarUpdateError("FEISHU_APP_ID and FEISHU_APP_SECRET must be configured together")
    return app_id, app_secret


def _build_client(env_file: Path) -> Any:
    app_id, app_secret = _credentials(env_file)
    return Client.builder().app_id(app_id).app_secret(app_secret).timeout(30).log_level(LogLevel.ERROR).build()


def _check_response(response: Any, operation: str) -> Any:
    if response is None or not callable(getattr(response, "success", None)) or not response.success():
        code = getattr(response, "code", None)
        message = _clean_text(getattr(response, "msg", None)) or "unknown error"
        raise AvatarUpdateError(f"Feishu {operation} failed (code={code}, message={message})")
    return response


def _get_chat(client: Any, target: GroupTarget) -> Any:
    request = GetChatRequest.builder().chat_id(target.chat_id).build()
    response = _check_response(client.im.v1.chat.get(request), "group readback")
    if response.data is None:
        raise AvatarUpdateError("Feishu group readback returned no data")
    remote_name = _clean_text(response.data.name, limit=160)
    if remote_name and remote_name != target.name:
        raise AvatarUpdateError(
            "configured group name no longer matches Feishu; update groups.yaml before changing the avatar"
        )
    return response.data


def _update_avatar(client: Any, target: GroupTarget, image: ImageInfo) -> dict[str, object]:
    before = _get_chat(client, target)
    with image.path.open("rb") as image_file:
        upload_body = CreateImageRequestBody.builder().image_type("avatar").image(image_file).build()
        upload_request = CreateImageRequest.builder().request_body(upload_body).build()
        upload_response = _check_response(client.im.v1.image.create(upload_request), "avatar upload")
    image_key = _clean_text(getattr(upload_response.data, "image_key", None), limit=256)
    if not image_key:
        raise AvatarUpdateError("Feishu avatar upload returned no image key")

    update_body = UpdateChatRequestBody.builder().avatar(image_key).build()
    update_request = UpdateChatRequest.builder().chat_id(target.chat_id).request_body(update_body).build()
    _check_response(client.im.v1.chat.update(update_request), "group avatar update")
    after = _get_chat(client, target)
    after_avatar = _clean_text(getattr(after, "avatar", None), limit=1024)
    if not after_avatar:
        raise AvatarUpdateError("Feishu accepted the update but avatar readback is empty")
    before_avatar = _clean_text(getattr(before, "avatar", None), limit=1024)
    return {
        "success": True,
        "group": target.name,
        "format": image.format,
        "width": image.width,
        "height": image.height,
        "size_bytes": image.size_bytes,
        "readback_present": True,
        "readback_changed": before_avatar != after_avatar,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", required=True, help="Exact configured group name, alias, or chat ID")
    parser.add_argument("--image", required=True, help="Local PNG, JPEG, or WebP avatar image")
    parser.add_argument(
        "--confirm-chat-id",
        help="Required for mutation; must exactly match the configured target chat ID",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate target and image without reading credentials or contacting Feishu",
    )
    return parser


def run(argv: list[str] | None = None, *, client: Any | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    home = _hermes_home()
    target = _resolve_group(args.group, home / "groups.yaml")
    image = _validate_image(args.image, allowed_roots=_allowed_image_roots(home))
    if args.dry_run:
        return {
            "success": True,
            "dry_run": True,
            "group": target.name,
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "size_bytes": image.size_bytes,
        }
    if args.confirm_chat_id != target.chat_id:
        raise AvatarUpdateError("refusing mutation: --confirm-chat-id must match the configured group")
    api_client = client or _build_client(home / ".env")
    return _update_avatar(api_client, target, image)


def main() -> int:
    try:
        print(json.dumps(run(), ensure_ascii=False))
        return 0
    except AvatarUpdateError as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:  # noqa: BLE001 - keep SDK/network details bounded and secret-free
        error_type = type(exc).__name__
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"group avatar update failed ({error_type})",
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
