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

import sys

import feishu_common as fc

_KINDS = ("docx", "docs", "wiki", "sheets", "base", "file")


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
        return f'文件已下载到: {path}\n用 read_file 抽取内容(.docx/.xlsx 自动转文本): read_file("{path}")'
    return f"(无法识别的飞书链接类型: {url}\n支持: /docx /docs /wiki /sheets /base /file)"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_feishu_url.py <feishu_url>")
        sys.exit(1)
    print(read_url(sys.argv[1]))
