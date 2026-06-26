"""Read a Feishu Spreadsheet (电子表格) and print it as markdown tables.

Links look like ``https://domain.feishu.cn/sheets/TOKEN``. Neither feishu_doc_read
nor the docx extraction scripts work on sheet tokens (they return 1770002). This
uses the documented sheets API (see references/sheet-api.md):

  1. /sheets/v3/spreadsheets/{token}/sheets/query  -> list worksheets
  2. /sheets/v2/spreadsheets/{token}/values/{id}!RANGE -> cell values

Usage:
  python read_sheet.py <sheet_url_or_token> [range]   # default range A1:Z300
"""

import sys

import feishu_common as fc
from feishu_render import flatten_cell, md_table

DEFAULT_RANGE = "A1:Z300"


def extract_sheet_token(url_or_token):
    s = (url_or_token or "").strip()
    if "/sheets/" in s:
        s = s.split("/sheets/", 1)[1]
    return s.split("?", 1)[0].split("#", 1)[0].strip("/")


def list_sheets(token, sheet_token):
    resp = fc.do_req(token, f"{fc.API}/sheets/v3/spreadsheets/{sheet_token}/sheets/query")
    fc._check(resp, "sheets query")
    return resp.get("data", {}).get("sheets", []) or []


def read_values(token, sheet_token, sheet_id, rng=DEFAULT_RANGE):
    # %21 == '!' — the range is "<sheet_id>!A1:Z300".
    url = f"{fc.API}/sheets/v2/spreadsheets/{sheet_token}/values/{sheet_id}%21{rng}"
    resp = fc.do_req(token, url)
    fc._check(resp, "sheet values")
    return resp.get("data", {}).get("valueRange", {}).get("values", []) or []


def _trim_trailing_empty(values):
    rows = [[flatten_cell(c) for c in row] for row in values]
    while rows and not any(c.strip() for c in rows[-1]):
        rows.pop()
    return rows


def read_sheet(url_or_token, rng=DEFAULT_RANGE):
    sheet_token = extract_sheet_token(url_or_token)
    token = fc.get_tenant_token()
    sheets = list_sheets(token, sheet_token)
    if not sheets:
        return f"(电子表格 {sheet_token} 没有可读工作表)"
    out = [f"# Feishu Sheet `{sheet_token}` — {len(sheets)} 个工作表"]
    for s in sheets:
        sid = s.get("sheet_id")
        title = s.get("title") or sid
        try:
            values = read_values(token, sheet_token, sid, rng)
        except Exception as e:  # one bad sheet shouldn't kill the rest
            out.append(f"## {title}\n\n(读取失败: {e})")
            continue
        rows = _trim_trailing_empty(values)
        if not rows:
            out.append(f"## {title}\n\n(空)")
            continue
        headers, body = rows[0], rows[1:]
        out.append(f"## {title}  ({len(body)} 行)\n\n" + md_table(headers, body))
    return "\n\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_sheet.py <sheet_url_or_token> [range]")
        sys.exit(1)
    rng = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_RANGE
    print(read_sheet(sys.argv[1], rng))
