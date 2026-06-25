#!/usr/bin/env python3
"""Build and send Chen's nightly daily report, then greet known Feishu groups.

Normal cron runs are intentionally silent on stdout. With Hermes cron
``--no-agent``, empty stdout means no extra delivery message; the only user
visible side effects are the Feishu report submission and group messages.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - macOS system Python is new enough.
    ZoneInfo = None

HERMES_HOME = Path.home() / ".hermes"
STATE_DB = HERMES_HOME / "state.db"
FEISHU_DOCS_SCRIPTS = HERMES_HOME / "my-skills/productivity/feishu-docs/scripts"
FEISHU_GROUPS_SKILL = HERMES_HOME / "my-skills/productivity/feishu-groups/SKILL.md"
REPORT_PROJECT = Path("/Users/chenzhou/Documents/WhaleDocs/organization/Reporting_2026Q2")
WORK_DIR = HERMES_HOME / "tmp/nightly_report"
STATE_PATH = WORK_DIR / "state.json"
LOCK_PATH = WORK_DIR / "nightly_report.lock"
HERMES_BIN = Path("/Users/chenzhou/.local/bin/hermes")
UV_BIN = Path("/opt/homebrew/bin/uv")

sys.path.insert(0, str(FEISHU_DOCS_SCRIPTS))
import feishu_common  # noqa: E402

CHAT_ID_RE = re.compile(r"`(oc_[A-Za-z0-9_]+)`")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.S)

TZ = ZoneInfo("Asia/Shanghai") if ZoneInfo else dt.timezone(dt.timedelta(hours=8))
MAX_CONTEXT_CHARS = 90000
MAX_MESSAGE_CHARS = 1800
TARGET_REPORT_CHARS = 200
MAX_REPORT_CHARS = 260
REPORT_SIGNATURE = "—— By 琛哥的赛博助手「Gödel」"


def log(message: str) -> None:
    print(f"[nightly] {message}", file=sys.stderr, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("dryrun", "dry-run"), help=argparse.SUPPRESS)
    parser.add_argument("--date", help="Local date to process, YYYY-MM-DD. Defaults to today.")
    parser.add_argument(
        "--dry-run",
        "--dryrun",
        action="store_true",
        help="Send the prepared report and greeting preview to the main Feishu chat. No report submit, no group send.",
    )
    parser.add_argument("--skip-report", action="store_true", help="Do not submit the Feishu daily report.")
    parser.add_argument("--skip-greeting", action="store_true", help="Do not send the nightly group greeting.")
    parser.add_argument(
        "--force-report", action="store_true", help="Submit the report even if today's local success marker exists."
    )
    parser.add_argument(
        "--force-greeting", action="store_true", help="Send the greeting even if today's local success marker exists."
    )
    parser.add_argument(
        "--force-dry-run",
        "--force-dryrun",
        action="store_true",
        help="Send a dry-run preview even if one was already sent today.",
    )
    args = parser.parse_args()
    if args.mode in {"dryrun", "dry-run"} or args.force_dry_run:
        args.dry_run = True
    return args


def local_day(value: str | None) -> dt.date:
    if value:
        return dt.date.fromisoformat(value)
    return dt.datetime.now(TZ).date()


def day_bounds(day: dt.date) -> tuple[float, float]:
    start = dt.datetime.combine(day, dt.time.min, TZ)
    end = start + dt.timedelta(days=1)
    return start.timestamp(), end.timestamp()


def cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text or ""))


def report_too_long(text: str) -> bool:
    return cjk_len(text) > MAX_REPORT_CHARS or len(text) > MAX_REPORT_CHARS


def load_group_ids(path: Path = FEISHU_GROUPS_SKILL) -> list[str]:
    """Read chat_ids from the Known Groups table in the feishu-groups skill."""
    in_known_groups = False
    group_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_known_groups = line.strip() == "## Known Groups"
            continue
        if not in_known_groups or not line.startswith("|"):
            continue
        match = CHAT_ID_RE.search(line)
        if match and match.group(1) not in group_ids:
            group_ids.append(match.group(1))
    if not group_ids:
        raise RuntimeError(f"No Feishu group chat_ids found in {path}")
    return group_ids


def send_message(token: str, chat_id: str, text: str) -> dict[str, Any]:
    url = f"{feishu_common.API}/im/v1/messages?receive_id_type=chat_id"
    payload = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }
    res = feishu_common.do_req(token, url, method="POST", payload=payload)
    if res.get("code", 0):
        raise RuntimeError(f"Failed to send to {chat_id}: {res}")
    log(f"Sent Feishu text to {chat_id}: {res}")
    return res


def trim_message(content: str) -> str:
    content = re.sub(r"\s+", " ", content or "").strip()
    if len(content) <= MAX_MESSAGE_CHARS:
        return content
    return f"{content[:MAX_MESSAGE_CHARS]}..."


def read_sessions_from_db(day: dt.date) -> str:
    start_ts, end_ts = day_bounds(day)
    if not STATE_DB.exists():
        return ""
    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS session_id,
                COALESCE(s.source, '') AS source,
                COALESCE(s.title, '') AS title,
                m.role AS role,
                COALESCE(m.content, '') AS content,
                m.timestamp AS timestamp
            FROM messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE m.timestamp >= ?
              AND m.timestamp < ?
              AND m.active = 1
              AND m.role IN ('user', 'assistant')
              AND COALESCE(m.content, '') <> ''
              AND COALESCE(s.source, '') NOT IN ('cron', 'nightly-report')
            ORDER BY m.timestamp ASC, m.id ASC
            """,
            (start_ts, end_ts),
        ).fetchall()
    finally:
        conn.close()
    return format_session_rows(rows)


