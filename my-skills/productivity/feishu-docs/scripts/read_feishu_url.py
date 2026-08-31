"""One entry point: read any Feishu URL and print its content as text/markdown.

Detects the object type from the URL and routes to the right reader:

  /docx/ , /docs/   -> document blocks -> markdown
  /wiki/            -> resolve wiki node -> recurse on the real object
  /sheets/          -> read_sheet  (电子表格)
  /base/            -> read_bitable (多维表格)
  /file/            -> download_feishu_file, then read_file extracts it

Run with the venv interpreter so feishu_common's deps resolve:
  ~/.hermes/hermes-agent/venv/bin/python read_feishu_url.py <feishu_url>

NOTE: docx tables render as placeholders. Pass ``--include-images`` to download
embedded raster images into the current Feishu group workspace and append a
machine-readable ``[DOCUMENT_IMAGES]`` manifest with relative ``image_path``
values. Without that flag, image bodies are not rendered, but known Feishu
remote-import error images are still detected and reported with block IDs.
Standalone 电子表格/多维表格 render as full markdown tables.
"""

import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import feishu_common as fc

_KINDS = ("docx", "docs", "wiki", "sheets", "base", "file")
_MAX_EXTRACTED_CHARS = 40_000
_IMPORT_ERROR_IMAGE_SHA256 = "c1263eb516bd6c4b27772fd159fd3f3a38ff8dbf5df04c7c3f97e2afd4b909cc"
_DEFAULT_DOC_IMAGE_LIMIT = 12
_DEFAULT_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_DEFAULT_TOTAL_IMAGE_BYTES = 50_000_000
_PLAIN_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".log",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".py",
    ".sh",
    ".ts",
}


def detect_kind(url):
    for kind in _KINDS:
        if f"/{kind}/" in url:
            return kind
    return None


def _token_after(url, kind):
    return url.split(f"/{kind}/", 1)[1].split("?", 1)[0].split("#", 1)[0].strip("/")


