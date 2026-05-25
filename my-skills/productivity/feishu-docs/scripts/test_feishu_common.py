#!/usr/bin/env python3
"""Integration tests for feishu_common's version-table orchestration.

Runs against an in-memory fake of the Feishu Block API (no network) by
monkeypatching ``feishu_common.do_req``. This exercises the real read -> delete
-> rewrite flow that the live scripts use, catching the failure modes that the
pure-logic self-test cannot — in particular: detecting an existing table,
preserving full history, NOT leaving a duplicate table behind, and splitting a
>9-row history across consecutive tables that still round-trip on read.

Usage: python test_feishu_common.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_common as fc

API = fc.API
DOC = "DOC"


class FakeDoc:
    """Minimal in-memory model of a docx: blocks keyed by id, root has children."""

    def __init__(self):
        self.n = 0
        self.blocks = {DOC: {"block_id": DOC, "block_type": 0, "children": []}}

    def _new(self):
        self.n += 1
        return f"b{self.n}"

    # -- setup helper: drop a fully-populated table into the doc -------------- #
    def add_table(self, rows_elements, at_index=None):
        cols = len(rows_elements[0])
        cells = []
        for row in rows_elements:
            for cell_elems in row:
                tb = self._new()
                self.blocks[tb] = {
                    "block_id": tb,
                    "block_type": 2,
                    "text": {"elements": [dict(e) for e in cell_elems]},
                    "children": [],
                }
                cell = self._new()
                self.blocks[cell] = {"block_id": cell, "block_type": 32, "children": [tb]}
                cells.append(cell)
        tid = self._new()
        self.blocks[tid] = {
            "block_id": tid,
            "block_type": 31,
            "table": {"property": {"row_size": len(rows_elements), "column_size": cols}, "cells": cells},
            "children": list(cells),
        }
        kids = self.blocks[DOC]["children"]
        kids.insert(len(kids) if at_index is None else at_index, tid)
        return tid

    def add_text(self, content):
        tid = self._new()
        self.blocks[tid] = {
            "block_id": tid,
            "block_type": 2,
            "text": {"elements": [{"text_run": {"content": content}}]},
            "children": [],
        }
        self.blocks[DOC]["children"].append(tid)
        return tid

    # -- the fake do_req dispatcher ------------------------------------------ #
    def do_req(self, token, url, method="GET", payload=None, **kw):
        path = url.split(API, 1)[1]

        if "/children/batch_delete" in path:
            assert payload is not None
            parent = path.split("/blocks/", 1)[1].split("/")[0]
            s, e = payload["start_index"], payload["end_index"]
            kids = self.blocks[parent]["children"]
            self.blocks[parent]["children"] = kids[:s] + kids[e:]
            return {"data": {}}

        if path.endswith("/children") and method == "POST":
            assert payload is not None
            parent = path.split("/blocks/", 1)[1].split("/")[0]
            index = payload.get("index", -1)
            created = []
            for child in payload["children"]:
                created.append(self._create_block(child))
            kids = self.blocks[parent]["children"]
            ids = [c["block_id"] for c in created]
            if index is None or index < 0:
                kids.extend(ids)
            else:
                self.blocks[parent]["children"] = kids[:index] + ids + kids[index:]
            return {"data": {"children": created}}

        # GET /blocks?page_size=... -> all items
        if "/blocks?" in path:
            return {"data": {"items": list(self.blocks.values())}}

        # GET /blocks/{id} -> single block
        if "/blocks/" in path and method == "GET":
            bid = path.split("/blocks/", 1)[1].split("?")[0]
            return {"data": {"block": self.blocks[bid]}}

        raise AssertionError(f"unhandled fake request: {method} {path}")

    def _create_block(self, child):
        if child.get("block_type") == 31:
            prop = child["table"]["property"]
            r, c = prop["row_size"], prop["column_size"]
            cells = []
            for _ in range(r * c):
                tb = self._new()
                self.blocks[tb] = {
                    "block_id": tb,
                    "block_type": 2,
                    "text": {"elements": [{"text_run": {"content": ""}}]},
                    "children": [],
                }
                cell = self._new()
                self.blocks[cell] = {"block_id": cell, "block_type": 32, "children": [tb]}
                cells.append(cell)
            tid = self._new()
            self.blocks[tid] = {
                "block_id": tid,
                "block_type": 31,
                "table": {"property": dict(prop), "cells": cells},
                "children": list(cells),
            }
            return {"block_id": tid, "block_type": 31, "table": {"property": dict(prop), "cells": cells}}
        # plain block (text/etc.)
        nid = self._new()
        b = {"block_id": nid, "children": []}
        b.update({k: v for k, v in child.items()})
        self.blocks[nid] = b
        return b


# --------------------------------------------------------------------------- #
# Assertions / helpers
# --------------------------------------------------------------------------- #

FAILS = []


def check(name, cond):
    print(f"  {'ok' if cond else 'FAIL'}  {name}")
    if not cond:
        FAILS.append(name)


def header():
    return [
        [{"text_run": {"content": "Version"}}],
        [{"text_run": {"content": "Time"}}],
        [{"text_run": {"content": "Author"}}],
    ]


def data_row(version, author_id=fc.BOT_OPEN_ID):
    return [
        [{"text_run": {"content": version}}],
        [{"text_run": {"content": "2026-05-01 00:00:00 UTC+8"}}],
        [{"mention_user": {"user_id": author_id}}],
    ]


def leading_table_count(doc):
    n = 0
    for cid in doc.blocks[DOC]["children"]:
        if doc.blocks[cid]["block_type"] == 31:
            n += 1
        else:
            break
    return n


def read_rows_text(doc):
    rows, _count, _bm, _root = fc.read_version_tables("tok", DOC)
    assert rows is not None, "expected a version table to exist"
    return [[fc._elems_text(c) for c in row] for row in rows]


def author_user_ids(doc):
    """user_id of each row's author cell, via the live reader."""
    rows, *_ = fc.read_version_tables("tok", DOC)
    assert rows is not None
    out = []
    for row in rows:
        uid = None
        for el in row[2]:
            if "mention_user" in el:
                uid = el["mention_user"]["user_id"]
        out.append(uid)
    return out


