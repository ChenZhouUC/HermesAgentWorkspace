#!/usr/bin/env python3
"""Insert a raster image into a Feishu docx document or set its cover.

The caller supplies a local image path that has already passed the surrounding
workspace/attachment provenance checks. This script still validates the file
again, uploads it as document-scoped media, performs the document mutation, and
appends the standard version-table row.

Usage:
  manage_doc_image.py insert <doc_token> <image_path> [options]
  manage_doc_image.py cover  <doc_token> <image_path> [options]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_common as fc


MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALIGNMENTS = {"left": 1, "center": 2, "right": 3}
TEXT_BLOCK_KEYS = (
    "text",
    "heading1",
    "heading2",
    "heading3",
    "heading4",
    "heading5",
    "heading6",
    "heading7",
    "heading8",
    "heading9",
    "bullet",
    "ordered",
    "quote",
    "todo",
)
DOC_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{5,200}$")


def _max_image_bytes() -> int:
    raw = os.environ.get("HERMES_FEISHU_IMAGE_MAX_BYTES", str(MAX_IMAGE_BYTES))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = MAX_IMAGE_BYTES
    return max(1_000_000, min(MAX_IMAGE_BYTES, value))


def _image_mime(path: Path) -> str:
    with path.open("rb") as handle:
        prefix = handle.read(16)
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "image/webp"
    if prefix.startswith(b"BM"):
        return "image/bmp"
    if prefix.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    raise ValueError("image must be PNG, JPEG, GIF, WebP, BMP, or TIFF")


def validate_image_path(value: str) -> tuple[Path, str, int]:
    raw = Path(value).expanduser()
    if raw.is_symlink():
        raise ValueError("symbolic-link image inputs are not allowed")
    try:
        path = raw.resolve(strict=True)
    except OSError:
        raise ValueError("image source is not available") from None
    if not path.is_file():
        raise ValueError("image path must name a regular file")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("image file is empty")
    limit = _max_image_bytes()
    if size > limit:
        raise ValueError(f"image exceeds the {limit}-byte Feishu upload limit")
    return path, _image_mime(path), size


def _complete_image_dimensions(
    path: Path,
    width: int | None,
    height: int | None,
) -> tuple[int | None, int | None]:
    """Derive one omitted display dimension without distorting the source."""
    if (width is None) == (height is None):
        return width, height
    try:
        with Image.open(path) as source:
            source_width, source_height = source.size
    except (OSError, UnidentifiedImageError):
        raise ValueError("image dimensions could not be read") from None
    if source_width <= 0 or source_height <= 0:
        raise ValueError("image dimensions must be positive")
    if width is not None:
        height = max(1, round(width * source_height / source_width))
        if height > 20_000:
            raise ValueError("derived height exceeds the 20000-pixel Feishu limit")
    else:
        assert height is not None
        width = max(1, round(height * source_width / source_height))
        if width > 20_000:
            raise ValueError("derived width exceeds the 20000-pixel Feishu limit")
    return width, height


def validate_doc_token(value: str) -> str:
    token = str(value or "").strip()
    if not DOC_TOKEN_RE.fullmatch(token):
        raise ValueError("invalid Feishu document token")
    return token


def _curl_json(command: list[str], context: str) -> dict[str, Any]:
    retryable_codes = {1061001, 1061006, 1061045, 99991400}
    last_error = "unknown failure"
    for attempt in range(5):
        try:
            result = subprocess.run(command, capture_output=True, check=False, timeout=120)
        except subprocess.TimeoutExpired:
            last_error = "timed out"
            if attempt < 4:
                fc._backoff(attempt)
                continue
            break
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip()
            last_error = f"failed (exit {result.returncode}): {detail[:300]}"
            if attempt < 4:
                fc._backoff(attempt)
                continue
            break
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"{context} returned invalid JSON") from None
        if payload.get("code") in retryable_codes and attempt < 4:
            last_error = f"retryable Feishu error code={payload.get('code')} msg={payload.get('msg')!r}"
            fc._backoff(attempt)
            continue
        return fc._check(payload, context)
    raise RuntimeError(f"{context} {last_error}") from None


def upload_doc_image(token: str, image_path: str, *, parent_node: str, doc_token: str) -> str:
    path, _mime, size = validate_image_path(image_path)
    safe_name = path.name.replace("\r", "_").replace("\n", "_").replace('"', "_")[:250] or "image"
    response = _curl_json(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            f"{fc.API}/drive/v1/medias/upload_all",
            "-H",
            f"Authorization: Bearer {token}",
            "-F",
            f"file=@{path}",
            "--form-string",
            f"file_name={safe_name}",
            "--form-string",
            "parent_type=docx_image",
            "--form-string",
            f"parent_node={parent_node}",
            "--form-string",
            f"size={size}",
            "--form-string",
            f"extra={json.dumps({'drive_route_token': doc_token}, separators=(',', ':'))}",
        ],
        "upload document image",
    )
    try:
        return response["data"]["file_token"]
    except (KeyError, TypeError):
        raise RuntimeError("upload document image response is missing file_token") from None


def _block_text(block: dict[str, Any]) -> str:
    for key in TEXT_BLOCK_KEYS:
        body = block.get(key)
        if not isinstance(body, dict):
            continue
        parts = []
        for element in body.get("elements", []):
            if not isinstance(element, dict):
                continue
            if isinstance(element.get("text_run"), dict):
                parts.append(str(element["text_run"].get("content") or ""))
            elif isinstance(element.get("mention_user"), dict):
                parts.append("@")
            elif isinstance(element.get("mention_doc"), dict):
                parts.append(str(element["mention_doc"].get("title") or ""))
        return "".join(parts).strip()
    return ""


def resolve_insert_index(
    root: dict[str, Any],
    block_map: dict[str, dict[str, Any]],
    *,
    version_table_count: int,
    insert_index: int | None,
    position: str,
    anchor_text: str | None,
) -> int:
    children = list(root.get("children", []))
    if insert_index is not None:
        if anchor_text:
            raise ValueError("insert_index cannot be combined with anchor_text")
        if insert_index < version_table_count:
            raise ValueError("insert_index cannot precede the document version table")
        if insert_index > len(children):
            raise ValueError("insert_index is beyond the document child count")
        return insert_index

    if position == "end":
        if anchor_text:
            raise ValueError("anchor_text requires position=before or position=after")
        return len(children)
    if position not in {"before", "after"} or not anchor_text:
        raise ValueError("position=before/after requires a non-empty anchor_text")

    needle = " ".join(anchor_text.split()).casefold()
    exact: list[int] = []
    partial: list[int] = []
    for index, block_id in enumerate(children):
        content = " ".join(_block_text(block_map.get(block_id, {})).split()).casefold()
        if not content:
            continue
        if content == needle:
            exact.append(index)
        elif needle in content:
            partial.append(index)
    matches = exact or partial
    if not matches:
        raise ValueError(f"anchor_text was not found in a top-level text block: {anchor_text!r}")
    if len(matches) != 1:
        raise ValueError(f"anchor_text matched multiple top-level blocks: {anchor_text!r}")
    index = matches[0] + (1 if position == "after" else 0)
    if index < version_table_count:
        raise ValueError("image placement cannot precede the document version table")
    return index


def _delete_top_level_block(token: str, doc_token: str, block_id: str) -> None:
    root = fc.do_req(token, f"{fc.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}")["data"]["block"]
    children = list(root.get("children", []))
    if block_id not in children:
        return
    index = children.index(block_id)
    fc.do_req(
        token,
        f"{fc.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
        method="DELETE",
        payload={"start_index": index, "end_index": index + 1},
    )


def _restore_version_rows(
    token: str,
    doc_token: str,
    rows: list[list[list[dict[str, Any]]]] | None,
    original_top_level_ids: set[str],
) -> None:
    root, block_map = fc._load_blocks(token, doc_token)
    leading_new_tables = 0
    for block_id in root.get("children", []):
        if block_id in original_top_level_ids:
            break
        block = block_map.get(block_id)
        if not block or block.get("block_type") != 31:
            break
        leading_new_tables += 1
    if leading_new_tables:
        fc.do_req(
            token,
            f"{fc.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": leading_new_tables},
        )
    if rows:
        fc._write_version_tables(token, doc_token, rows, insert_index=0)


def _rollback_error(original: BaseException, failures: list[str]) -> RuntimeError:
    detail = f"{type(original).__name__}: {original}"
    if failures:
        detail += "; rollback failures: " + "; ".join(failures)
    return RuntimeError(detail)


def insert_image(
    token: str,
    doc_token: str,
    image_path: str,
    *,
    insert_index: int | None = None,
    position: str = "end",
    anchor_text: str | None = None,
    align: str = "center",
    caption: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    doc_token = validate_doc_token(doc_token)
    image, _mime, _size = validate_image_path(image_path)
    if align not in ALIGNMENTS:
        raise ValueError("align must be left, center, or right")
    if caption is not None and (len(caption) > 1_000 or "\x00" in caption):
        raise ValueError("caption must contain at most 1000 characters")
    for name, value in (("width", width), ("height", height)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 20_000):
            raise ValueError(f"{name} must be an integer between 1 and 20000")
    width, height = _complete_image_dimensions(image, width, height)
    rows, version_table_count, block_map, root = fc.read_version_tables(token, doc_token)
    original_top_level_ids = set(root.get("children", []))
    target_index = resolve_insert_index(
        root,
        block_map,
        version_table_count=version_table_count,
        insert_index=insert_index,
        position=position,
        anchor_text=anchor_text,
    )

    image_block_id: str | None = None
    version_started = False
    try:
        created = fc._check(
            fc.do_req(
                token,
                f"{fc.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
                method="POST",
                payload={"children": [{"block_type": 27, "image": {}}], "index": target_index},
            ),
            "create image block",
        )
        image_block_id = created["data"]["children"][0]["block_id"]
        file_token = upload_doc_image(
            token,
            image_path,
            parent_node=image_block_id,
            doc_token=doc_token,
        )
        replacement: dict[str, Any] = {"token": file_token, "align": ALIGNMENTS[align]}
        if caption:
            replacement["caption"] = {"content": caption}
        if width is not None:
            replacement["width"] = width
        if height is not None:
            replacement["height"] = height
        fc._check(
            fc.do_req(
                token,
                f"{fc.API}/docx/v1/documents/{doc_token}/blocks/{image_block_id}",
                method="PATCH",
                payload={"replace_image": replacement},
            ),
            "replace image block",
        )
        version_started = True
        version = fc.append_version_row(token, doc_token)
        return {
            "document_id": doc_token,
            "block_id": image_block_id,
            "file_token": file_token,
            "insert_index": target_index,
            "width": width,
            "height": height,
            "version": version,
        }
    except BaseException as exc:
        failures = []
        if version_started:
            try:
                _restore_version_rows(token, doc_token, rows, original_top_level_ids)
            except Exception as rollback_exc:
                failures.append(f"version table: {rollback_exc}")
        if image_block_id:
            try:
                _delete_top_level_block(token, doc_token, image_block_id)
            except Exception as rollback_exc:
                failures.append(f"image block: {rollback_exc}")
        raise _rollback_error(exc, failures) from None


def _get_cover(token: str, doc_token: str) -> dict[str, Any] | None:
    data = fc._check(
        fc.do_req(token, f"{fc.API}/docx/v1/documents/{doc_token}"),
        "read document cover",
    ).get("data", {})
    cover = (data.get("document") or {}).get("cover") or data.get("cover")
    if not isinstance(cover, dict) or not cover.get("token"):
        return None
    return {key: cover[key] for key in ("token", "offset_ratio_x", "offset_ratio_y") if cover.get(key) is not None}


def _patch_cover(token: str, doc_token: str, cover: dict[str, Any] | None) -> None:
    fc._check(
        fc.do_req(
            token,
            f"{fc.API}/docx/v1/documents/{doc_token}",
            method="PATCH",
            payload={"update_cover": {"cover": cover}},
        ),
        "update document cover",
    )


def set_cover(
    token: str,
    doc_token: str,
    image_path: str,
    *,
    offset_ratio_x: float | None = None,
    offset_ratio_y: float | None = None,
) -> dict[str, Any]:
    doc_token = validate_doc_token(doc_token)
    validate_image_path(image_path)
    for name, value in (("offset_ratio_x", offset_ratio_x), ("offset_ratio_y", offset_ratio_y)):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
        ):
            raise ValueError(f"{name} must be a finite number")
    old_cover = _get_cover(token, doc_token)
    rows, _table_count, _block_map, root = fc.read_version_tables(token, doc_token)
    original_top_level_ids = set(root.get("children", []))
    cover_changed = False
    version_started = False
    try:
        file_token = upload_doc_image(
            token,
            image_path,
            parent_node=doc_token,
            doc_token=doc_token,
        )
        cover: dict[str, Any] = {"token": file_token}
        if offset_ratio_x is not None:
            cover["offset_ratio_x"] = offset_ratio_x
        if offset_ratio_y is not None:
            cover["offset_ratio_y"] = offset_ratio_y
        _patch_cover(token, doc_token, cover)
        cover_changed = True
        version_started = True
        version = fc.append_version_row(token, doc_token)
        return {
            "document_id": doc_token,
            "file_token": file_token,
            "cover": cover,
            "version": version,
        }
    except BaseException as exc:
        failures = []
        if cover_changed:
            try:
                _patch_cover(token, doc_token, old_cover)
            except Exception as rollback_exc:
                failures.append(f"cover: {rollback_exc}")
        if version_started:
            try:
                _restore_version_rows(token, doc_token, rows, original_top_level_ids)
            except Exception as rollback_exc:
                failures.append(f"version table: {rollback_exc}")
        raise _rollback_error(exc, failures) from None


def _positive_size(value: str) -> int:
    parsed = int(value)
    if parsed <= 0 or parsed > 20_000:
        raise argparse.ArgumentTypeError("value must be between 1 and 20000")
    return parsed


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be finite")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)

    insert = subparsers.add_parser("insert")
    insert.add_argument("doc_token")
    insert.add_argument("image_path")
    insert.add_argument("--insert-index", type=int)
    insert.add_argument("--position", choices=("end", "before", "after"), default="end")
    insert.add_argument("--anchor-text")
    insert.add_argument("--align", choices=tuple(ALIGNMENTS), default="center")
    insert.add_argument("--caption")
    insert.add_argument("--width", type=_positive_size)
    insert.add_argument("--height", type=_positive_size)

    cover = subparsers.add_parser("cover")
    cover.add_argument("doc_token")
    cover.add_argument("image_path")
    cover.add_argument("--offset-ratio-x", type=_finite_float)
    cover.add_argument("--offset-ratio-y", type=_finite_float)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        token = fc.get_tenant_token()
        if args.operation == "insert":
            result = insert_image(
                token,
                args.doc_token,
                args.image_path,
                insert_index=args.insert_index,
                position=args.position,
                anchor_text=args.anchor_text,
                align=args.align,
                caption=args.caption,
                width=args.width,
                height=args.height,
            )
        else:
            result = set_cover(
                token,
                args.doc_token,
                args.image_path,
                offset_ratio_x=args.offset_ratio_x,
                offset_ratio_y=args.offset_ratio_y,
            )
    except Exception as exc:
        print(f"Feishu document image operation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"success": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