def _download_doc_image(token, media_token, max_bytes=1_000_000):
    req = urllib.request.Request(
        f"{fc.API}/drive/v1/medias/{media_token}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("document image exceeds verification limit")
    return data


def _bounded_env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe_component(value, fallback):
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", str(value or ""))[:120].strip("_")
    return cleaned or fallback


def _image_suffix(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tiff"
    return ""


def read_doc_cover(token, doc_token):
    data = fc._check(
        fc.do_req(token, f"{fc.API}/docx/v1/documents/{doc_token}"),
        "read document cover",
    ).get("data", {})
    cover = (data.get("document") or {}).get("cover") or data.get("cover")
    if not isinstance(cover, dict) or not cover.get("token"):
        return None
    return {
        "block_id": "document-cover",
        "block_type": 27,
        "asset_role": "cover",
        "image": {
            "token": cover["token"],
            "width": cover.get("width"),
            "height": cover.get("height"),
        },
    }


def export_doc_images(
    access_token,
    doc_token,
    blocks,
    workspace,
    *,
    max_images=_DEFAULT_DOC_IMAGE_LIMIT,
    max_bytes=_DEFAULT_IMAGE_MAX_BYTES,
    max_total_bytes=_DEFAULT_TOTAL_IMAGE_BYTES,
):
    """Download docx image blocks into a bounded group-workspace bundle."""
    workspace = Path(workspace).expanduser().resolve(strict=False)
    target_dir = workspace / "feishu-doc-images" / _safe_component(doc_token, "document")
    if target_dir.exists() and target_dir.is_symlink():
        raise ValueError("document image directory must not be a symlink")
    target_dir.mkdir(parents=True, exist_ok=True)

    image_blocks = [
        block
        for block in blocks
        if isinstance(block, dict)
        and block.get("block_type") == 27
        and isinstance(block.get("image"), dict)
        and block["image"].get("token")
    ]
    selected = image_blocks[:max_images]
    result = {"images": [], "errors": [], "truncated": max(0, len(image_blocks) - len(selected))}
    total_bytes = 0
    for index, block in enumerate(selected, 1):
        image = block["image"]
        block_id = str(block.get("block_id") or f"image-{index}")
        try:
            data = _download_doc_image(access_token, image["token"], max_bytes)
        except Exception as exc:
            result["errors"].append({"block_id": block_id, "error": type(exc).__name__})
            continue
        if (
            image.get("width") == 1460
            and image.get("height") == 220
            and hashlib.sha256(data).hexdigest() == _IMPORT_ERROR_IMAGE_SHA256
        ):
            result["errors"].append({"block_id": block_id, "error": "feishu_import_placeholder"})
            continue
        suffix = _image_suffix(data)
        if not suffix:
            result["errors"].append({"block_id": block_id, "error": "unsupported_raster_format"})
            continue
        if total_bytes + len(data) > max_total_bytes:
            result["errors"].append({"block_id": block_id, "error": "total_image_bytes_exceeded"})
            result["truncated"] += len(selected) - index
            break
        filename = f"{index:02d}-{_safe_component(block_id, f'image-{index}')}{suffix}"
        destination = target_dir / filename
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            raise ValueError("document image destination must be a regular file")
        destination.write_bytes(data)
        total_bytes += len(data)
        result["images"].append(
            {
                "block_id": block_id,
                "role": block.get("asset_role") or "body",
                "image_path": destination.relative_to(workspace).as_posix(),
                "width": image.get("width"),
                "height": image.get("height"),
                "size_bytes": len(data),
            }
        )
    return result


def detect_import_error_images(token, blocks):
    """Return image block IDs containing Feishu's remote-import failure asset."""
    failures = []
    for block in blocks:
        image = block.get("image") if isinstance(block, dict) else None
        if not isinstance(image, dict) or block.get("block_type") != 27:
            continue
        if image.get("width") != 1460 or image.get("height") != 220 or not image.get("token"):
            continue
        try:
            data = _download_doc_image(token, image["token"])
        except Exception:
            continue
        if hashlib.sha256(data).hexdigest() == _IMPORT_ERROR_IMAGE_SHA256:
            failures.append(str(block.get("block_id") or "unknown"))
    return failures


def read_docx(doc_token, *, include_images=False):
    token = fc.get_tenant_token()
    blocks, page_token = [], ""
    while True:
        url = f"{fc.API}/docx/v1/documents/{doc_token}/blocks?page_size=500"
        if page_token:
            url += f"&page_token={page_token}"
        resp = fc.do_req(token, url)
        fc._check(resp, "docx blocks")
        data = resp.get("data", {})
        blocks.extend(data.get("items", []) or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
    from read_docx_to_markdown import parse_blocks  # pure renderer, reused

    _title, md = parse_blocks(blocks)
    if include_images:
        workspace = os.environ.get("HERMES_GROUP_WORKSPACE", "").strip()
        if not workspace:
            image_result = {
                "images": [],
                "errors": [{"block_id": "", "error": "group_workspace_unavailable"}],
                "truncated": 0,
            }
        else:
            cover = read_doc_cover(token, doc_token)
            image_result = export_doc_images(
                token,
                doc_token,
                ([cover] if cover else []) + blocks,
                workspace,
                max_images=_bounded_env_int(
                    "HERMES_FEISHU_DOC_READ_MAX_IMAGES",
                    _DEFAULT_DOC_IMAGE_LIMIT,
                    1,
                    20,
                ),
                max_bytes=_bounded_env_int(
                    "HERMES_FEISHU_IMAGE_MAX_BYTES",
                    _DEFAULT_IMAGE_MAX_BYTES,
                    1_000_000,
                    100_000_000,
                ),
                max_total_bytes=_bounded_env_int(
                    "HERMES_GROUP_MAX_DOWNLOAD_BYTES",
                    _DEFAULT_TOTAL_IMAGE_BYTES,
                    1_000_000,
                    500_000_000,
                ),
            )
        md += "\n\n[DOCUMENT_IMAGES]\n" + json.dumps(image_result, ensure_ascii=False)
    else:
        failures = detect_import_error_images(token, blocks)
        if failures:
            md += (
                "\n\n[IMAGE_IMPORT_ERRORS] Feishu replaced remote Markdown images with its import-error "
                f"placeholder in {len(failures)} block(s): {', '.join(failures)}. "
                "Do not report visual verification as successful; stage the source images locally and replace these blocks."
            )
    return md


def resolve_wiki(wiki_token):
    """Resolve a wiki node to (obj_type, obj_token). obj_type ∈ docx/doc/sheet/bitable/..."""
    token = fc.get_tenant_token()
    resp = fc.do_req(token, f"{fc.API}/wiki/v2/spaces/get_node?token={wiki_token}")
    fc._check(resp, "wiki get_node")
    node = resp.get("data", {}).get("node", {})
    return node.get("obj_type"), node.get("obj_token")


def _bounded_text(text, max_chars=_MAX_EXTRACTED_CHARS):
    if len(text) <= max_chars:
        return text
    marker = "\n\n[... 文件内容过长，已截断；原文件路径见上方 ...]\n\n"
    remaining = max_chars - len(marker)
    head = max(0, remaining * 3 // 4)
    return text[:head].rstrip() + marker + text[-(remaining - head) :].lstrip()


def _read_downloaded_file(path):
    """Extract a downloaded Drive file without relying on agent terminal tools."""
    path = str(path)
    repo = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "hermes-agent"
    if repo.is_dir() and str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    ext = Path(path).suffix.lower()
    if ext in _PLAIN_TEXT_EXTENSIONS:
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        return _bounded_text(content)

    try:
        from tools.read_extract import ExtractionError, extract_document_text, is_extractable_document
    except ImportError as exc:
        return f"(文件已下载，但通用文档解析器不可用: {exc})"

    if not is_extractable_document(path):
        return f"(文件已下载；类型 {ext or '未知'} 暂无文本抽取器。图片/视频链接应由飞书网关原生媒体链路读取。)"
    try:
        return _bounded_text(extract_document_text(path))
    except ExtractionError as exc:
        return f"(文件已下载，但无法抽取文本: {exc})"


def read_url(url, *, include_images=False):
    url = (url or "").strip()
    kind = detect_kind(url)
    if kind in ("docx", "docs"):
        return read_docx(_token_after(url, kind), include_images=include_images)
    if kind == "wiki":
        obj_type, obj_token = resolve_wiki(_token_after(url, "wiki"))
        if not obj_token:
            return f"(无法解析 wiki 节点: {url})"
        if obj_type in ("docx", "doc"):
            return read_docx(obj_token, include_images=include_images)
        if obj_type in ("sheet", "sheets"):
            from read_sheet import read_sheet

            return read_sheet(obj_token)
        if obj_type in ("bitable", "base"):
            from read_bitable import read_bitable

            return read_bitable(obj_token)
        return f"(wiki 节点指向暂不支持的类型 obj_type={obj_type}, token={obj_token})"
    if kind == "sheets":
        from read_sheet import read_sheet

        return read_sheet(url)
    if kind == "base":
        from read_bitable import read_bitable

        return read_bitable(url)
    if kind == "file":
        from download_feishu_file import download_file

        path = download_file(url)
        content = _read_downloaded_file(path)
        return f"文件已下载到: {path}\n\n{content}"
    return f"(无法识别的飞书链接类型: {url}\n支持: /docx /docs /wiki /sheets /base /file)"


if __name__ == "__main__":
    positional = [arg for arg in sys.argv[1:] if arg != "--include-images"]
    if len(positional) != 1:
        print("Usage: python read_feishu_url.py <feishu_url> [--include-images]")
        sys.exit(1)
    print(read_url(positional[0], include_images="--include-images" in sys.argv[1:]))
