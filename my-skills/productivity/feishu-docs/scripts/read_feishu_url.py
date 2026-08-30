"""One entry point: read any Feishu URL and print its content as text/markdown.

Detects the object type from the URL and routes to the right reader:

  /docx/ , /docs/   -> document blocks -> markdown
  /wiki/            -> resolve wiki node -> recurse on the real object
  /sheets/          -> read_sheet  (电子表格)
  /base/            -> read_bitable (多维表格)
  /file/            -> download_feishu_file, then read_file extracts it

Run with the venv interpreter so feishu_common's deps resolve:
  ~/.hermes/hermes-agent/venv/bin/python read_feishu_url.py <feishu_url>

NOTE: docx tables render as placeholders. Image bodies are not rendered, but
known Feishu remote-import error images are detected and reported with block IDs.
Standalone 电子表格/多维表格 render as full markdown tables.
"""

import os
import hashlib
import sys
import urllib.request
from pathlib import Path

import feishu_common as fc

_KINDS = ("docx", "docs", "wiki", "sheets", "base", "file")
_MAX_EXTRACTED_CHARS = 40_000
_IMPORT_ERROR_IMAGE_SHA256 = "c1263eb516bd6c4b27772fd159fd3f3a38ff8dbf5df04c7c3f97e2afd4b909cc"
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


def read_docx(doc_token):
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


def read_url(url):
    url = (url or "").strip()
    kind = detect_kind(url)
    if kind in ("docx", "docs"):
        return read_docx(_token_after(url, kind))
    if kind == "wiki":
        obj_type, obj_token = resolve_wiki(_token_after(url, "wiki"))
        if not obj_token:
            return f"(无法解析 wiki 节点: {url})"
        if obj_type in ("docx", "doc"):
            return read_docx(obj_token)
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
    if len(sys.argv) < 2:
        print("Usage: python read_feishu_url.py <feishu_url>")
        sys.exit(1)
    print(read_url(sys.argv[1]))