def read_sessions_from_snapshots(day: dt.date) -> str:
    """Fallback for older Hermes homes that only have JSON/JSONL snapshots."""
    sessions_dir = HERMES_HOME / "sessions"
    if not sessions_dir.exists():
        return ""
    day_prefix = day.strftime("%Y%m%d")
    blocks: list[str] = []
    for path in sorted(sessions_dir.glob(f"*{day_prefix}*")):
        if path.name == "sessions.json" or path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            if path.suffix == ".jsonl":
                messages = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                data = json.loads(path.read_text(encoding="utf-8"))
                messages = data.get("messages") or data.get("conversation_history") or []
        except Exception as exc:  # noqa: BLE001
            log(f"Skipping unreadable session snapshot {path}: {exc}")
            continue
        for item in messages:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                blocks.append(f"[{path.name}] {role}: {trim_message(content)}")
    return "\n".join(blocks)


def format_session_rows(rows: list[sqlite3.Row]) -> str:
    blocks: list[str] = []
    current_key: tuple[str, str, str] | None = None
    current_len = 0
    for row in rows:
        key = (row["session_id"], row["source"], row["title"])
        if key != current_key:
            title = row["title"] or "(untitled)"
            blocks.append(f"\n## Session {row['session_id']} | source={row['source']} | title={title}")
            current_key = key
        ts = dt.datetime.fromtimestamp(float(row["timestamp"]), TZ).strftime("%H:%M:%S")
        content = trim_message(row["content"])
        blocks.append(f"[{ts}] {row['role']}: {content}")
        current_len += len(content)
        if current_len >= MAX_CONTEXT_CHARS:
            blocks.append("\n[context truncated at daily size limit]")
            break
    return "\n".join(blocks).strip()


def read_daily_sessions(day: dt.date) -> str:
    content = read_sessions_from_db(day)
    if not content:
        content = read_sessions_from_snapshots(day)
    if not content:
        content = "当天没有读取到可用于日报的 Hermes 会话内容。"
    return content


