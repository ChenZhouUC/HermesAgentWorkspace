"""One entry point: read any Feishu URL and print its content as text/markdown.

Detects the object type from the URL and routes to the right reader:

  /docx/ , /docs/   -> document blocks -> markdown
  /wiki/            -> resolve wiki node -> recurse on the real object
  /sheets/          -> read_sheet  (电子表格)
  /base/            -> read_bitable (多维表格)
  /file/            -> download_feishu_file, then read_file extracts it

Run with the venv interpreter so feishu_common's deps resolve:
  ~/.hermes/hermes-agent/venv/bin/python read_feishu_url.py <feishu_url>

NOTE: docx-embedded tables/images render as placeholders (a known limitation of
the block extractor). Standalone 电子表格/多维表格 render as full markdown tables.
"""

import os
import sys
from pathlib import Path

import feishu_common as fc

_KINDS = ("docx", "docs", "wiki", "sheets", "base", "file")
_MAX_EXTRACTED_CHARS = 40_000
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
