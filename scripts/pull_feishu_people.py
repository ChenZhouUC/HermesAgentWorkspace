#!/usr/bin/env python3
"""Sync the Feishu (Lark) org directory into ~/.hermes/people.yaml — two steps.

The pull and the merge are intentionally separate so an automated objective
pull can never clobber the subjective fields you set by hand:

  pull   Fetch a complete active-employee snapshot from Feishu and write
         people.draft.yaml.
         NEVER touches the production people.yaml.

  merge  Combine the draft's NEW data (objective facts, org structure) with the
         OLD data in people.yaml (your manual fields), writing people.merged.yaml
         for review. With --apply, write the result back into people.yaml (.bak
         kept). Owner pinned to the top, everyone else sorted by employee_no.

  sync   Pull, then merge. With --apply this is the unattended nightly path;
         --summary-only writes only added/removed people for a dry-run review.

  check  Audit people.yaml formatting only (exit 1 when it deviates); --fix
         rewrites it in canonical form after verifying the data is unchanged.

Field policy on merge:
  Feishu-backed — authoritative. Values are refreshed from the latest complete
  snapshot; a field omitted by Feishu is removed rather than retaining stale
  local org data:
      user_id, name, role, department, employee_no, join_date, tenure,
      manager, direct_reports, total_reports
  Subjective — created blank for new people, NEVER overwritten if already set:
      address, background, behavior, stance, risks
  aliases — preserved for existing people; synthesized from the Feishu name for
  new people, then left untouched for later manual refinement.
  Any unknown/local-only key is also preserved for still-active employees.
  Roster — the draft is authoritative; entries absent from it are removed.
  Safety — API/page failures abort the snapshot. Applying a removal of more than
  20% of the current roster requires --allow-large-removal, protecting against
  accidental permission-scope shrinkage.

Subordinate counts come from the management graph (each user's leader_user_id);
employee_no + join_date reveal tenure / seniority.

Formatting: every write ends with the canonical style — fields in FIELD_ORDER,
aliases as a flow list `[a, b, c]`, placeholder hints only on empty fields — and
is then piped through Prettier with the same options VS Code uses on save
(settings.json maps `[yaml]` to esbenp.prettier-vscode), so opening the file and
saving it produces no diff. NOTE: AutoCorrect must not touch people*.yaml — it
rewrites `别名, Nickname` into `别名，Nickname` and merges aliases; see .autocorrectignore.

Usage:
    python scripts/pull_feishu_people.py pull
    python scripts/pull_feishu_people.py merge            # → people.merged.yaml (review)
    python scripts/pull_feishu_people.py merge --apply     # → people.yaml (.bak kept)
    python scripts/pull_feishu_people.py sync --apply      # nightly pull + apply
    python scripts/pull_feishu_people.py check             # audit formatting
    python scripts/pull_feishu_people.py check --fix       # normalize in place

Requires a published app version granting:
    contact:department.base:readonly   → department names
    contact:user.employee:readonly     → job_title / employee_no / join_time / leader_user_id
Data range (which departments) = whatever you authorized in the console.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
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
    "user_id",
    "name",
    "aliases",
    "role",
    "department",
    "employee_no",
    "join_date",
    "tenure",
    "manager",
    "direct_reports",
    "total_reports",
    "address",
    "background",
    "behavior",
    "stance",
    "risks",
    "notes",
]
# Feishu-backed fields the merge refreshes whenever the draft provides a value.
ALWAYS_REFRESH = [
    "user_id",
    "name",
    "role",
    "department",
    "employee_no",
    "join_date",
    "tenure",
    "manager",
    "direct_reports",
    "total_reports",
]
# Purely human-set — created blank for new people, never overwritten.
SUBJECTIVE = ["address", "background", "behavior", "stance", "risks"]
MAX_AUTOMATIC_REMOVAL_RATIO = 0.20

# Canonical trailing comments, so every entry reads the same way. `role` carries
# a different hint depending on whether Feishu supplied a job title.
ROLE_COMMENT_FILLED = "职务（飞书组织同步，勿手改）"
ROLE_COMMENT_EMPTY = "岗位（待填）"
SUBJECTIVE_COMMENTS = {
    "address": "称呼（待填）",
    "background": "职业背景（待填）",
    "behavior": "行为模式（待填）",
    "stance": "你的态度（待填）",
    "risks": "风险注意（待填）",
}
# Every comment this script owns — anything else on these keys is hand-written
# and must be left alone.
ALL_COMMENTS = {ROLE_COMMENT_FILLED, ROLE_COMMENT_EMPTY, *SUBJECTIVE_COMMENTS.values()}


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


def is_active_employee(user) -> bool:
    """Exclude people Feishu marks as resigned/exited/unjoined/inactive."""
    status = getattr(user, "status", None)
    if status is None:
        return True
    if any(bool(getattr(status, field, False)) for field in ("is_resigned", "is_exited", "is_unjoin")):
        return False
    activated = getattr(status, "is_activated", None)
    return activated is not False


def validate_identity_fields(people: dict) -> None:
    """Require a complete, one-to-one open_id ↔ tenant user_id snapshot."""
    missing_user_ids = [oid for oid, entry in people.items() if not entry.get("user_id")]
    if missing_user_ids:
        raise RuntimeError(
            "Feishu organization snapshot has "
            f"{len(missing_user_ids)} employees without tenant user_id; "
            "refusing to write a partial identity roster"
        )
    user_ids = [str(entry["user_id"]) for entry in people.values()]
    if len(set(user_ids)) != len(user_ids):
        raise RuntimeError("Feishu organization snapshot contains duplicate tenant user_id values")


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
    if not roots:
        raise RuntimeError("Feishu contact scope returned no authorized root departments")

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
        if not r.success() or not getattr(r, "data", None) or not getattr(r.data, "department", None):
            raise RuntimeError(f"department.get failed for {did}: code={r.code} msg={r.msg}")
        nm = getattr(r.data.department, "name", None)
        if not nm:
            raise RuntimeError(f"department.get returned no name for {did}")
        dept_name[did] = nm
        return dept_name[did]

    def add_user(u, fallback_dept):
        if not is_active_employee(u):
            return
        oid = getattr(u, "open_id", None)
        if not oid:
            return
        e = people.setdefault(
            oid,
            {
                "user_id": None,
                "name": None,
                "job_title": None,
                "employee_no": None,
                "join_time": None,
                "leader": None,
                "dept_ids": set(),
            },
        )
        e["user_id"] = e["user_id"] or getattr(u, "user_id", None)
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
                raise RuntimeError(f"users in {did} failed: code={r.code} msg={r.msg}")
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
                raise RuntimeError(f"department.children failed for {did}: code={r.code} msg={r.msg}")
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
    if not people:
        raise RuntimeError("Feishu organization snapshot contained no active employees")
    missing_names = [oid for oid, entry in people.items() if not entry.get("name")]
    if missing_names:
        raise RuntimeError(f"Feishu organization snapshot has {len(missing_names)} employees without names")
    validate_identity_fields(people)

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
        if not r.success() or not getattr(r, "data", None) or not getattr(r.data, "user", None):
            raise RuntimeError(f"leader lookup failed for {oid}: code={r.code} msg={r.msg}")
        return getattr(r.data.user, "name", None)

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
    out = {"open_id": oid, "user_id": e["user_id"], "name": e["name"]}
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
        if ent[key] != value:
            if key == "join_date" and isinstance(value, str):
                from ruamel.yaml.scalarstring import DoubleQuotedScalarString

                value = DoubleQuotedScalarString(value)
            ent[key] = value
        return
    if key == "join_date" and isinstance(value, str):
        from ruamel.yaml.scalarstring import DoubleQuotedScalarString

        value = DoubleQuotedScalarString(value)
    prevs = FIELD_ORDER[: FIELD_ORDER.index(key)]
    keys = list(ent.keys())
    pos = len(keys)
    for a in reversed(prevs):
        if a in keys:
            pos = keys.index(a) + 1
            break
    ent.insert(pos, key, value)


def aliases_from_name(name: str) -> list[str]:
    """Build the compact alias form used by existing people.yaml entries."""
    text = " ".join(str(name or "").split())
    if not text:
        return []
    aliases: list[str] = []

    def add(value: str):
        value = value.strip()
        if value and value not in aliases:
            aliases.append(value)

    nickname_match = re.search(r"\(([^()]+)\)\s*$", text)
    nickname = nickname_match.group(1).strip() if nickname_match else ""
    base = text[: nickname_match.start()].strip() if nickname_match else text
    parts = base.split()
    latin_parts = [part for part in parts if re.search(r"[A-Za-z]", part)]
    non_latin_parts = [part for part in parts if not re.search(r"[A-Za-z]", part)]
    if latin_parts:
        add(latin_parts[0])
        add(" ".join(latin_parts))
    for part in non_latin_parts:
        add(part)
    if not aliases:
        add(base)
    add(nickname)
    return aliases


def canonical_comments(ent) -> dict:
    """The trailing comment each field of this entry should carry ("" = none).

    Placeholder hints mark fields still waiting to be filled in, so a field that
    already holds a value gets no hint. `role` is the exception: it is populated
    from Feishu, so it keeps a note saying the value is auto-filled but editable.
    """
    wanted = {}
    if "role" in ent:
        wanted["role"] = ROLE_COMMENT_FILLED if ent.get("role") not in (None, "") else ROLE_COMMENT_EMPTY
    for key, comment in SUBJECTIVE_COMMENTS.items():
        if key in ent:
            wanted[key] = "" if ent.get(key) not in (None, "") else comment
    return wanted


def normalize_entry(ent) -> None:
    """Make one entry's formatting canonical (idempotent, value-preserving).

    Keeps hand-edited files and script-generated ones byte-identical in style:
      * fields ordered per FIELD_ORDER;
      * aliases as a flow sequence — `[a, b, c]`, not a block list;
      * the canonical trailing comment on role + the subjective fields.
    """
    from ruamel.yaml.comments import CommentedSeq

    # Field order: rebuild in canonical order, unknown keys keep their tail spot.
    desired = [k for k in FIELD_ORDER if k in ent] + [k for k in ent if k not in FIELD_ORDER]
    if list(ent.keys()) != desired:
        for key in desired:
            ent.move_to_end(key)

    # aliases: always the compact flow form.
    val = ent.get("aliases")
    if isinstance(val, list):
        seq = val if isinstance(val, CommentedSeq) else CommentedSeq(val)
        seq.fa.set_flow_style()
        ent["aliases"] = seq

    # Trailing hints. A "（待填）" note is a prompt to fill the field in, so it
    # belongs only on empty ones — never append it to content you already wrote.
    for key, comment in canonical_comments(ent).items():
        existing = ent.ca.items.get(key)
        existing_text = existing[2].value.lstrip("#").strip() if existing and existing[2] else ""
        # Only ever rewrite our own boilerplate; a hand-written note is yours.
        if existing_text and existing_text not in ALL_COMMENTS:
            continue
        if existing_text == comment:
            continue
        ent.ca.items.pop(key, None)
        if comment:
            ent.yaml_add_eol_comment(comment, key)


def prettier_format(text: str, label: str) -> str:
    """Run the text through Prettier — the formatter VS Code uses on save.

    settings.json maps `[yaml]` to esbenp.prettier-vscode with formatOnSave, so
    emitting anything Prettier would rewrite means the file drifts the next time
    you save it in the editor. Matching it here keeps the diff empty. Prettier is
    optional: without it the output is already valid, just possibly two spaces
    before a trailing comment where Prettier wants one.
    """
    exe = shutil.which("prettier")
    if not exe:
        print(f"  note: prettier not found — skipped final format of {label}", file=sys.stderr)
        return text
    # --ignore-path pins the extension's behaviour: it honours .prettierignore
    # only, while the Prettier 3 CLI would also skip people.yaml for being
    # gitignored. Options mirror the `prettier.*` keys in VS Code settings.json.
    cmd = [
        exe,
        "--ignore-path",
        str(HERMES_HOME / ".prettierignore"),
        "--parser",
        "yaml",
        "--print-width",
        "120",
        "--tab-width",
        "2",
        "--prose-wrap",
        "preserve",
    ]
    try:
        # check=False: a Prettier failure must not lose the merge — fall back to
        # the unformatted text and say so.
        done = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  note: prettier failed ({exc}) — kept unformatted {label}", file=sys.stderr)
        return text
    if done.returncode != 0:
        print(f"  note: prettier exited {done.returncode} — kept unformatted {label}", file=sys.stderr)
        if done.stderr.strip():
            print(f"        {done.stderr.strip().splitlines()[0]}", file=sys.stderr)
        return text
    return done.stdout


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
    for it in items:
        if isinstance(it, dict):
            normalize_entry(it)

    buf = io.StringIO()
    yaml.dump(doc, buf)
    text = buf.getvalue()
    text = re.sub(r"\n(  - open_id:)", r"\n\n\1", text)  # blank line between entries
    text = re.sub(r"\n{3,}(  - open_id:)", r"\n\n\1", text)  # don't duplicate existing spacing
    text = re.sub(r"(people:\n)\n+", r"\1", text)  # but not right after "people:"
    return text


def atomic_write_private(path: Path, text: str) -> None:
    """Atomically replace a private roster artifact with owner-only mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(path)
        path.chmod(0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


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
    atomic_write_private(
        DRAFT_FILE,
        prettier_format(
            "# OBJECTIVE SNAPSHOT from Feishu — do not hand-edit; run `merge` to combine\n"
            "# with people.yaml. This file never affects production until you merge.\n" + text,
            DRAFT_FILE.name,
        ),
    )
    have_mgr = sum(1 for e in people.values() if e.get("manager_name"))
    have_no = sum(1 for e in people.values() if e["employee_no"])
    have_user_id = sum(1 for e in people.values() if e["user_id"])
    leads = sum(1 for e in people.values() if e["direct_reports"] > 0)
    print(
        f"  user_id: {have_user_id} | manager: {have_mgr} | employee_no: {have_no} | people with reports: {leads}",
        file=sys.stderr,
    )
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

    removed_ids = [oid for oid in index if oid not in draft]
    removed_people = [{"open_id": oid, "name": str(index[oid].get("name") or "")} for oid in removed_ids]
    if args.apply and index and removed_ids and not args.allow_large_removal:
        removal_ratio = len(removed_ids) / len(index)
        if removal_ratio > MAX_AUTOMATIC_REMOVAL_RATIO:
            raise RuntimeError(
                f"Refusing to remove {len(removed_ids)}/{len(index)} people "
                f"({removal_ratio:.1%}); this exceeds the automatic "
                f"{MAX_AUTOMATIC_REMOVAL_RATIO:.0%} safety limit. Check Feishu "
                "contact scope/API completeness, then rerun manually with "
                "--allow-large-removal if the change is intentional."
            )
    for ent in list(seq):
        if isinstance(ent, dict) and ent.get("open_id") in removed_ids:
            seq.remove(ent)
    index = {it["open_id"]: it for it in seq if isinstance(it, dict) and it.get("open_id")}

    added = updated = 0
    added_people: list[dict[str, str]] = []
    for oid, d in draft.items():
        ent = index.get(oid)
        if ent is None:
            ent = CommentedMap()
            ent["open_id"] = oid
            seq.append(ent)
            index[oid] = ent
            added += 1
            added_people.append({"open_id": oid, "name": str(d.get("name") or "")})
        else:
            updated += 1
        for f in ALWAYS_REFRESH:
            if f in d and d[f] not in (None, ""):
                upsert(ent, f, d[f])
            elif f in ent:
                # Feishu-backed fields are authoritative. An omitted latest
                # value must clear stale local org data rather than preserving it.
                ent.ca.items.pop(f, None)
                del ent[f]
        if "aliases" not in ent:
            upsert(ent, "aliases", aliases_from_name(d.get("name") or ent.get("name") or ""))
        for f in SUBJECTIVE:
            if f not in ent:
                upsert(ent, f, None)

    text = dump_sorted(yaml, doc)
    summary = {
        "added": added_people,
        "removed": removed_people,
    }

    if args.apply:
        if PEOPLE_FILE.exists():
            shutil.copy2(PEOPLE_FILE, PEOPLE_FILE.with_suffix(".yaml.bak"))
        atomic_write_private(PEOPLE_FILE, prettier_format(text, PEOPLE_FILE.name))
    elif getattr(args, "summary_only", False):
        from ruamel.yaml.comments import CommentedMap, CommentedSeq

        summary_doc = CommentedMap()
        summary_doc["generated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for key in ("added", "removed"):
            seq = CommentedSeq()
            for person in summary[key]:
                item = CommentedMap()
                item["open_id"] = person["open_id"]
                item["name"] = person["name"]
                seq.append(item)
            summary_doc[key] = seq
        buf = io.StringIO()
        yaml.dump(summary_doc, buf)
        atomic_write_private(
            MERGED_FILE,
            prettier_format(
                "# MERGE SUMMARY — dry-run only; official field refreshes are intentionally omitted.\n"
                + buf.getvalue(),
                MERGED_FILE.name,
            ),
        )
    else:
        atomic_write_private(
            MERGED_FILE,
            prettier_format(
                "# MERGE PREVIEW — objective fields from people.draft.yaml refreshed,\n"
                "# your subjective fields preserved. Re-run with --apply to write people.yaml.\n" + text,
                MERGED_FILE.name,
            ),
        )

    print(f"merged: {updated} updated, {added} new, {len(removed_ids)} departed removed", file=sys.stderr)
    print(f"summary-json: {json.dumps(summary, ensure_ascii=False, sort_keys=True)}", file=sys.stderr)
    if args.apply:
        print(f"Applied → {PEOPLE_FILE} (backup: people.yaml.bak)", file=sys.stderr)
    else:
        print(f"Preview → {MERGED_FILE}", file=sys.stderr)
        if getattr(args, "summary_only", False):
            print("Summary contains added/removed people only; official field refreshes are omitted.", file=sys.stderr)
        else:
            print("Review it, then: python scripts/pull_feishu_people.py merge --apply", file=sys.stderr)
    return summary


def cmd_sync(args):
    """Pull a complete active roster, then preview or apply its merge."""
    cmd_pull(args)
    return cmd_merge(args)


def cmd_check(args):
    """Audit people.yaml formatting; with --fix, rewrite it in canonical form."""
    if not PEOPLE_FILE.exists():
        sys.exit(f"{PEOPLE_FILE} not found.")
    yaml = make_yaml()
    original = PEOPLE_FILE.read_text(encoding="utf-8")
    doc = yaml.load(original)
    people = [e for e in (doc.get("people") or []) if isinstance(e, dict)]

    # Count deviations before normalizing, so the report names what changed.
    block_aliases, bad_order, bad_comment = [], [], []
    for ent in people:
        name = str(ent.get("name") or ent.get("open_id") or "?")
        seq = ent.get("aliases")
        if isinstance(seq, list) and not seq.fa.flow_style():
            block_aliases.append(name)
        keys = [k for k in ent if k in FIELD_ORDER]
        if keys != sorted(keys, key=FIELD_ORDER.index):
            bad_order.append(name)
        for key, comment in canonical_comments(ent).items():
            token = ent.ca.items.get(key)
            got = token[2].value.lstrip("#").strip() if token and token[2] else ""
            if got != comment and (not got or got in ALL_COMMENTS):
                bad_comment.append(f"{name}.{key}")
                break

    rewritten = prettier_format(dump_sorted(yaml, doc), PEOPLE_FILE.name)
    clean = rewritten == original

    print(f"people.yaml: {len(people)} entries", file=sys.stderr)
    for label, hits in (
        ("aliases in block form (want flow [a, b, c])", block_aliases),
        ("fields out of canonical order", bad_order),
        ("missing/incorrect trailing comment", bad_comment),
    ):
        if hits:
            shown = ", ".join(hits[:5]) + (f", … (+{len(hits) - 5})" if len(hits) > 5 else "")
            print(f"  ✗ {len(hits):3} {label}: {shown}", file=sys.stderr)
        else:
            print(f"  ✓   0 {label}", file=sys.stderr)

    if clean:
        print("Format is canonical — nothing to do.", file=sys.stderr)
        return
    if not args.fix:
        print("Formatting differs. Re-run with --fix to normalize (.bak kept).", file=sys.stderr)
        sys.exit(1)

    # Values must survive verbatim — a formatter that edits content is a bug.
    import yaml as _pyyaml

    before = _pyyaml.safe_load(original)
    after = _pyyaml.safe_load(rewritten)
    if before != after:
        sys.exit("ABORTED: normalization would change data, not just formatting.")

    shutil.copy2(PEOPLE_FILE, PEOPLE_FILE.with_suffix(".yaml.bak"))
    atomic_write_private(PEOPLE_FILE, rewritten)
    print(f"Normalized → {PEOPLE_FILE} (backup: people.yaml.bak); data verified identical.", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Sync Feishu org directory into people.yaml (pull → merge).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pull", help="fetch objective org data → people.draft.yaml (never touches production)")
    mp = sub.add_parser("merge", help="combine draft + people.yaml → people.merged.yaml (or people.yaml with --apply)")
    mp.add_argument("--apply", action="store_true", help="write the merge result into people.yaml (.bak kept)")
    mp.add_argument(
        "--summary-only",
        action="store_true",
        help="write only the added/removed roster summary (for dry-run review)",
    )
    mp.add_argument(
        "--allow-large-removal",
        action="store_true",
        help="allow applying a roster removal larger than the 20%% automatic safety limit",
    )
    sp = sub.add_parser("sync", help="pull, then merge (preview by default; --apply for nightly sync)")
    sp.add_argument("--apply", action="store_true", help="write the merge result into people.yaml (.bak kept)")
    sp.add_argument(
        "--summary-only",
        action="store_true",
        help="write only the added/removed roster summary (for dry-run review)",
    )
    sp.add_argument(
        "--allow-large-removal",
        action="store_true",
        help="allow applying a roster removal larger than the 20%% automatic safety limit",
    )
    cp = sub.add_parser("check", help="audit people.yaml formatting (exit 1 if it differs)")
    cp.add_argument("--fix", action="store_true", help="rewrite people.yaml in canonical form (.bak kept)")
    args = ap.parse_args()
    {"pull": cmd_pull, "merge": cmd_merge, "sync": cmd_sync, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    main()
