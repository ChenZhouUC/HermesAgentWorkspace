"""Shared helpers for the Feishu (Lark) docs scripts.

Stdlib-only. Two responsibilities:

1. ``do_req`` — a hardened HTTP helper that retries on the failures that
   actually happen against the Feishu Open API: rate limiting (429), transient
   5xx, and connection-level drops (the ``RemoteDisconnected`` that large
   ``batch_delete`` calls trigger). Exponential backoff with jitter.

2. Version-table automation — read the existing version table at the top of a
   doc, compute the next ``YYYYMMDD.NNed`` version, and rewrite the table while
   preserving the full history (splitting into consecutive 9-row tables when it
   outgrows Feishu's per-table limit). Used by both the in-place update flow
   (``append_md_to_doc``) and the full-rebuild flow (``rebuild_doc_from_md``).
"""

import http.client
import json
import os
import random
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime

API = "https://open.feishu.cn/open-apis"
BOT_OPEN_ID = "ou_0091f5c50226a4ee0dc8a6d51665db0f"  # @Gödel
VERSION_RE = re.compile(r"^(\d{8})\.(\d+)ed$")
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_CONN = (
    urllib.error.URLError,
    http.client.RemoteDisconnected,
    http.client.IncompleteRead,
    ConnectionError,
    socket.timeout,
    TimeoutError,
)


def do_req(token, url, method="GET", payload=None, timeout=30, max_attempts=5):
    """HTTP request with retry on rate-limit, transient 5xx, and dropped connections."""
    data = json.dumps(payload).encode() if payload is not None else None
    last_err = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code in _RETRYABLE_STATUS and attempt < max_attempts - 1:
                last_err = e
                _backoff(attempt, retry_after=e.headers.get("Retry-After"))
                continue
            print(f"HTTP {e.code} on {method} {url}: {body}")
            raise
        except _RETRYABLE_CONN as e:
            last_err = e
            if attempt < max_attempts - 1:
                print(f"Transient connection error ({type(e).__name__}) on {method} {url}; retrying...")
                _backoff(attempt)
                continue
            raise
    raise last_err or RuntimeError("do_req exhausted retries")  # pragma: no cover


def _backoff(attempt, retry_after=None, base=1.0, cap=20.0):
    if retry_after:
        try:
            time.sleep(min(cap, float(retry_after)))
            return
        except (TypeError, ValueError):
            pass
    time.sleep(min(cap, base * (2**attempt)) + random.uniform(0, 0.5))


