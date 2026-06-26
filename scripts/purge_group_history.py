#!/usr/bin/env python3
"""Purge Feishu **group-chat** session history from Hermes state.

Why this exists
---------------
``state.db`` has no column that distinguishes a group conversation from a
private (p2p) DM — both land under ``source='feishu'``. The ONLY trustworthy
signal for "this session belongs to a group chat" is the gateway routing key
in ``sessions/sessions.json`` whose shape is::

    agent:main:feishu:group:<chat_id>:<thread_or_msg_id>  ->  <session_id>

So this tool derives its target set *exclusively* from those ``:group:`` keys.
It never content-matches chat_ids inside messages: cron broadcasts and admin
sessions mention every chat_id (false positives) while real group sessions
often don't contain their own chat_id at all (false negatives). The trade-off:
a group session already rotated out of ``sessions.json`` is indistinguishable
from a DM and is intentionally left alone rather than risk deleting private
history.

What --execute does (the verified runbook)
------------------------------------------
1. stop the gateway (so nothing writes mid-purge)
2. cold backup: sqlite native ``.backup`` (folds the WAL) + copy sessions.json
   into ``state-snapshots/pre_group_purge_<ts>/``
3. ``SessionDB.delete_sessions`` — one transaction drops messages + sessions
   rows; the FTS5 index syncs via triggers; transcript files are unlinked
4. atomically prune the matching ``:group:`` keys from sessions.json
5. restart the gateway (only if it was running before step 1)
6. verify: target rows gone, FTS count == messages count, no group keys left

Usage
-----
    # preview only (default) — touches nothing
    python scripts/purge_group_history.py

    # actually purge every group's history
    python scripts/purge_group_history.py --execute

    # limit to specific group(s)
    python scripts/purge_group_history.py --execute --chat-id oc_xxx [--chat-id oc_yyy]

    # purge but leave gateway control to the caller
    python scripts/purge_group_history.py --execute --no-gateway-control

Must run under the hermes venv python (needs ``hermes_state`` importable):
    ~/.hermes/hermes-agent/venv/bin/python scripts/purge_group_history.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Hermes home / paths — resolved from hermes_constants, never from cwd.
# ---------------------------------------------------------------------------
try:
    from hermes_constants import get_hermes_home
except Exception as exc:  # pragma: no cover - clear guidance over a traceback
    sys.exit(
        "error: cannot import hermes_constants — run this with the hermes venv "
        f"python (~/.hermes/hermes-agent/venv/bin/python). underlying: {exc}"
    )

HOME = get_hermes_home()
STATE_DB = HOME / "state.db"
SESSIONS_DIR = HOME / "sessions"
SESSIONS_JSON = SESSIONS_DIR / "sessions.json"
GROUPS_YAML = HOME / "groups.yaml"
SNAPSHOT_ROOT = HOME / "state-snapshots"
GATEWAY_PID = HOME / "gateway.pid"

GROUP_KEY_RE = re.compile(r":group:(oc_[0-9a-zA-Z]+):")
OC_IN_YAML_RE = re.compile(r"oc_[0-9a-zA-Z]+")


# ---------------------------------------------------------------------------
# Discovery (read-only)
# ---------------------------------------------------------------------------
def load_group_routes(
    wanted_chat_ids: Set[str] | None,
) -> Tuple[Dict[str, Set[str]], List[str]]:
    """Return ({chat_id: {session_id, ...}}, [group_route_key, ...]).

    Targets are taken solely from ``:group:`` keys in sessions.json. When
    ``wanted_chat_ids`` is given, only those chat_ids are included.
    """
    if not SESSIONS_JSON.exists():
        sys.exit(f"error: {SESSIONS_JSON} not found")
    sj = json.loads(SESSIONS_JSON.read_text())

    by_chat: Dict[str, Set[str]] = {}
    keys: List[str] = []
    for key, val in sj.items():
        if key.startswith("_"):
            continue
        m = GROUP_KEY_RE.search(key)
        if not m:
            continue
        chat_id = m.group(1)
        if wanted_chat_ids and chat_id not in wanted_chat_ids:
            continue
        sid = val.get("session_id") if isinstance(val, dict) else val
        if not sid:
            continue
        by_chat.setdefault(chat_id, set()).add(sid)
        keys.append(key)
    return by_chat, keys


def yaml_chat_ids() -> Set[str]:
    """Chat ids currently registered in groups.yaml (regex, no PyYAML needed)."""
    if not GROUPS_YAML.exists():
        return set()
    ids: Set[str] = set()
    for line in GROUPS_YAML.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "chat_id" not in stripped:
            continue
        ids.update(OC_IN_YAML_RE.findall(stripped))
    return ids


def message_counts(db_path: Path, sids: Set[str]) -> Dict[str, int]:
    """Per-session message_count for the given ids (existing sessions only)."""
    if not sids:
        return {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" * len(sids))
        rows = conn.execute(
            f"SELECT id, message_count FROM sessions WHERE id IN ({placeholders})",
            tuple(sids),
        ).fetchall()
    finally:
        conn.close()
    return {sid: (mc or 0) for sid, mc in rows}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(by_chat: Dict[str, Set[str]], in_yaml: Set[str]) -> Tuple[Set[str], int]:
    """Print the per-group breakdown. Returns (all_target_sids, total_messages)."""
    all_sids: Set[str] = set()
    for sids in by_chat.values():
        all_sids |= sids
    counts = message_counts(STATE_DB, all_sids)
    existing = {s for s in all_sids if s in counts}

    print(f"hermes home : {HOME}")
    print(f"target source: sessions.json :group: routing keys (authoritative)\n")
    print(f"{'chat_id':<40} {'in groups.yaml':<14} {'sessions':<9} {'messages'}")
    print("-" * 78)
    total_msg = 0
    for chat_id, sids in sorted(by_chat.items(), key=lambda kv: -len(kv[1])):
        present = [s for s in sids if s in counts]
        msgs = sum(counts[s] for s in present)
        total_msg += msgs
        tag = "yes" if chat_id in in_yaml else "no (historical)"
        print(f"{chat_id:<40} {tag:<14} {len(present):<9} {msgs}")
    print("-" * 78)
    print(f"{'TOTAL':<40} {'':<14} {len(existing):<9} {total_msg}")
    missing = all_sids - existing
    if missing:
        print(
            f"\nnote: {len(missing)} routed session id(s) already absent from state.db "
            f"(will only have their routing key pruned): {sorted(missing)}"
        )
    return existing, total_msg


# ---------------------------------------------------------------------------
# Gateway control
# ---------------------------------------------------------------------------
def _hermes_bin() -> str:
    cand = Path(sys.executable).resolve().parent / "hermes"
    return str(cand) if cand.exists() else "hermes"


def gateway_running() -> bool:
    """True if gateway.pid points at a live process."""
    try:
        pid = json.loads(GATEWAY_PID.read_text()).get("pid")
    except Exception:
        return False
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def gateway(action: str) -> None:
    print(f"  $ hermes gateway {action}")
    subprocess.run([_hermes_bin(), "gateway", action], check=False)


# ---------------------------------------------------------------------------
# Backup + execute
# ---------------------------------------------------------------------------
def cold_backup() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = SNAPSHOT_ROOT / f"pre_group_purge_{ts}"
    dst.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(str(STATE_DB))
    bk = sqlite3.connect(str(dst / "state.db"))
    try:
        with bk:
            src.backup(bk)  # native backup folds the WAL into a consistent file
    finally:
        bk.close()
        src.close()
    shutil.copy2(SESSIONS_JSON, dst / "sessions.json")

    # integrity check on the copy
    chk = sqlite3.connect(str(dst / "state.db"))
    try:
        ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        chk.close()
    if ok != "ok":
        sys.exit(f"error: backup integrity_check returned {ok!r} — aborting before any delete")
    print(f"  backup ok -> {dst}  (integrity: {ok})")
    return dst


def prune_routing_keys(target_keys: Set[str]) -> int:
    """Atomically remove the given keys from sessions.json. Returns count removed."""
    sj = json.loads(SESSIONS_JSON.read_text())
    removed = [k for k in list(sj.keys()) if k in target_keys]
    for k in removed:
        del sj[k]
    tmp = SESSIONS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sj, ensure_ascii=False, indent=1))
    os.replace(tmp, SESSIONS_JSON)
    return len(removed)


def verify(sids: Set[str], pruned_keys: Set[str]) -> bool:
    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" * len(sids)) if sids else "''"
        left_s = (
            conn.execute(f"SELECT count(*) FROM sessions WHERE id IN ({placeholders})", tuple(sids)).fetchone()[0]
            if sids
            else 0
        )
        left_m = (
            conn.execute(f"SELECT count(*) FROM messages WHERE session_id IN ({placeholders})", tuple(sids)).fetchone()[
                0
            ]
            if sids
            else 0
        )
        n_msg = conn.execute("SELECT count(*) FROM messages").fetchone()[0]
        n_fts = conn.execute("SELECT count(*) FROM messages_fts").fetchone()[0]
    finally:
        conn.close()

    sj = json.loads(SESSIONS_JSON.read_text())
    left_keys = sum(1 for k in sj if k in pruned_keys)
    left_files = [p.name for s in sids for p in SESSIONS_DIR.glob(f"{s}*")]

    ok = left_s == 0 and left_m == 0 and n_fts == n_msg and left_keys == 0 and not left_files
    print("\nverification")
    print(f"  residual session rows : {left_s}  (want 0)")
    print(f"  residual message rows : {left_m}  (want 0)")
    print(f"  messages_fts == messages : {n_fts == n_msg}  ({n_fts} / {n_msg})")
    print(f"  residual :group: keys : {left_keys}  (want 0)")
    print(f"  residual transcripts  : {len(left_files)}  (want 0)")
    print(f"  RESULT: {'OK' if ok else 'FAILED — inspect the snapshot before retrying'}")
    return ok


def execute(by_chat: Dict[str, Set[str]], keys: List[str], control_gateway: bool) -> int:
    from hermes_state import SessionDB

    target_sids: Set[str] = set()
    for sids in by_chat.values():
        target_sids |= sids
    target_keys = set(keys)

    was_running = gateway_running()
    print("\n=== executing purge ===")
    if control_gateway:
        if was_running:
            print("stopping gateway...")
            gateway("stop")
            time.sleep(2)
        else:
            print("gateway not running — skipping stop")
    else:
        print("--no-gateway-control: assuming caller has stopped the gateway")

    print("backing up...")
    cold_backup()

    print("deleting sessions...")
    db = SessionDB()
    try:
        n_deleted = db.delete_sessions(sorted(target_sids), sessions_dir=SESSIONS_DIR)
    finally:
        db.close()
    print(f"  delete_sessions removed {n_deleted} session row(s)")

    print("pruning routing keys...")
    n_keys = prune_routing_keys(target_keys)
    print(f"  pruned {n_keys} :group: key(s) from sessions.json")

    if control_gateway and was_running:
        print("restarting gateway...")
        gateway("start")

    ok = verify(target_sids, target_keys)
    return 0 if ok else 1


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Purge Feishu group-chat session history (dry-run by default).",
    )
    ap.add_argument("--execute", action="store_true", help="actually purge (default is a read-only preview)")
    ap.add_argument(
        "--chat-id",
        action="append",
        default=None,
        metavar="oc_xxx",
        help="limit to this group chat_id (repeatable); default = all groups",
    )
    ap.add_argument(
        "--no-gateway-control", action="store_true", help="do not stop/start the gateway; caller manages it"
    )
    args = ap.parse_args()

    wanted = set(args.chat_id) if args.chat_id else None
    by_chat, keys = load_group_routes(wanted)

    if not by_chat:
        scope = f" matching {sorted(wanted)}" if wanted else ""
        print(f"no group sessions found{scope} in {SESSIONS_JSON}. nothing to do.")
        return 0

    in_yaml = yaml_chat_ids()
    print_report(by_chat, in_yaml)

    if not args.execute:
        print("\n(dry-run) nothing changed. re-run with --execute to purge.")
        return 0

    return execute(by_chat, keys, control_gateway=not args.no_gateway_control)


if __name__ == "__main__":
    raise SystemExit(main())
