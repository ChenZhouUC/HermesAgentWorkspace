#!/usr/bin/env python3
"""Sync the Feishu (Lark) org directory into ~/.hermes/people.yaml — two steps.

The pull and the merge are intentionally separate so an automated objective
pull can never clobber the subjective fields you set by hand:

  pull   Fetch objective org data from Feishu and write people.draft.yaml.
         NEVER touches the production people.yaml.

  merge  Combine the draft's NEW data (objective facts, org structure) with the
         OLD data in people.yaml (your manual fields), writing people.merged.yaml
         for review. With --apply, write the result back into people.yaml (.bak
         kept). Owner pinned to the top, everyone else sorted by employee_no.

Field policy on merge:
  Objective — always refreshed from the draft (don't hand-edit these):
      name, department, employee_no, join_date, tenure,
      manager, direct_reports, total_reports
  role — seeded from the Feishu job title only if you haven't set it.
  Subjective — created blank for new people, NEVER overwritten if already set:
      address, background, behavior, stance, risks

Subordinate counts come from the management graph (each user's leader_user_id);
employee_no + join_date reveal tenure / seniority.

Usage:
    python scripts/pull_feishu_people.py pull
    python scripts/pull_feishu_people.py merge            # → people.merged.yaml (review)
    python scripts/pull_feishu_people.py merge --apply     # → people.yaml (.bak kept)

Requires a published app version granting:
    contact:department.base:readonly   → department names
    contact:user.employee:readonly     → job_title / employee_no / join_time / leader_user_id
Data range (which departments) = whatever you authorized in the console.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import re
import shutil
import sys
from pathlib import Path

HERMES_HOME = Path(__file__).resolve().parent.parent
ENV_FILE = HERMES_HOME / ".env"
PEOPLE_FILE = HERMES_HOME / "people.yaml"
DRAFT_FILE = HERMES_HOME / "people.draft.yaml"
MERGED_FILE = HERMES_HOME / "people.merged.yaml"

# Owner's open_id — always pinned to the top of the sorted file.
PIN_FIRST = "ou_33eeacfbd0c0559b7b734f83503719ab"

# Canonical field order inside each person entry (drives insert positions).
FIELD_ORDER = [
    "open_id",
    "name",
    "role",
    "department",
    "employee_no",
    "join_date",
    "tenure",
    "manager",
    "direct_reports",
    "total_reports",
    "aliases",
    "address",
    "background",
    "behavior",
    "stance",
    "risks",
    "notes",
]
# Objective fields the pull owns and the merge always refreshes.
ALWAYS_REFRESH = [
    "name",
    "department",
    "employee_no",
    "join_date",
    "tenure",
    "manager",
    "direct_reports",
    "total_reports",
]
# Seeded from Feishu but yours to refine — only filled when empty.
FILL_IF_EMPTY = ["role"]
# Purely human-set — created blank for new people, never overwritten.
SUBJECTIVE = ["address", "background", "behavior", "stance", "risks"]


# --------------------------------------------------------------------------- #
# Feishu fetch
# --------------------------------------------------------------------------- #
def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)\s*$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def build_client():
    env = load_env(ENV_FILE)
    app_id = env.get("FEISHU_APP_ID", "").strip()
    app_secret = env.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        sys.exit("FEISHU_APP_ID / FEISHU_APP_SECRET missing in .env")
    import lark_oapi as lark

    return lark.Client.builder().app_id(app_id).app_secret(app_secret).log_level(lark.LogLevel.ERROR).build()


def collect(client) -> tuple[dict, dict]:
    """Return (people_by_open_id, dept_name_by_id) of raw objective data."""
    from lark_oapi.api.contact.v3 import (
        ListScopeRequest,
        GetDepartmentRequest,
        ChildrenDepartmentRequest,
        FindByDepartmentUserRequest,
        GetUserRequest,
    )

    scope = client.contact.v3.scope.list(ListScopeRequest.builder().page_size(50).build())
    if not scope.success():
        sys.exit(f"scope.list failed: code={scope.code} msg={scope.msg}")
    roots = list(scope.data.department_ids or [])

    dept_name: dict = {}
    people: dict = {}
    seen: set = set()

    def name_of_dept(did: str) -> str:
        if did in dept_name:
            return dept_name[did]
        r = client.contact.v3.department.get(
            GetDepartmentRequest.builder()
            .department_id(did)
            .department_id_type("open_department_id")
            .user_id_type("open_id")
            .build()
        )
        nm = getattr(r.data.department, "name", None) if r.success() else None
        dept_name[did] = nm or did
        return dept_name[did]

    def add_user(u, fallback_dept):
        oid = getattr(u, "open_id", None)
        if not oid:
            return
        e = people.setdefault(
            oid,
            {
                "name": None,
                "job_title": None,
                "employee_no": None,
                "join_time": None,
                "leader": None,
                "dept_ids": set(),
            },
        )
        e["name"] = e["name"] or getattr(u, "name", None)
        e["job_title"] = e["job_title"] or getattr(u, "job_title", None)
        e["employee_no"] = e["employee_no"] or getattr(u, "employee_no", None)
        e["join_time"] = e["join_time"] or getattr(u, "join_time", None)
        e["leader"] = e["leader"] or getattr(u, "leader_user_id", None)
        for d in getattr(u, "department_ids", None) or [fallback_dept]:
            e["dept_ids"].add(d)

    def walk(did: str):
        if did in seen:
            return
        seen.add(did)
        name_of_dept(did)
        token = None
        while True:
            b = (
                FindByDepartmentUserRequest.builder()
                .department_id(did)
                .department_id_type("open_department_id")
                .user_id_type("open_id")
                .page_size(50)
            )
            if token:
                b = b.page_token(token)
            r = client.contact.v3.user.find_by_department(b.build())
            if not r.success():
                print(f"  [warn] users in {did}: code={r.code} msg={r.msg}", file=sys.stderr)
                break
            for u in r.data.items or []:
                add_user(u, did)
            if getattr(r.data, "has_more", False) and getattr(r.data, "page_token", None):
                token = r.data.page_token
            else:
                break
        token = None
        while True:
            b = (
                ChildrenDepartmentRequest.builder()
                .department_id(did)
                .department_id_type("open_department_id")
                .user_id_type("open_id")
                .page_size(50)
            )
            if token:
                b = b.page_token(token)
            r = client.contact.v3.department.children(b.build())
            if not r.success():
                break
            for ch in r.data.items or []:
                cid = getattr(ch, "open_department_id", None) or getattr(ch, "department_id", None)
                nm = getattr(ch, "name", None)
                if cid:
                    if nm:
                        dept_name[cid] = nm
                    walk(cid)
            if getattr(r.data, "has_more", False) and getattr(r.data, "page_token", None):
                token = r.data.page_token
            else:
                break

    for root in roots:
        walk(root)

    # Resolve manager names for leaders outside the pulled set (best effort).
    def resolve_name(oid: str):
        if oid in people and people[oid]["name"]:
            return people[oid]["name"]
        r = client.contact.v3.user.get(
            GetUserRequest.builder()
            .user_id(oid)
            .user_id_type("open_id")
            .department_id_type("open_department_id")
            .build()
        )
        return getattr(r.data.user, "name", None) if r.success() else None

    name_cache: dict = {}
    for e in people.values():
        lid = e["leader"]
        if lid and lid not in name_cache:
            name_cache[lid] = resolve_name(lid)
    for e in people.values():
        e["manager_name"] = name_cache.get(e["leader"]) if e["leader"] else None

    # Management graph → direct + total (recursive) report counts.
    direct: dict = {}
    for oid, e in people.items():
        if e["leader"]:
            direct.setdefault(e["leader"], []).append(oid)
    for oid, e in people.items():
        e["direct_reports"] = len(direct.get(oid, []))

    def total(oid, stack):
        if oid in stack:  # cycle guard
            return 0
        stack.add(oid)
        n = sum(1 + total(r, stack) for r in direct.get(oid, []))
        stack.discard(oid)
        return n

    for oid, e in people.items():
        e["total_reports"] = total(oid, set())

    return people, dept_name


def fmt_join(ts):
    if not ts:
        return None
    try:
        return dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return None


def fmt_tenure(ts):
    if not ts:
        return None
    try:
        days = (dt.datetime.now() - dt.datetime.fromtimestamp(int(ts))).days
        return f"{days / 365.25:.1f}年"
    except (ValueError, OSError, OverflowError):
        return None


def objective_entry(oid: str, e: dict, dept_name: dict) -> dict:
    """Flatten one raw person record into the objective YAML field set."""
    depts = " / ".join(dict.fromkeys(dept_name.get(d, d) for d in sorted(e["dept_ids"])))
    out = {"open_id": oid, "name": e["name"]}
    if e["job_title"]:
        out["role"] = e["job_title"]
    if depts:
        out["department"] = depts
    if e["employee_no"]:
        out["employee_no"] = e["employee_no"]
    if fmt_join(e["join_time"]):
        out["join_date"] = fmt_join(e["join_time"])
    if fmt_tenure(e["join_time"]):
        out["tenure"] = fmt_tenure(e["join_time"])
    if e.get("manager_name"):
        out["manager"] = e["manager_name"]
    out["direct_reports"] = e["direct_reports"]
    out["total_reports"] = e["total_reports"]
    return out


# --------------------------------------------------------------------------- #
# YAML helpers (ruamel round-trip)
# --------------------------------------------------------------------------- #
def make_yaml():
    from ruamel.yaml import YAML

    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    y.representer.add_representer(type(None), lambda r, d: r.represent_scalar("tag:yaml.org,2002:null", ""))
    return y


def upsert(ent, key, value):
    """Set ent[key]=value, inserting at the canonical position if new."""
    if key in ent:
        ent[key] = value
        return
    prevs = FIELD_ORDER[: FIELD_ORDER.index(key)]
    keys = list(ent.keys())
    pos = len(keys)
    for a in reversed(prevs):
        if a in keys:
            pos = keys.index(a) + 1
            break
    ent.insert(pos, key, value)


def dump_sorted(yaml, doc) -> str:
    """Sort entries (owner first, then employee_no asc) and return YAML text."""
    seq = doc["people"]
    items = list(seq)
    seq.ca.items.clear()  # drop seq-level comments; re-spaced on output below

    def key(it):
        oid = it.get("open_id") if isinstance(it, dict) else None
        eno = it.get("employee_no") if isinstance(it, dict) else None
        return (
            0 if oid == PIN_FIRST else 1,
            eno is None,
            str(eno or ""),
            str((it.get("name") if isinstance(it, dict) else "") or ""),
        )

    items.sort(key=key)
    seq[:] = items

    buf = io.StringIO()
    yaml.dump(doc, buf)
    text = buf.getvalue()
    text = re.sub(r"\n(  - open_id:)", r"\n\n\1", text)  # blank line between entries
    text = re.sub(r"(people:\n)\n+", r"\1", text)  # but not right after "people:"
    return text


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #
def cmd_pull(args):
    client = build_client()
    print("Pulling authorized departments and members ...", file=sys.stderr)
    people, dept_name = collect(client)
    print(f"Collected {len(people)} people across {len(dept_name)} departments.", file=sys.stderr)

    yaml = make_yaml()
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    seq = CommentedSeq()
    for oid, e in people.items():
        m = CommentedMap()
        for k, v in objective_entry(oid, e, dept_name).items():
            m[k] = v
        seq.append(m)
    doc = CommentedMap()
    doc["generated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc["people"] = seq
    text = dump_sorted(yaml, doc)
    DRAFT_FILE.write_text(
        "# OBJECTIVE SNAPSHOT from Feishu — do not hand-edit; run `merge` to combine\n"
        "# with people.yaml. This file never affects production until you merge.\n" + text,
        encoding="utf-8",
    )
    have_mgr = sum(1 for e in people.values() if e.get("manager_name"))
    have_no = sum(1 for e in people.values() if e["employee_no"])
    leads = sum(1 for e in people.values() if e["direct_reports"] > 0)
    print(f"  manager: {have_mgr} | employee_no: {have_no} | people with reports: {leads}", file=sys.stderr)
    print(f"Wrote objective snapshot → {DRAFT_FILE}", file=sys.stderr)
    print("Next: python scripts/pull_feishu_people.py merge", file=sys.stderr)


def cmd_merge(args):
    if not DRAFT_FILE.exists():
        sys.exit(f"{DRAFT_FILE} not found — run `pull` first.")
    yaml = make_yaml()
    draft_doc = yaml.load(DRAFT_FILE)
    draft = {it["open_id"]: it for it in draft_doc["people"] if isinstance(it, dict) and it.get("open_id")}

    doc = yaml.load(PEOPLE_FILE) if PEOPLE_FILE.exists() else None
    if doc is None or "people" not in doc or doc["people"] is None:
        from ruamel.yaml.comments import CommentedMap, CommentedSeq

        doc = doc if isinstance(doc, dict) else CommentedMap()
        doc["people"] = CommentedSeq()
    seq = doc["people"]
    index = {it["open_id"]: it for it in seq if isinstance(it, dict) and it.get("open_id")}

    from ruamel.yaml.comments import CommentedMap

    added = updated = 0
    for oid, d in draft.items():
        ent = index.get(oid)
        if ent is None:
            ent = CommentedMap()
            ent["open_id"] = oid
            seq.append(ent)
            index[oid] = ent
            added += 1
        else:
            updated += 1
        for f in ALWAYS_REFRESH:
            if f in d:
                upsert(ent, f, d[f])
        for f in FILL_IF_EMPTY:
            if not ent.get(f) and d.get(f):
                upsert(ent, f, d[f])
        for f in SUBJECTIVE:
            if f not in ent:
                upsert(ent, f, None)

    kept_manual = [oid for oid in index if oid not in draft]
    text = dump_sorted(yaml, doc)

    if args.apply:
        if PEOPLE_FILE.exists():
            shutil.copy2(PEOPLE_FILE, PEOPLE_FILE.with_suffix(".yaml.bak"))
        PEOPLE_FILE.write_text(text, encoding="utf-8")
    else:
        MERGED_FILE.write_text(
            "# MERGE PREVIEW — objective fields from people.draft.yaml refreshed,\n"
            "# your subjective fields preserved. Re-run with --apply to write people.yaml.\n" + text,
            encoding="utf-8",
        )

    print(f"merged: {updated} updated, {added} new, {len(kept_manual)} manual-only kept", file=sys.stderr)
    if args.apply:
        print(f"Applied → {PEOPLE_FILE} (backup: people.yaml.bak)", file=sys.stderr)
    else:
        print(f"Preview → {MERGED_FILE}", file=sys.stderr)
        print("Review it, then: python scripts/pull_feishu_people.py merge --apply", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Sync Feishu org directory into people.yaml (pull → merge).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pull", help="fetch objective org data → people.draft.yaml (never touches production)")
    mp = sub.add_parser("merge", help="combine draft + people.yaml → people.merged.yaml (or people.yaml with --apply)")
    mp.add_argument("--apply", action="store_true", help="write the merge result into people.yaml (.bak kept)")
    args = ap.parse_args()
    {"pull": cmd_pull, "merge": cmd_merge}[args.cmd](args)


if __name__ == "__main__":
    main()