def doc_content(doc):
    """Snapshot the doc's top-level content as comparable (type, value) tuples."""
    out = []
    for cid in doc.blocks[DOC]["children"]:
        b = doc.blocks[cid]
        if b["block_type"] == 31:
            rows = fc._table_rows(b)
            out.append(("table", [[fc._elems_text(fc._cell_elements(c, doc.blocks)) for c in row] for row in rows]))
        elif b["block_type"] == 2:
            out.append(("text", fc._elems_text(b["text"]["elements"])))
        else:
            out.append((b["block_type"], None))
    return out


def run_case(name, build):
    print(name + ":")
    doc = FakeDoc()
    fc.do_req = doc.do_req
    build(doc)


def main():
    # ---- A: existing table with history -> append preserves + no duplicate ----
    def case_a(doc):
        doc.add_table([header(), data_row("20260518.01ed"), data_row("20260521.01ed")])
        doc.add_text("Some body content")
        v = fc.append_version_row("tok", DOC, version="20260525.01ed")
        rows = read_rows_text(doc)
        check("returns the new version", v == "20260525.01ed")
        check("exactly one leading table (no duplicate)", leading_table_count(doc) == 1)
        check("history preserved + appended (4 rows)", len(rows) == 4)
        check(
            "row order is oldest->newest",
            [r[0] for r in rows[1:]] == ["20260518.01ed", "20260521.01ed", "20260525.01ed"],
        )
        check("new author is a mention card", author_user_ids(doc)[-1] == fc.BOT_OPEN_ID)
        check(
            "body content still present",
            any(
                doc.blocks[c]["block_type"] == 2
                and doc.blocks[c]["text"]["elements"][0].get("text_run", {}).get("content") == "Some body content"
                for c in doc.blocks[DOC]["children"]
            ),
        )

    run_case("A. append onto existing history", case_a)

    # ---- B: no version table -> creates header + 1 row ----
    def case_b(doc):
        doc.add_text("Only body, no table")
        v = fc.append_version_row("tok", DOC, version="20260525.01ed")
        rows = read_rows_text(doc)
        check("returns version", v == "20260525.01ed")
        check("one leading table created", leading_table_count(doc) == 1)
        check("header + 1 data row", rows is not None and len(rows) == 2 and rows[0][0] == "Version")

    run_case("B. create when none exists", case_b)

    # ---- C: >9 rows -> split across consecutive tables, round-trips on read ----
    def case_c(doc):
        rows_in = [header()] + [data_row(f"2026050{i % 10}.0{i % 9 + 1}ed") for i in range(9)]  # header + 9 data = 10
        doc.add_table(rows_in)
        check("setup is 10 rows in 1 table", leading_table_count(doc) == 1)
        fc.append_version_row("tok", DOC, version="20260525.01ed")  # -> 11 rows total
        check("split into 2 consecutive tables", leading_table_count(doc) == 2)
        # the two tables should hold 9 + 2 rows
        kids = doc.blocks[DOC]["children"]
        t0, t1 = kids[0], kids[1]
        r0 = doc.blocks[t0]["table"]["property"]["row_size"]
        r1 = doc.blocks[t1]["table"]["property"]["row_size"]
        check("first table 9 rows, second 2", (r0, r1) == (9, 2))
        rows = read_rows_text(doc)
        check("reader concatenates to 11 rows", rows is not None and len(rows) == 11)
        check("newest row is the appended one", rows[-1][0] == "20260525.01ed")

    run_case("C. history outgrows 9-row table limit", case_c)

    # ---- D: rebuild flow -> read-before-clear, then rewrite preserves history ----
    def case_d(doc):
        doc.add_table([header(), data_row("20260520.01ed")])
        doc.add_text("old content 1")
        doc.add_text("old content 2")
        existing, _c, _bm, _root = fc.read_version_tables("tok", DOC)
        # simulate rebuild's clear-all
        n = len(doc.blocks[DOC]["children"])
        fc.do_req(
            "tok",
            f"{API}/docx/v1/documents/{DOC}/blocks/{DOC}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": n},
        )
        check("doc fully cleared", len(doc.blocks[DOC]["children"]) == 0)
        v = fc.build_and_write_version_table("tok", DOC, existing, version="20260525.01ed", insert_index=0)
        rows = read_rows_text(doc)
        check("returns version", v == "20260525.01ed")
        check("history preserved through rebuild (3 rows)", rows is not None and len(rows) == 3)
        check("old version row survived", rows[1][0] == "20260520.01ed")
        check("one leading table", leading_table_count(doc) == 1)

    run_case("D. rebuild preserves version history", case_d)

    # ---- E: atomic_update happy path returns result, no rollback ----
    def case_e(doc):
        fc.BACKUP_DIR = tempfile.mkdtemp()
        doc.add_table([header(), data_row("20260520.01ed")])
        doc.add_text("content X")
        res = fc.atomic_update("tok", DOC, lambda: "ok-result")
        check("returns op result", res == "ok-result")
        check("content untouched on success", len(doc.blocks[DOC]["children"]) == 2)

    run_case("E. atomic_update success path", case_e)

    # ---- F: atomic_update rolls back a partially-applied destructive failure ----
    def case_f(doc):
        fc.BACKUP_DIR = tempfile.mkdtemp()
        doc.add_table([header(), data_row("20260520.01ed")])
        doc.add_text("important content A")
        doc.add_text("important content B")
        before = doc_content(doc)

        def bad_op():
            fc._clear_doc("tok", DOC)  # destructive
            doc.add_text("garbage half-write")
            raise RuntimeError("boom mid-update")

        raised = False
        try:
            fc.atomic_update("tok", DOC, bad_op)
        except RuntimeError:
            raised = True

        after = doc_content(doc)
        check("failure propagated to caller", raised)
        check("doc rolled back to pre-update content", after == before)
        check("backup file was written", any(f.endswith(".json") for f in os.listdir(fc.BACKUP_DIR)))

    run_case("F. atomic_update rollback on failure", case_f)

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