def build_generation_prompt(day: dt.date, session_text: str) -> str:
    return textwrap.dedent(
        f"""
        你是琛哥的日报代笔，只根据下面的 Hermes 当天会话记录生成内容，不要调用工具，不要补充外部信息。

        目标：
        1. 提取工作的部分，删除玩笑、吐槽、人身攻击、不正经内容。
        2. 业务范围限定：只保留 SpaceSight（摄像头 / 计算机视觉）产品线、且由琛哥本人负责或推进的工作；口径符合摄像头业务产品线 leader，重点围绕客流、巡检、热力图、动线、轨迹、图片、视频、大模型、小模型、报价、成本、私有化、（门店）汽车售后、算法/数据/交付方案、问题讨论与推进计划。
        3. 输出飞书日报两个字段：今日完成、明日计划。
        4. 再输出一段群发晚安词，符合“琛哥的赛博助手 Gödel”人设；每天可以有新花样，但必须按顺序自然包含且不要重复表达：先问好并自我介绍，再说明已经帮琛哥发好日报，最后说大家工作辛苦了并道晚安祝愿。

        范围红线（不属于 SpaceSight 的内容必须剔除，不得写进今日完成/明日计划）：
        - 其它产品线/团队的客户与项目，尤其是 Echo / 语音工牌 / 声纹识别 / 语义聚合 / 视频质检(QA/QC) / Alivia 等 zy 团队的业务（例如资生堂、理想汽车这类语音工牌 POC）。
        - 琛哥只是旁观、吃瓜、分析他人团队动态或八卦的内容，而非他本人推进的工作。
        - 飞书截图里的“产品线: SpaceSight”等系统标签可能是错标，要以对话中确认的实际业务归属为准；若对话已纠正归属（如“其实是 Echo/zy 的业务、不是你的地盘”），以纠正后的结论为准。
        - 拿不准是否属于 SpaceSight 时，宁可不写进日报。

        严格格式：
        - 只输出一个 JSON 对象，不要 Markdown，不要解释。
        - JSON schema: {{"today":"1. ...\\n2. ...","plan":"1. ...\\n2. ...","goodnight":"..."}}
        - today 和 plan 都必须是带序号的换行分点文本。
        - today 和 plan 目标各自控制在 {TARGET_REPORT_CHARS} 字左右，略超可以；只有明显超过 {MAX_REPORT_CHARS} 字才需要压缩。
        - 不要出现“骂、开除、喷、吹牛、老登、锅、完蛋”等玩笑或攻击性表达。
        - 不要编造客户名称之外的新事实；可做适度职业化概括。

        本地日期：{day.isoformat()}

        Hermes 会话记录：
        {session_text}
        """
    ).strip()


