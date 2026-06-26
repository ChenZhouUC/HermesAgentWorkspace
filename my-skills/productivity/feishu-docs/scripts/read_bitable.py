"""Read a Feishu Bitable / 多维表格 (base) and print its tables as markdown.

Links look like ``https://domain.feishu.cn/base/APP_TOKEN?table=TABLE_ID&view=...``.
Uses the bitable API:

  /bitable/v1/apps/{app_token}/tables              -> list data tables
  /bitable/v1/apps/{app_token}/tables/{id}/records -> rows (paginated)

Usage:
  python read_bitable.py <base_url_or_app_token> [table_id] [max_records]
"""

import sys
from urllib.parse import parse_qs, urlparse

import feishu_common as fc
from feishu_render import flatten_field, md_table

DEFAULT_MAX_RECORDS = 200


def extract_base(url_or_token):
    """Return (app_token, table_id_or_None) from a /base/ URL or a bare app_token."""
    s = (url_or_token or "").strip()
    app_token, table_id = s, None
    if "/base/" in s:
        rest = s.split("/base/", 1)[1]
        app_token = rest.split("?", 1)[0].split("#", 1)[0].strip("/").split("/")[0]
        qs = parse_qs(urlparse(s).query)
        table_id = (qs.get("table") or [None])[0]
    return app_token, table_id


def list_tables(token, app_token):
    resp = fc.do_req(token, f"{fc.API}/bitable/v1/apps/{app_token}/tables?page_size=100")
    fc._check(resp, "bitable tables")
    return resp.get("data", {}).get("items", []) or []


def read_records(token, app_token, table_id, max_records=DEFAULT_MAX_RECORDS):
    records, page_token = [], ""
    while len(records) < max_records:
        url = f"{fc.API}/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"
        resp = fc.do_req(token, url)
        fc._check(resp, "bitable records")
        data = resp.get("data", {})
        records.extend(data.get("items", []) or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
    return records[:max_records]


def _render_table(token, app_token, table, max_records):
    table_id = table.get("table_id")
    name = table.get("name") or table_id
    try:
        records = read_records(token, app_token, table_id, max_records)
    except Exception as e:
        return f"## {name}\n\n(读取失败: {e})"
    if not records:
        return f"## {name}\n\n(空)"
    # Column order: first record's field order, then any fields seen later.
    columns = []
    for rec in records:
        for key in (rec.get("fields") or {}).keys():
            if key not in columns:
                columns.append(key)
    rows = [[flatten_field((rec.get("fields") or {}).get(col)) for col in columns] for rec in records]
    note = f"  ({len(records)} 条记录)" if len(records) < max_records else f"  (前 {max_records} 条，可能被截断)"
    return f"## {name}{note}\n\n" + md_table(columns, rows)


def read_bitable(url_or_token, table_id=None, max_records=DEFAULT_MAX_RECORDS):
    app_token, url_table_id = extract_base(url_or_token)
    table_id = table_id or url_table_id
    token = fc.get_tenant_token()
    if table_id:
        tables = [{"table_id": table_id, "name": table_id}]
    else:
        tables = list_tables(token, app_token)
    if not tables:
        return f"(多维表格 {app_token} 没有可读数据表)"
    out = [f"# Feishu Bitable `{app_token}` — {len(tables)} 个数据表"]
    for table in tables:
        out.append(_render_table(token, app_token, table, max_records))
    return "\n\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_bitable.py <base_url_or_app_token> [table_id] [max_records]")
        sys.exit(1)
    tid = sys.argv[2] if len(sys.argv) > 2 else None
    mx = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_MAX_RECORDS
    print(read_bitable(sys.argv[1], tid, mx))