def get_tenant_token(app_id=None, app_secret=None):
    """Fetch a tenant_access_token. Prefers env vars, falls back to ~/.hermes/.env."""
    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                content = f.read()
            m_id = re.search(r"FEISHU_APP_ID=(.*)", content)
            m_sec = re.search(r"FEISHU_APP_SECRET=(.*)", content)
            app_id = app_id or (m_id.group(1).strip() if m_id else None)
            app_secret = app_secret or (m_sec.group(1).strip() if m_sec else None)
    if not app_id or not app_secret:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET not found in env or ~/.hermes/.env")
    req = urllib.request.Request(
        f"{API}/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["tenant_access_token"]


def _check(resp, ctx):
    """Raise a clear error if a Feishu response carries a non-zero error code."""
    if isinstance(resp, dict) and resp.get("code", 0):
        raise RuntimeError(f"Feishu API error during {ctx}: code={resp.get('code')} msg={resp.get('msg')!r}")
    return resp


# --------------------------------------------------------------------------- #
# Markdown upload + import (fails loudly instead of a cryptic KeyError)
# --------------------------------------------------------------------------- #


def upload_md(token, file_path):
    """Upload a .md file to Drive, returning its file_token. Raises on any failure."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Markdown file not found: {file_path}")
    size = os.path.getsize(file_path)
    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        f"{API}/drive/v1/files/upload_all",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: multipart/form-data",
        "-F",
        f"file=@{file_path}",
        "-F",
        "file_name=temp.md",
        "-F",
        f"size={size}",
        "-F",
        "parent_type=explorer",
        "-F",
        "parent_node=",
    ]
    try:
        raw = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"curl upload failed (exit {e.returncode}): {e.output!r}")
    try:
        resp = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"Feishu upload returned non-JSON (auth/network issue?): {raw[:300]!r}")
    _check(resp, "drive upload")
    try:
        return resp["data"]["file_token"]
    except (KeyError, TypeError):
        raise RuntimeError(f"Feishu upload response missing file_token: {resp}")


def import_md_to_doc(token, file_token, poll_timeout=180):
    """Create an import task for an uploaded .md and poll until done; return the docx token."""
    ticket = _check(
        do_req(
            token,
            f"{API}/drive/v1/import_tasks",
            method="POST",
            payload={
                "file_extension": "md",
                "file_token": file_token,
                "type": "docx",
                "point": {"mount_type": 1, "mount_key": ""},
            },
        ),
        "create import task",
    )["data"]["ticket"]

    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        result = _check(do_req(token, f"{API}/drive/v1/import_tasks/{ticket}"), "poll import task")["data"]["result"]
        status = result["job_status"]
        if status == 0:
            return result["token"]
        if status not in (1, 2):  # 1/2 == in progress
            raise RuntimeError(f"Feishu import failed: job_status={status} detail={result}")
        time.sleep(1)
    raise TimeoutError(f"Feishu import task {ticket} did not finish within {poll_timeout}s")


# --------------------------------------------------------------------------- #
# Version-table automation
# --------------------------------------------------------------------------- #


def _elems_text(elements):
    """Concatenate the plain-text content of a list of text/mention elements."""
    out = []
    for el in elements:
        if "text_run" in el:
            out.append(el["text_run"].get("content", ""))
        elif "mention_user" in el:
            out.append("@")
    return "".join(out)


def _table_rows(table_block):
    """Return the table's cell-id grid as a list of rows (each a list of cell ids)."""
    prop = table_block["table"]["property"]
    cols = prop["column_size"]
    cells = table_block["table"]["cells"]
    return [cells[i : i + cols] for i in range(0, len(cells), cols)]


def _cell_elements(cell_id, block_map):
    """Reconstruct a cell's text/mention elements (styles stripped) for re-posting."""
    out = []
    cell = block_map.get(cell_id)
    for child_id in (cell or {}).get("children", []):
        tb = block_map.get(child_id)
        if tb and tb.get("block_type") == 2:
            for el in tb["text"].get("elements", []):
                if "text_run" in el:
                    out.append({"text_run": {"content": el["text_run"].get("content", "")}})
                elif "mention_user" in el and el["mention_user"].get("user_id"):
                    out.append({"mention_user": {"user_id": el["mention_user"]["user_id"]}})
    return out or [{"text_run": {"content": ""}}]


def _load_blocks(token, doc_token):
    root = do_req(token, f"{API}/docx/v1/documents/{doc_token}/blocks/{doc_token}")["data"]["block"]
    items = do_req(token, f"{API}/docx/v1/documents/{doc_token}/blocks?page_size=500")["data"]["items"]
    return root, {b["block_id"]: b for b in items}


def read_version_tables(token, doc_token):
    """Locate the leading version table(s).

    Returns ``(rows_elements, table_count, block_map, root)`` where
    ``rows_elements`` is ``[[col0_elems, col1_elems, col2_elems], ...]`` including
    the header row, or ``None`` if the doc has no recognizable version table at
    the top. ``table_count`` is how many leading table blocks make up the version
    table (>1 when a long history was split).
    """
    root, block_map = _load_blocks(token, doc_token)
    children = root.get("children", [])
    if not children:
        return None, 0, block_map, root

    leading = []
    for cid in children:
        b = block_map.get(cid)
        if b and b.get("block_type") == 31:
            leading.append(b)
        else:
            break
    if not leading:
        return None, 0, block_map, root

    # First leading table must look like a version table (header "Version" or a versioned first cell).
    first_rows = _table_rows(leading[0])
    if not first_rows:
        return None, 0, block_map, root
    head_text = _elems_text(_cell_elements(first_rows[0][0], block_map)).strip().lower()
    first_cell = _elems_text(_cell_elements(first_rows[0][0], block_map)).strip()
    if head_text not in ("version", "版本") and not VERSION_RE.match(first_cell):
        return None, 0, block_map, root

    # Include continuation tables only while their first cell is a version string.
    tables = [leading[0]]
    for b in leading[1:]:
        rws = _table_rows(b)
        if rws and VERSION_RE.match(_elems_text(_cell_elements(rws[0][0], block_map)).strip()):
            tables.append(b)
        else:
            break

    rows_elements = []
    for tb in tables:
        for row in _table_rows(tb):
            rows_elements.append([_cell_elements(cid, block_map) for cid in row])
    return rows_elements, len(tables), block_map, root


def compute_next_version(data_rows_elements, today=None):
    """Next ``YYYYMMDD.NNed`` — increment suffix within the same day, else reset to 01."""
    today = today or datetime.now().strftime("%Y%m%d")
    last = None
    for row in reversed(data_rows_elements):
        m = VERSION_RE.match(_elems_text(row[0]).strip())
        if m:
            last = m
            break
    n = int(last.group(2)) + 1 if (last and last.group(1) == today) else 1
    return f"{today}.{n:02d}ed"


def _chunk_rows(rows, size=9):
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _write_version_tables(token, doc_token, rows_elements, insert_index):
    """Create version table block(s) at ``insert_index`` and fill every cell.

    ``rows_elements`` includes the header row. Splits into consecutive 9-row
    tables to respect Feishu's per-table limit.
    """
    col_size = len(rows_elements[0])
    col_width = [150, 250, 150][:col_size] or None
    cur_index = insert_index
    for chunk in _chunk_rows(rows_elements):
        prop: dict = {"row_size": len(chunk), "column_size": col_size}
        if col_width:
            prop["column_width"] = col_width
        res = do_req(
            token,
            f"{API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
            method="POST",
            payload={"children": [{"block_type": 31, "table": {"property": prop}}], "index": cur_index},
        )
        cells = res["data"]["children"][0]["table"]["cells"]
        for k, cell_id in enumerate(cells):
            r, c = divmod(k, col_size)
            do_req(
                token,
                f"{API}/docx/v1/documents/{doc_token}/blocks/{cell_id}/children",
                method="POST",
                payload={"children": [{"block_type": 2, "text": {"elements": chunk[r][c]}}], "index": -1},
            )
            try:  # remove the auto-created empty text block
                do_req(
                    token,
                    f"{API}/docx/v1/documents/{doc_token}/blocks/{cell_id}/children/batch_delete",
                    method="DELETE",
                    payload={"start_index": 0, "end_index": 1},
                )
            except Exception:
                pass
        cur_index += 1


def _new_row(version, author_id):
    return [
        [{"text_run": {"content": version}}],
        [{"text_run": {"content": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC+8")}}],
        [{"mention_user": {"user_id": author_id}}],
    ]


def _header_row():
    return [
        [{"text_run": {"content": "Version"}}],
        [{"text_run": {"content": "Time"}}],
        [{"text_run": {"content": "Author"}}],
    ]


def build_and_write_version_table(token, doc_token, existing_rows, author_id=BOT_OPEN_ID, version=None, insert_index=0):
    """Write a version table = ``existing_rows`` (incl. header) + one fresh row.

    Used after the old table is already gone (caller deleted it or cleared the
    doc). Pass ``existing_rows=None`` to create a brand-new table. Returns the
    version string written.
    """
    if not existing_rows:
        version = version or compute_next_version([])
        rows = [_header_row(), _new_row(version, author_id)]
    else:
        version = version or compute_next_version(existing_rows[1:])
        rows = existing_rows + [_new_row(version, author_id)]
    _write_version_tables(token, doc_token, rows, insert_index)
    return version


def append_version_row(token, doc_token, author_id=BOT_OPEN_ID, version=None):
    """Append a new version row to the top version table, preserving all history.

    Creates the table if the doc has none. Returns the version string written.
    """
    rows, table_count, _block_map, _root = read_version_tables(token, doc_token)
    if rows:
        # Replace the old version table(s) in place: delete leading blocks first.
        do_req(
            token,
            f"{API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": table_count},
        )
    return build_and_write_version_table(token, doc_token, rows, author_id, version, insert_index=0)


# --------------------------------------------------------------------------- #
# Generic block-tree copy (shared by merge + atomic restore)
# --------------------------------------------------------------------------- #

_COPY_KEYS = (
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
    "code",
    "quote",
    "todo",
    "callout",
    "divider",
    "grid",
    "equation",
)


def build_tree(block_id, block_map):
    """Rebuild a writable block payload (ids/styles stripped) from a block_map subtree."""
    b = block_map[block_id]
    node = {"block_type": b["block_type"]}
    for k in _COPY_KEYS:
        if k in b:
            node[k] = b[k]
            if isinstance(node[k], dict) and "style" in node[k]:
                del node[k]["style"]
    for k in ("text", "bullet", "ordered"):
        if k in node:
            for el in node[k].get("elements", []):
                tr = el.get("text_run")
                if tr and "text_element_style" in tr:
                    tr["text_element_style"] = {kk: vv for kk, vv in tr["text_element_style"].items() if vv}
                    if not tr["text_element_style"]:
                        del tr["text_element_style"]
    if b["block_type"] == 31:  # table: only structural props, cells filled separately
        prop = b["table"]["property"]
        node["table"] = {"property": {"row_size": prop["row_size"], "column_size": prop["column_size"]}}
        if "column_width" in prop:
            node["table"]["property"]["column_width"] = prop["column_width"]
        return node
    if b.get("children"):
        node["children"] = [build_tree(c, block_map) for c in b["children"] if c in block_map]
    return node


def _write_table_block(token, target_doc, b, block_map):
    col_size = b["table"]["property"]["column_size"]
    col_width = b["table"]["property"].get("column_width")
    orig_cells = b["table"]["cells"]
    done = 0
    while done < len(orig_cells):
        rem_rows = (len(orig_cells) - done) // col_size
        curr_rows = min(rem_rows, 9)  # Feishu caps table creation at 9 rows
        prop: dict = {"row_size": curr_rows, "column_size": col_size}
        if col_width:
            prop["column_width"] = col_width
        res = do_req(
            token,
            f"{API}/docx/v1/documents/{target_doc}/blocks/{target_doc}/children",
            method="POST",
            payload={"children": [{"block_type": 31, "table": {"property": prop}}], "index": -1},
        )
        new_cells = res["data"]["children"][0]["table"]["cells"]
        for k, ncell in enumerate(new_cells):
            oidx = done + k
            if oidx < len(orig_cells):
                cc = block_map[orig_cells[oidx]].get("children", [])
                if cc:
                    do_req(
                        token,
                        f"{API}/docx/v1/documents/{target_doc}/blocks/{ncell}/children",
                        method="POST",
                        payload={"children": [build_tree(c, block_map) for c in cc], "index": -1},
                    )
            try:
                do_req(
                    token,
                    f"{API}/docx/v1/documents/{target_doc}/blocks/{ncell}/children/batch_delete",
                    method="DELETE",
                    payload={"start_index": 0, "end_index": 1},
                )
            except Exception:
                pass
        done += curr_rows * col_size


def write_block_tree(token, target_doc, top_children_ids, block_map, skip_first_h1=False, chunk_size=40):
    """Copy a block tree (described by ``block_map``) into ``target_doc`` in order.

    Non-table blocks are batched; tables are posted individually with their cells
    mapped, splitting tables >9 rows. Preserves strict source order.
    """
    if skip_first_h1 and top_children_ids and block_map.get(top_children_ids[0], {}).get("block_type") == 3:
        top_children_ids = top_children_ids[1:]

    for i in range(0, len(top_children_ids), chunk_size):
        chunk_ids = top_children_ids[i : i + chunk_size]
        payload_chunk = []

        def flush():
            if payload_chunk:
                do_req(
                    token,
                    f"{API}/docx/v1/documents/{target_doc}/blocks/{target_doc}/children",
                    method="POST",
                    payload={"children": list(payload_chunk), "index": -1},
                )
                payload_chunk.clear()

        for cid in chunk_ids:
            b = block_map.get(cid)
            if not b:
                continue
            if b["block_type"] == 31:
                flush()
                _write_table_block(token, target_doc, b, block_map)
            else:
                payload_chunk.append(build_tree(cid, block_map))
        flush()


# --------------------------------------------------------------------------- #
# Atomicity: snapshot -> attempt op -> roll back on failure
# --------------------------------------------------------------------------- #

BACKUP_DIR = os.path.expanduser("~/.hermes/db_workspace/feishu_backups")


def _clear_doc(token, doc_token):
    root = do_req(token, f"{API}/docx/v1/documents/{doc_token}/blocks/{doc_token}")["data"]["block"]
    kids = root.get("children", [])
    if kids:
        do_req(
            token,
            f"{API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": len(kids)},
        )


def snapshot_doc(token, doc_token):
    """Capture the doc's current block tree and write it to a local backup file.

    Returns a dict with ``children``, ``blocks`` and ``backup_path`` (the durable
    safety net; ``None`` if the file could not be written). Note: the bulk block
    read is capped at 500 blocks and only standard block types round-trip on
    restore — images/embeds are not reconstructed, so the backup file is the
    ultimate recovery source.
    """
    root, block_map = _load_blocks(token, doc_token)
    children = list(root.get("children", []))
    snap = {"doc_token": doc_token, "children": children, "blocks": block_map, "backup_path": None}
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        path = os.path.join(BACKUP_DIR, f"{doc_token}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w") as f:
            json.dump({"children": children, "blocks": block_map}, f, ensure_ascii=False)
        snap["backup_path"] = path
    except Exception as e:
        print(f"[atomic] warning: could not write backup file: {e}")
    return snap


def restore_doc(token, doc_token, snapshot):
    """Best-effort restore: clear the doc, then rewrite the snapshot's block tree."""
    _clear_doc(token, doc_token)
    write_block_tree(token, doc_token, snapshot["children"], snapshot["blocks"], skip_first_h1=False)


def atomic_update(token, doc_token, op):
    """Run ``op()`` atomically: on any exception, roll back to the pre-update state.

    Snapshots the doc (to memory + a backup file) before ``op`` runs. If ``op``
    raises, the doc is restored from the snapshot and the error re-raised, so the
    caller sees a clean failure with the document unchanged. If rollback itself
    fails, the backup file path is printed for manual recovery.
    """
    snap = snapshot_doc(token, doc_token)
    try:
        return op()
    except BaseException as e:
        print(f"[atomic] update failed: {type(e).__name__}: {e}")
        print("[atomic] rolling back to pre-update state...")
        try:
            restore_doc(token, doc_token, snap)
            print("[atomic] rollback complete — document left unchanged.")
        except Exception as re:
            print(f"[atomic] ROLLBACK FAILED: {re}")
            if snap.get("backup_path"):
                print(f"[atomic] original content is preserved in backup: {snap['backup_path']}")
        raise


# --------------------------------------------------------------------------- #
# Offline self-test for the pure logic (no network).
# --------------------------------------------------------------------------- #


def _selftest():
    failures = []

    def check(name, cond):
        print(f"  {'ok' if cond else 'FAIL'}  {name}")
        if not cond:
            failures.append(name)

    print("compute_next_version:")
    today = "20260525"
    tr = lambda v: [[{"text_run": {"content": v}}]]  # noqa: E731
    check("empty -> .01ed", compute_next_version([], today) == "20260525.01ed")
    check("same day increments", compute_next_version([tr("20260525.01ed")], today) == "20260525.02ed")
    check("same day from 02 -> 03", compute_next_version([tr("20260525.02ed")], today) == "20260525.03ed")
    check("older day resets to 01", compute_next_version([tr("20260521.03ed")], today) == "20260525.01ed")
    check(
        "uses last versioned row",
        compute_next_version([tr("20260521.01ed"), tr("20260525.01ed")], today) == "20260525.02ed",
    )
    check("ignores garbage row", compute_next_version([tr("n/a")], today) == "20260525.01ed")

    print("chunking (9-row split):")
    rows = [["h"]] + [[str(i)] for i in range(1, 20)]  # 20 rows total
    chunks = _chunk_rows(rows)
    check("20 rows -> 3 chunks", len(chunks) == 3)
    check("chunk sizes 9/9/2", [len(c) for c in chunks] == [9, 9, 2])
    check("no row lost", sum(len(c) for c in chunks) == 20)

    print("element text:")
    check("text_run concat", _elems_text([{"text_run": {"content": "ab"}}, {"text_run": {"content": "cd"}}]) == "abcd")
    check("mention rendered", _elems_text([{"mention_user": {"user_id": "x"}}]) == "@")

    print("do_req retry (mocked):")
    import io

    calls = {"n": 0}
    real_urlopen = urllib.request.urlopen

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise http.client.RemoteDisconnected("boom")

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return None

        return R(json.dumps({"ok": True}).encode())

    orig_backoff = globals()["_backoff"]
    urllib.request.urlopen = fake_urlopen
    try:
        globals()["_backoff"] = lambda *a, **k: None  # no real sleeping
        res = do_req("tok", "https://example/test")
        check("retries past 2 disconnects", res == {"ok": True} and calls["n"] == 3)
    finally:
        urllib.request.urlopen = real_urlopen
        globals()["_backoff"] = orig_backoff

    print(f"\n{'ALL PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(_selftest())
    print("Usage: python feishu_common.py --selftest")