def run_hermes_generation(prompt: str) -> dict[str, str]:
    env = os.environ.copy()
    env["HERMES_SESSION_SOURCE"] = "nightly-report"
    hermes_bin = str(HERMES_BIN if HERMES_BIN.exists() else shutil.which("hermes") or "hermes")
    cmd = [hermes_bin, "--ignore-rules", "-t", "search", "-z", prompt]
    res = subprocess.run(
        cmd,
        cwd=str(HERMES_HOME),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=420,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Hermes generation failed ({res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
    return parse_generation_json(res.stdout)


def parse_generation_json(raw: str) -> dict[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = JSON_OBJECT_RE.search(text)
    if not match:
        raise RuntimeError(f"Hermes generation did not return JSON: {raw[:500]}")
    data = json.loads(match.group(0))
    result = {
        "today": str(data.get("today", "")).strip(),
        "plan": str(data.get("plan", "")).strip(),
        "goodnight": str(data.get("goodnight", "")).strip(),
    }
    if not all(result.values()):
        raise RuntimeError(f"Hermes generation missed required fields: {data}")
    return normalize_generation(result)


def normalize_generation(data: dict[str, str]) -> dict[str, str]:
    return {
        "today": append_report_signature(normalize_report_section(data["today"], "今日完成")),
        "plan": append_report_signature(normalize_report_section(data["plan"], "明日计划")),
        "goodnight": ensure_goodnight_requirements(data["goodnight"]),
    }


def append_report_signature(section: str) -> str:
    return f"{section}\n\n{REPORT_SIGNATURE}"


def normalize_report_section(text: str, label: str) -> str:
    raw_lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    lines: list[str] = []
    for line in raw_lines:
        line = re.sub(r"^\d+[\.、)]\s*", "", line).strip()
        line = re.sub(r"^[一二三四五六七八九十]+[、.]\s*", "", line).strip()
        if line:
            lines.append(line)
    if not lines:
        lines = [f"完成{label}梳理，聚焦客流、巡检与摄像头方案推进。"]

    numbered: list[str] = []
    for idx, line in enumerate(lines[:4], 1):
        numbered.append(f"{idx}. {line}")
        candidate = "\n".join(numbered)
        if report_too_long(candidate):
            numbered.pop()
            break
    if not numbered:
        numbered = [f"1. {truncate_report_text(lines[0], MAX_REPORT_CHARS - 4)}"]

    section = "\n".join(numbered)
    while report_too_long(section) and numbered:
        last = numbered.pop()
        existing = "\n".join(numbered)
        remaining = max(20, MAX_REPORT_CHARS - max(cjk_len(existing), len(existing)) - 4)
        numbered.append(truncate_numbered_line(last, remaining))
        section = "\n".join(numbered)
        if not report_too_long(section):
            break
        numbered.pop()
        section = "\n".join(numbered)
    return section.strip()


def truncate_numbered_line(line: str, max_chars: int) -> str:
    prefix_match = re.match(r"^(\d+\.\s*)(.*)$", line)
    if not prefix_match:
        return truncate_report_text(line, max_chars)
    prefix, body = prefix_match.groups()
    return prefix + truncate_report_text(body, max_chars)


def truncate_report_text(text: str, max_chars: int) -> str:
    count = 0
    out: list[str] = []
    for char in text:
        if CJK_RE.match(char):
            count += 1
        if count > max_chars or len(out) >= max_chars:
            break
        out.append(char)
    return "".join(out).rstrip("，、；。,. ") + "。"


def ensure_goodnight_requirements(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text).strip()
    text = dedupe_sentences(text)
    text = dedupe_report_done_sentences(text)
    if not goodnight_has_required_order(text):
        return default_goodnight()
    return text


def default_goodnight() -> str:
    return "大家好，我是琛哥的赛博助手 Gödel。今天的日报已经帮琛哥发好了。大家今天工作辛苦了，晚安，祝大家好梦。"


def goodnight_has_required_order(text: str) -> bool:
    intro_pos = first_index(text, ("Gödel", "赛博助手"))
    report_pos = first_index(text, ("日报",))
    work_pos = first_index(text, ("辛苦",))
    night_pos = first_index(text, ("晚安",))
    if min(intro_pos, report_pos, work_pos, night_pos) < 0:
        return False
    if not any(word in text for word in report_done_words()):
        return False
    return intro_pos <= report_pos <= min(work_pos, night_pos)


def first_index(text: str, needles: tuple[str, ...]) -> int:
    indexes = [text.find(needle) for needle in needles if needle in text]
    return min(indexes) if indexes else -1


def report_done_words() -> tuple[str, ...]:
    return ("发好", "提交", "发完", "发送", "送出", "发出", "整理完", "完成", "处理完")


def dedupe_report_done_sentences(text: str) -> str:
    sentences = split_sentences(text)
    report_indexes = [
        idx
        for idx, sentence in enumerate(sentences)
        if "日报" in sentence and any(word in sentence for word in report_done_words())
    ]
    if len(report_indexes) <= 1:
        return text

    generic = "今天的日报已经帮琛哥发好了"

    def score(idx: int) -> tuple[int, int]:
        sentence = sentences[idx]
        return (0 if generic in sentence else 1, len(sentence))

    keep = max(report_indexes, key=score)
    filtered = [sentence for idx, sentence in enumerate(sentences) if idx == keep or idx not in report_indexes]
    return " ".join(filtered).strip()


def dedupe_sentences(text: str) -> str:
    parts = split_sentences(text)
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        key = re.sub(r"[，,。！？!?.；;：:\\s]", "", part)
        if key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return " ".join(unique).strip()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？!?.])\s*", text) if part.strip()]


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"reports": {}, "greetings": {}, "dry_runs": {}}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log(f"State file unreadable, starting fresh: {exc}")
        return {"reports": {}, "greetings": {}, "dry_runs": {}}
    data.setdefault("reports", {})
    data.setdefault("greetings", {})
    data.setdefault("dry_runs", {})
    return data


def save_state(data: dict[str, Any]) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def write_artifacts(day: dt.date, session_text: str, draft: dict[str, str]) -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    prefix = WORK_DIR / day.isoformat()
    (prefix.with_suffix(".sessions.md")).write_text(session_text + "\n", encoding="utf-8")
    (prefix.with_suffix(".draft.json")).write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def submit_report(day: dt.date, draft: dict[str, str]) -> str:
    uv_bin = str(UV_BIN if UV_BIN.exists() else shutil.which("uv") or "uv")
    cmd = [uv_bin, "run", "python", "report.py", "--today", draft["today"], "--plan", draft["plan"]]
    log(f"Submitting Feishu daily report for {day.isoformat()}")
    res = subprocess.run(
        cmd,
        cwd=str(REPORT_PROJECT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=600,
    )
    output_path = WORK_DIR / f"{day.isoformat()}.report-submit.log"
    output_path.write_text(res.stdout or "", encoding="utf-8")
    if res.returncode == 4:
        # rc=4: the report was submitted but report.py could not detect the
        # success toast. Treat as submitted (avoid duplicate re-submits and do
        # not block the greeting); flag for manual verification.
        log(f"Report submitted but success toast not detected (rc=4); treating as submitted. Verify: {output_path}")
        return str(output_path)
    if res.returncode != 0:
        raise RuntimeError(f"Report submit failed ({res.returncode}); see {output_path}")
    log(f"Report submitted; log saved to {output_path}")
    return str(output_path)


def send_greetings(day: dt.date, text: str) -> list[dict[str, Any]]:
    token = feishu_common.get_tenant_token()
    results = []
    for group_id in load_group_ids():
        results.append({"group_id": group_id, "response": send_message(token, group_id, text)})
    (WORK_DIR / f"{day.isoformat()}.greeting-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return results


def resolve_main_chat_id() -> str:
    for key in ("HERMES_NIGHTLY_DRY_RUN_CHAT_ID", "FEISHU_NIGHTLY_DRY_RUN_CHAT_ID"):
        value = os.getenv(key, "").strip()
        if value.startswith("oc_"):
            return value

    jobs_path = HERMES_HOME / "cron/jobs.json"
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
        for job in data.get("jobs", []):
            if job.get("script") == "nightly_greeting.py" or job.get("id") == "ccb273ada501":
                chat_id = ((job.get("origin") or {}).get("chat_id") or "").strip()
                if chat_id.startswith("oc_"):
                    return chat_id
    except Exception as exc:  # noqa: BLE001
        log(f"Could not resolve dry-run chat from cron jobs: {exc}")

    sandbox_cfg = HERMES_HOME / "plugins/sandbox/config.yaml"
    try:
        match = re.search(r"^\s*-\s*(oc_[A-Za-z0-9_]+)\s*$", sandbox_cfg.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    except Exception as exc:  # noqa: BLE001
        log(f"Could not resolve dry-run chat from sandbox config: {exc}")

    raise RuntimeError("Cannot resolve main Feishu chat_id for dry-run preview")


def draft_hash(draft: dict[str, str]) -> str:
    raw = json.dumps(draft, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def preview_message(day: dt.date, draft: dict[str, str]) -> str:
    return (
        textwrap.dedent(
            f"""
        【日报 Dry Run】{day.isoformat()}
        本次仅预览：不会提交飞书日报，也不会群发晚安词。

        今日完成:
        {draft["today"]}

        明日计划:
        {draft["plan"]}

        晚安词:
        {draft["goodnight"]}
        """
        )
        .strip()
        .replace("\n        ", "\n")
    )


def send_dry_run_preview(day: dt.date, draft: dict[str, str], state: dict[str, Any]) -> None:
    chat_id = resolve_main_chat_id()
    token = feishu_common.get_tenant_token()
    response = send_message(token, chat_id, preview_message(day, draft))
    day_key = day.isoformat()
    state["dry_runs"][day_key] = {
        "sent_at": dt.datetime.now(TZ).isoformat(),
        "chat_id": chat_id,
        "draft_hash": draft_hash(draft),
        "response": response,
    }
    save_state(state)


@contextlib.contextmanager
def nightly_lock():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Another nightly report run is active; exiting silently.")
            yield False
            return
        yield True


def run(args: argparse.Namespace) -> str | None:
    day = local_day(args.date)
    with nightly_lock() as acquired:
        if not acquired:
            return None

        state = load_state()
        day_key = day.isoformat()
        if args.dry_run and state["dry_runs"].get(day_key) and not args.force_dry_run:
            log(f"Dry-run preview already sent for {day_key}; exiting silently.")
            return None

        report_done = bool(state["reports"].get(day_key)) or args.skip_report
        greeting_done = bool(state["greetings"].get(day_key)) or args.skip_greeting
        if not args.dry_run and report_done and greeting_done and not args.force_report and not args.force_greeting:
            log(f"Nightly report and greeting already completed for {day_key}; exiting silently.")
            return None

        session_text = read_daily_sessions(day)
        draft = run_hermes_generation(build_generation_prompt(day, session_text))
        write_artifacts(day, session_text, draft)

        if args.dry_run:
            send_dry_run_preview(day, draft, state)
            return None

        # Report and greeting are decoupled: a failure in one must not block the
        # other. Errors are collected and re-raised at the end so the cron run is
        # still marked as failed for visibility.
        errors: list[str] = []

        if not args.skip_report:
            if state["reports"].get(day_key) and not args.force_report:
                log(f"Report already submitted for {day_key}; skipping report submit.")
            else:
                try:
                    report_log = submit_report(day, draft)
                    state["reports"][day_key] = {
                        "submitted_at": dt.datetime.now(TZ).isoformat(),
                        "report_log": report_log,
                        "today": draft["today"],
                        "plan": draft["plan"],
                    }
                    save_state(state)
                except Exception as exc:  # noqa: BLE001
                    log(f"Report submit failed (continuing to greeting): {exc}")
                    errors.append(f"report: {exc}")
        else:
            log("Report submit skipped by flag.")

        if not args.skip_greeting:
            if state["greetings"].get(day_key) and not args.force_greeting:
                log(f"Greeting already sent for {day_key}; skipping group send.")
            else:
                try:
                    results = send_greetings(day, draft["goodnight"])
                    state["greetings"][day_key] = {
                        "sent_at": dt.datetime.now(TZ).isoformat(),
                        "groups": [item["group_id"] for item in results],
                    }
                    save_state(state)
                except Exception as exc:  # noqa: BLE001
                    log(f"Greeting send failed: {exc}")
                    errors.append(f"greeting: {exc}")
        else:
            log("Greeting skipped by flag.")

        if errors:
            raise RuntimeError("; ".join(errors))
    return None


def main() -> int:
    args = parse_args()
    with contextlib.redirect_stdout(sys.stderr):
        run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
