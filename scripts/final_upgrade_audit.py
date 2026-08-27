#!/usr/bin/env python3
"""Run the single authoritative Hermes post-upgrade audit.

This entrypoint intentionally runs after the last reconcile. It executes the
canonical patched-file test suite with retries disabled, per-PATCH evidence
matrix with fresh registered probe receipts, documentation/schema checks,
post-test replay closure, final runtime/plugin identity verification, and the
final recoverable cleanup.
Output is one JSON object suitable for the final report or a post-commit
verification step.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import test_patch_evidence as patch_evidence

ROOT = Path(__file__).resolve().parents[1]
INNER = ROOT / "hermes-agent"
UPDATE = ROOT / "hermes-update.sh"
EVIDENCE = ROOT / "scripts/test_patch_evidence.py"
CLEANUP = ROOT / "scripts/cleanup_transient_artifacts.py"
CLEANUP_POLICY = ROOT / "scripts/cleanup_policy.json"
WIKI_LINT = ROOT / "scripts/wiki_lint.py"
_ALLOWED_REVIEWED_INNER_DIRTY = {"package-lock.json": " M"}


class FinalAuditError(RuntimeError):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step


def _run(
    step: str,
    argv: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        tail = f"{result.stdout[-2000:]}{result.stderr[-2000:]}".strip()
        raise FinalAuditError(step, f"command failed ({result.returncode}): {' '.join(argv)}\n{tail}")
    return result


def _patched_files() -> list[str]:
    result = _run("patched-files", ["bash", str(UPDATE), "--print-patched-files"])
    files = [line for line in result.stdout.splitlines() if line]
    if not files:
        raise FinalAuditError("patched-files", "PATCHED_FILES is empty")
    return files


def _patched_tests() -> list[str]:
    result = _run("patched-tests", ["bash", str(UPDATE), "--print-patched-tests"])
    files = [line for line in result.stdout.splitlines() if line]
    if not files:
        raise FinalAuditError("patched-tests", "PATCH_TESTS is empty")
    return files


def _run_canonical_patch_tests(test_files: list[str]) -> dict[str, int]:
    result = _run(
        "canonical-patch-tests",
        [str(INNER / "scripts/run_tests.sh"), "--file-retries", "0", *test_files],
        cwd=INNER,
        timeout=900,
    )
    if re.search(r"(?:^|\n).*FLAKY", result.stdout):
        raise FinalAuditError(
            "canonical-patch-tests",
            "canonical runner reported a pass-on-retry flake",
        )
    match = re.search(
        r"=== Summary: (\d+) files, (\d+) tests passed, (\d+) failed(?:, (\d+) skipped)?",
        result.stdout,
    )
    if not match:
        raise FinalAuditError("canonical-patch-tests", "canonical runner summary was not found")
    files, passed, failed, skipped = (int(value or 0) for value in match.groups())
    if files != len(test_files) or failed:
        raise FinalAuditError(
            "canonical-patch-tests",
            f"unexpected result: files={files}/{len(test_files)} passed={passed} failed={failed} skipped={skipped}",
        )
    return {"files": files, "passed": passed, "failed": failed, "skipped": skipped}


def _validate_canonical_coverage(canonical: dict[str, int], evidence: dict[str, object]) -> None:
    evidence_files = int(evidence.get("files") or 0)
    evidence_collected = int(evidence.get("collected") or 0)
    completed = canonical["passed"] + canonical["skipped"]
    if canonical["files"] != evidence_files or completed != evidence_collected:
        raise FinalAuditError(
            "canonical-patch-tests",
            "canonical results do not cover the full collected PATCH suite: "
            f"files={canonical['files']}/{evidence_files} "
            f"completed={completed}/{evidence_collected}",
        )


def _markdown_table_summary(row: str) -> str:
    """Return semantic summary content, ignoring formatter alignment padding."""
    cells = row.split("|")
    return cells[3].strip() if len(cells) >= 5 else ""


def _current_week_readme_rows(readme: str, today: date) -> list[str]:
    """Return version-table rows belonging to today's ISO week."""
    current_iso = today.isocalendar()
    current_key = (current_iso.year, current_iso.week)
    rows: list[str] = []
    for line in readme.splitlines():
        match = re.match(r"^\|\s*v[^|]*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", line)
        if match is None:
            continue
        row_iso = date.fromisoformat(match.group(1)).isocalendar()
        if (row_iso.year, row_iso.week) == current_key:
            rows.append(line)
    return rows


def _validate_absorption_matrix(patch_records: list[dict[str, object]], summary_text: str) -> dict[str, int]:
    pairs = re.findall(
        r"`(PATCH-[A-Z0-9-]+)`=(未吸收|部分吸收|完全吸收)",
        summary_text,
    )
    seen: dict[str, str] = {}
    duplicates: set[str] = set()
    for patch_id, verdict in pairs:
        if patch_id in seen:
            duplicates.add(patch_id)
        seen[patch_id] = verdict
    if duplicates:
        raise FinalAuditError(
            "derived-docs",
            f"duplicate PATCH absorption verdicts: {sorted(duplicates)}",
        )

    overlapping = {str(record.get("id")): record for record in patch_records if record.get("upstream_overlap")}
    missing = sorted(set(overlapping) - set(seen))
    extra = sorted(set(seen) - set(overlapping))
    if missing or extra:
        raise FinalAuditError(
            "derived-docs",
            f"PATCH absorption matrix drift: missing={missing} extra={extra}",
        )
    invalid = {
        patch_id: verdict
        for patch_id, verdict in seen.items()
        if (overlapping[patch_id].get("lifecycle") == "active" and verdict == "完全吸收")
        or (overlapping[patch_id].get("lifecycle") == "archived" and verdict != "完全吸收")
    }
    if invalid:
        raise FinalAuditError(
            "derived-docs",
            f"PATCH absorption verdict conflicts with lifecycle: {invalid}",
        )

    no_overlap_match = re.search(r"无路径相交=(\d+)", summary_text)
    active_no_overlap = sum(
        1 for record in patch_records if record.get("lifecycle") == "active" and not record.get("upstream_overlap")
    )
    if no_overlap_match is None or int(no_overlap_match.group(1)) != active_no_overlap:
        reported = int(no_overlap_match.group(1)) if no_overlap_match else None
        raise FinalAuditError(
            "derived-docs",
            f"no-overlap active PATCH count drift: reported={reported} actual={active_no_overlap}",
        )
    return {
        "overlap_verdicts": len(seen),
        "active_no_overlap": active_no_overlap,
    }


def _validate_evidence_upgrade_range(patch_records: list[dict[str, object]], current_head: str) -> dict[str, str]:
    ranges = {
        (
            str(record.get("upgrade_range", {}).get("old_sha") or ""),
            str(record.get("upgrade_range", {}).get("new_sha") or ""),
        )
        for record in patch_records
    }
    if len(ranges) != 1:
        raise FinalAuditError(
            "derived-docs",
            f"PATCH evidence does not have one consistent upgrade range: {sorted(ranges)}",
        )
    old_sha, new_sha = next(iter(ranges))
    if not re.fullmatch(r"[0-9a-f]{40}", old_sha) or new_sha != current_head:
        raise FinalAuditError(
            "derived-docs",
            f"PATCH evidence upgrade range is stale or invalid: {old_sha!r} -> {new_sha!r}, HEAD={current_head}",
        )
    return {"old_sha": old_sha, "new_sha": new_sha}


def _validate_patch_count_claims(
    patch_records: list[dict[str, object]],
    patches_text: str,
    readme_text: str,
    summary_text: str,
) -> dict[str, int]:
    active = sum(record.get("lifecycle") == "active" for record in patch_records)
    archived = sum(record.get("lifecycle") == "archived" for record in patch_records)
    engineering = sum(
        record.get("lifecycle") == "active"
        and record.get("evidence_type") not in {"runtime_contract", "external_verifier"}
        for record in patch_records
    )
    claims = {
        "PATCHES active": re.search(r"当前共 (\d+) 个语义补丁", patches_text),
        "PATCHES engineering": re.search(r"(\d+) 个工程内补丁", patches_text),
        "README active": re.search(r"维护 (\d+) 个按职责命名的活跃语义补丁", readme_text),
        "README engineering": re.search(r"活跃语义补丁：(\d+) 个工程内补丁", readme_text),
        "summary active/archive": re.search(r"终态为 (\d+) active \+ (\d+) Archive", summary_text),
    }
    missing = [label for label, match in claims.items() if match is None]
    if missing:
        raise FinalAuditError("derived-docs", f"PATCH count claims are missing: {missing}")
    observed = {
        "PATCHES active": int(claims["PATCHES active"].group(1)),
        "PATCHES engineering": int(claims["PATCHES engineering"].group(1)),
        "README active": int(claims["README active"].group(1)),
        "README engineering": int(claims["README engineering"].group(1)),
        "summary active": int(claims["summary active/archive"].group(1)),
        "summary archived": int(claims["summary active/archive"].group(2)),
    }
    expected = {
        "PATCHES active": active,
        "PATCHES engineering": engineering,
        "README active": active,
        "README engineering": engineering,
        "summary active": active,
        "summary archived": archived,
    }
    if observed != expected:
        raise FinalAuditError(
            "derived-docs",
            f"PATCH count claims drift: observed={observed} expected={expected}",
        )
    return {"active": active, "archived": archived, "engineering": engineering}


def _validate_documented_regression_counts(
    canonical: dict[str, int],
    patch_records: list[dict[str, object]],
    readme_summary: str,
    patch_summary: str,
) -> dict[str, int]:
    pattern = re.compile(
        r"(\d+)\s+files\s*/\s*\*{0,2}(\d+)\s+passed\s*/\s*"
        r"(\d+)\s+failed\s*/\s*(\d+)\s+skipped\*{0,2}"
    )
    expected = (
        canonical["files"],
        canonical["passed"],
        canonical["failed"],
        canonical["skipped"],
    )
    for label, text in (("README", readme_summary), ("PATCHES", patch_summary)):
        match = pattern.search(text)
        observed = tuple(int(value) for value in match.groups()) if match else None
        if observed != expected:
            raise FinalAuditError(
                "derived-docs",
                f"{label} canonical test count drift: observed={observed} expected={expected}",
            )

    evidence_matches = re.findall(r"(\d+)/(\d+)\s+full PATCH evidence", patch_summary)
    expected_evidence = len(patch_records)
    if len(evidence_matches) != 1 or tuple(map(int, evidence_matches[0])) != (
        expected_evidence,
        expected_evidence,
    ):
        raise FinalAuditError(
            "derived-docs",
            f"PATCHES full evidence count drift: observed={evidence_matches} expected={expected_evidence}",
        )
    return {
        "files": canonical["files"],
        "passed": canonical["passed"],
        "failed": canonical["failed"],
        "skipped": canonical["skipped"],
        "patch_evidence": expected_evidence,
    }


def _validate_documented_gate_counts(
    script_text: str,
    readme_summary: str,
    patch_summary: str,
) -> dict[str, int]:
    gate_region = script_text.split("# -- 8b.", 1)[1].split("# -- 8c.", 1)[0]
    expected = (
        len(set(re.findall(r"^(_[A-Z0-9_]+_PATCH_OK)=false$", gate_region, re.MULTILINE))),
        len(set(re.findall(r"^(_ARCHIVED_[A-Z0-9_]+_OK)=false$", gate_region, re.MULTILINE))),
    )
    pattern = re.compile(r"(\d+) active \+ (\d+) archived gates")
    for label, text in (("README", readme_summary), ("PATCHES", patch_summary)):
        match = pattern.search(text)
        observed = tuple(int(value) for value in match.groups()) if match else None
        if observed != expected:
            raise FinalAuditError(
                "derived-docs",
                f"{label} Step 8b gate count drift: observed={observed} expected={expected}",
            )
    return {"active": expected[0], "archived": expected[1]}


def _derived_checks(
    patched_files: list[str],
    evidence: dict[str, object],
    canonical: dict[str, int],
) -> dict[str, object]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    patches = (ROOT / "patches/PATCHES.md").read_text(encoding="utf-8")
    playbook = (ROOT / "hermes-update.md").read_text(encoding="utf-8")
    script = UPDATE.read_text(encoding="utf-8")

    days = re.findall(r"(?m)^\|\s*v[^|]*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", readme)
    weeks = [f"{(iso := date.fromisoformat(day).isocalendar()).year}-W{iso.week:02d}" for day in days]
    duplicates = {week: count for week, count in Counter(weeks).items() if count > 1}
    if duplicates:
        raise FinalAuditError("derived-docs", f"duplicate README ISO weeks: {duplicates}")
    init_text = (INNER / "hermes_cli/__init__.py").read_text(encoding="utf-8")
    version_match = re.search(r'^__version__\s*=\s*"([^"]+)"', init_text, re.MULTILINE)
    if not version_match:
        raise FinalAuditError("derived-docs", "could not read current Hermes version")
    current_version = version_match.group(1)
    current_rows = _current_week_readme_rows(readme, date.today())
    current_summary = _markdown_table_summary(current_rows[0]) if current_rows else ""
    if len(current_rows) != 1 or not current_summary or len(current_summary) > 1500:
        raise FinalAuditError(
            "derived-docs",
            f"current README row count/summary length invalid: count={len(current_rows)} length={len(current_summary)}",
        )
    if not current_rows[0].startswith(f"| v{current_version}"):
        raise FinalAuditError(
            "derived-docs",
            f"current README week does not report checkout version v{current_version}",
        )

    array = re.findall(
        r'^\s+"([^"]+)"',
        script.split("PATCHED_FILES=(", 1)[1].split(")", 1)[0],
        re.MULTILINE,
    )
    snapshot_section = patches.split("受 `PATCHED_FILES` 管理的文件", 1)[1].split("> 以上", 1)
    snapshot = re.findall(r'"([^"]+)"', snapshot_section[0])
    note_count = int(re.search(r"（(\d+) 文件", snapshot_section[1]).group(1))
    if len(array) != len(set(array)) or len(snapshot) != len(set(snapshot)):
        raise FinalAuditError("derived-docs", "PATCHED_FILES contains duplicate paths")
    if array != snapshot or note_count != len(array) or array != patched_files:
        raise FinalAuditError("derived-docs", "PATCHED_FILES array/snapshot/print output drift")

    definitions = list(re.finditer(r"^### \[(PATCH-[A-Z0-9-]+)\].*$", patches, re.MULTILINE))
    for index, match in enumerate(definitions):
        block = patches[
            match.start() : definitions[index + 1].start() if index + 1 < len(definitions) else len(patches)
        ]
        for label in ("问题", "修复", "验证", "上游吸收判断"):
            if len(re.findall(rf"^\*\*{label}\*\*：", block, re.MULTILINE)) != 1:
                raise FinalAuditError(
                    "derived-docs",
                    f"{match.group(1)} does not have exact four-section shape",
                )

    table_lines = playbook.splitlines()
    table_start = next(index for index, line in enumerate(table_lines) if line.startswith("| 现象"))
    table_end = next(
        index for index in range(table_start + 2, len(table_lines)) if table_lines[index].startswith("> 这张表")
    )
    malformed = [
        index + 1
        for index, line in enumerate(table_lines[table_start:table_end], table_start)
        if line.startswith("|") and line.count("|") != 3
    ]
    if malformed:
        raise FinalAuditError("derived-docs", f"playbook friction table has malformed rows: {malformed}")

    base = (ROOT / "patches/.local-patches.base").read_text(encoding="utf-8").split()[0]
    head = _run("head-sha", ["git", "rev-parse", "HEAD"], cwd=INNER).stdout.strip()
    if base != head:
        raise FinalAuditError("derived-docs", f"patch base {base} != inner HEAD {head}")
    if len(evidence.get("patches", [])) != len(definitions):
        raise FinalAuditError(
            "derived-docs",
            "per-PATCH report count differs from registry definition count",
        )
    patch_records = list(evidence.get("patches", []))
    upgrade_range = _validate_evidence_upgrade_range(patch_records, head)
    overlap_paths = sorted({path for record in patch_records for path in record.get("upstream_overlap", [])})
    summary_match = re.search(r"\*\*最近一次升级.*?(?=\n---\n)", patches, re.DOTALL)
    if not summary_match:
        raise FinalAuditError("derived-docs", "PATCHES current upgrade summary is missing")
    summary_text = summary_match.group(0)
    missing_overlap_notes = [path for path in overlap_paths if path not in summary_text]
    if missing_overlap_notes or "吸收" not in summary_text:
        raise FinalAuditError(
            "derived-docs",
            f"current summary does not record upstream overlap/absorption review: {missing_overlap_notes}",
        )
    absorption = _validate_absorption_matrix(patch_records, summary_text)
    patch_counts = _validate_patch_count_claims(
        patch_records,
        patches,
        readme,
        summary_text,
    )
    regression_counts = _validate_documented_regression_counts(
        canonical,
        patch_records,
        current_summary,
        summary_text,
    )
    gate_counts = _validate_documented_gate_counts(
        script,
        current_summary,
        summary_text,
    )

    known = set(re.findall(r"^### \[(PATCH-[A-Z0-9-]+)\]", patches, re.MULTILINE))
    refs = set(re.findall(r"PATCH-[A-Z0-9][A-Z0-9-]*[A-Z0-9]", playbook)) - {"PATCH-FOO-BAR"}
    if refs - known:
        raise FinalAuditError(
            "derived-docs",
            f"playbook references unknown PATCH IDs: {sorted(refs - known)}",
        )

    return {
        "weekly_rows": len(weeks),
        "weekly_rows_unique": True,
        "current_version": current_version,
        "current_week_summary_chars": len(current_summary),
        "patch_definitions": len(definitions),
        "patched_files": len(array),
        "friction_table_valid": True,
        "base_sha": base,
        "upstream_overlap_paths": overlap_paths,
        "absorption_matrix": absorption,
        "patch_counts": patch_counts,
        "regression_counts": regression_counts,
        "gate_counts": gate_counts,
        "upgrade_range": upgrade_range,
    }


def _validate_gateway_state_payload(
    payload: object,
    *,
    gateway_pid: int,
    expected_sha: str,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise FinalAuditError("gateway-runtime", "gateway_state.json is not a JSON object")
    if payload.get("kind") != "hermes-gateway":
        raise FinalAuditError(
            "gateway-runtime",
            f"gateway_state.json has unexpected kind: {payload.get('kind')!r}",
        )
    recorded_pid = payload.get("pid")
    if isinstance(recorded_pid, bool) or not isinstance(recorded_pid, int):
        raise FinalAuditError("gateway-runtime", "gateway_state.json has no integer pid")
    if recorded_pid != gateway_pid:
        raise FinalAuditError(
            "gateway-runtime",
            f"gateway_state.json belongs to PID {recorded_pid}, not live Gateway PID {gateway_pid}",
        )
    argv_value = payload.get("argv")
    argv = " ".join(str(part) for part in argv_value) if isinstance(argv_value, list) else str(argv_value or "")
    if "pytest" in argv.lower():
        raise FinalAuditError("gateway-runtime", "gateway_state.json was overwritten by a pytest process")
    if payload.get("code_sha") != expected_sha:
        raise FinalAuditError(
            "gateway-runtime",
            f"gateway_state.json code_sha {payload.get('code_sha')!r} != HEAD {expected_sha}",
        )
    state = str(payload.get("gateway_state") or "")
    if state not in {"running", "degraded"}:
        raise FinalAuditError("gateway-runtime", f"gateway_state.json is not serving: {state!r}")
    return {"state": state, "state_file_pid": recorded_pid, "code_sha": expected_sha}


def _gateway_runtime() -> dict[str, object]:
    status = _run("gateway-status", ["hermes", "gateway", "status"], timeout=60)
    supervisor = re.search(r"supervised by launchd \(PID (\d+)\)", status.stdout)
    child = _run(
        "gateway-child-pid",
        [
            str(INNER / "venv/bin/python"),
            "-c",
            "from gateway.status import get_running_pid; print(get_running_pid() or '')",
        ],
        cwd=INNER,
        timeout=60,
    ).stdout.strip()
    if not supervisor or not child.isdigit():
        raise FinalAuditError(
            "gateway-runtime",
            "could not resolve supervisor and real Gateway child PIDs",
        )
    gateway_pid = int(child)
    supervisor_pid = int(supervisor.group(1))
    if supervisor_pid == gateway_pid:
        raise FinalAuditError(
            "gateway-runtime",
            "launchd supervisor PID and real Gateway child PID unexpectedly match",
        )
    state_path = ROOT / "gateway_state.json"
    try:
        state_payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalAuditError(
            "gateway-runtime",
            f"could not read current gateway_state.json: {exc}",
        ) from exc
    head = _run("gateway-head-sha", ["git", "rev-parse", "HEAD"], cwd=INNER).stdout.strip()
    state_details = _validate_gateway_state_payload(
        state_payload,
        gateway_pid=gateway_pid,
        expected_sha=head,
    )

    ledger_path = ROOT / "spawn-ledger.json"
    ledger_entries = 0
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FinalAuditError(
                "gateway-runtime",
                f"spawn-ledger.json is unreadable: {exc}",
            ) from exc
        if not isinstance(ledger, list):
            raise FinalAuditError("gateway-runtime", "spawn-ledger.json is not a JSON list")
        contaminated = [
            entry for entry in ledger if isinstance(entry, dict) and "pytest" in str(entry.get("argv") or "").lower()
        ]
        if contaminated:
            raise FinalAuditError(
                "gateway-runtime",
                f"spawn-ledger.json contains {len(contaminated)} pytest process record(s)",
            )
        ledger_entries = len(ledger)
    return {
        "supervisor_pid": supervisor_pid,
        "gateway_pid": gateway_pid,
        "spawn_ledger_entries": ledger_entries,
        **state_details,
    }


def _doctor_health() -> dict[str, object]:
    result = _run("hermes-doctor", ["hermes", "doctor"], timeout=300)
    required = (
        "No active security advisories",
        "Config version up to date",
        "No deprecated config keys or env vars",
    )
    missing = [text for text in required if text not in result.stdout]
    if missing:
        raise FinalAuditError("hermes-doctor", f"doctor health invariants missing: {missing}")
    issue_match = re.search(r"Found (\d+) issue\(s\) to address", result.stdout)
    return {
        "issue_count": int(issue_match.group(1)) if issue_match else 0,
        "security_advisories": 0,
        "config_up_to_date": True,
        "deprecated_config": 0,
    }


def _validate_inner_status(inner_lines: list[str], patched_files: list[str]) -> list[str]:
    entries = {line[3:]: line[:2] for line in inner_lines if len(line) >= 4}
    inner_paths = set(entries)
    expected = set(patched_files)
    missing = expected - inner_paths
    extra = inner_paths - expected
    disallowed_extra = extra - set(_ALLOWED_REVIEWED_INNER_DIRTY)
    invalid_reviewed = {
        path: entries[path]
        for path in extra & set(_ALLOWED_REVIEWED_INNER_DIRTY)
        if entries[path] != _ALLOWED_REVIEWED_INNER_DIRTY[path]
    }
    if missing or disallowed_extra or invalid_reviewed:
        raise FinalAuditError(
            "repository-checks",
            f"inner status differs from PATCHED_FILES: missing={sorted(missing)} "
            f"extra={sorted(disallowed_extra)} invalid_reviewed={invalid_reviewed}",
        )
    return sorted(extra)


def _reverify_bundle_after_tests() -> None:
    """Close the gap between the initial evidence run and final repository state."""
    try:
        patch_evidence.audit_bundle()
    except (patch_evidence.EvidenceError, subprocess.SubprocessError, OSError) as exc:
        raise FinalAuditError(
            "repository-checks",
            f"post-test replay bundle verification failed: {exc}",
        ) from exc


def _repository_checks(patched_files: list[str]) -> dict[str, object]:
    _run("outer-diff-check", ["git", "diff", "--check"], cwd=ROOT)
    _run("outer-cached-diff-check", ["git", "diff", "--cached", "--check"], cwd=ROOT)
    bundle = (ROOT / "patches/local-patches.diff").read_text(encoding="utf-8")
    marker = re.compile(r"^\+?(<<<<<<<($| )|=======$|>>>>>>>($| ))", re.MULTILINE)
    if marker.search(bundle):
        raise FinalAuditError("repository-checks", "replay bundle contains conflict markers")
    for rel in patched_files:
        path = INNER / rel
        if (path.exists() or path.is_symlink()) and re.search(
            r"^(<<<<<<<($| )|=======$|>>>>>>>($| ))",
            path.read_text(errors="ignore"),
            re.MULTILINE,
        ):
            raise FinalAuditError("repository-checks", f"managed path contains conflict markers: {rel}")

    inner_lines = _run("inner-git-status", ["git", "status", "--short"], cwd=INNER).stdout.splitlines()
    reviewed_non_patch_paths = _validate_inner_status(inner_lines, patched_files)
    for rel in reviewed_non_patch_paths:
        if rel == "package-lock.json":
            try:
                json.loads((INNER / rel).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FinalAuditError(
                    "repository-checks",
                    f"reviewed npm lockfile is invalid JSON: {exc}",
                ) from exc
    _reverify_bundle_after_tests()
    return {
        "inner_overlay_paths": len(patched_files),
        "reviewed_non_patch_paths": reviewed_non_patch_paths,
        "bundle_reverified_after_tests": True,
        "conflict_markers": 0,
        "diff_check": "ok",
    }


def _cleanup_final() -> dict[str, object]:
    _run(
        "cleanup-apply",
        [
            sys.executable,
            str(CLEANUP),
            "--apply",
            "--fail-on-review",
            "--policy",
            str(CLEANUP_POLICY),
        ],
        timeout=300,
    )
    result = _run(
        "cleanup-final-dry-run",
        [
            sys.executable,
            str(CLEANUP),
            "--dry-run",
            "--json",
            "--fail-on-review",
            "--policy",
            str(CLEANUP_POLICY),
        ],
        timeout=300,
    )
    payload = json.loads(result.stdout)
    summary = payload["summary"]
    if summary["candidate_count"] or summary["ignored_review"] or summary["script_review"] or payload["policy_errors"]:
        raise FinalAuditError("cleanup-final-dry-run", f"cleanup did not converge: {summary}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the final audit JSON (default output is also JSON).",
    )
    parser.add_argument(
        "--require-clean-outer",
        action="store_true",
        help="Fail unless the outer ~/.hermes repository is clean (post-commit mode).",
    )
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    report: dict[str, object] = {
        "status": "running",
        "started_at": started.isoformat(),
    }
    try:
        transaction = _run("transaction-status", ["bash", str(UPDATE), "--transaction-status"]).stdout.strip()
        if transaction != "none":
            raise FinalAuditError("transaction-status", f"unfinished update transaction: {transaction}")
        _run("bash-syntax", ["bash", "-n", str(UPDATE)])
        _run("patch-gates", ["bash", str(UPDATE), "--self-test-patch-gates"])

        patched_files = _patched_files()
        test_files = _patched_tests()
        with tempfile.TemporaryDirectory(prefix="hermes-final-audit-") as temp_raw:
            evidence_path = Path(temp_raw) / "patch-evidence.json"
            _run(
                "patch-evidence-full",
                [sys.executable, str(EVIDENCE), "--report-json", str(evidence_path)],
                timeout=1200,
            )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence.get("status") != "ok" or evidence.get("mode") != "full":
                raise FinalAuditError("patch-evidence-full", "evidence report is not status=ok/mode=full")
            if evidence.get("execution_scope") != "per_patch_process":
                raise FinalAuditError(
                    "patch-evidence-full",
                    "active PATCH evidence was not executed in per-PATCH process isolation",
                )
            probe_summary = evidence.get("probes", {})
            if (
                probe_summary.get("registered", 0) <= 0
                or probe_summary.get("registered") != probe_summary.get("executed")
                or probe_summary.get("deferred") != 0
            ):
                raise FinalAuditError(
                    "patch-evidence-full",
                    f"registered PATCH probes did not fully execute: {probe_summary}",
                )
            patch_records = evidence.get("patches", [])
            patch_ids = [record.get("id") for record in patch_records]
            if len(patch_ids) != len(set(patch_ids)) or any(
                record.get("status") != "passed" for record in patch_records
            ):
                raise FinalAuditError(
                    "patch-evidence-full",
                    "per-PATCH report has duplicates, deferred contracts, or non-passing outcomes",
                )
            sandbox_record = next(
                (record for record in patch_records if record.get("id") == "PATCH-FEISHU-GROUP-SANDBOX"),
                None,
            )
            sandbox_probes = sandbox_record.get("probe_results", []) if sandbox_record else []
            sandbox_details = sandbox_probes[0].get("details", {}) if len(sandbox_probes) == 1 else {}
            sandbox_passed = sandbox_details.get("passed")
            if not isinstance(sandbox_passed, int) or sandbox_passed <= 0:
                raise FinalAuditError(
                    "patch-evidence-full",
                    "sandbox PATCH lacks an executed verifier result",
                )

        canonical_tests = _run_canonical_patch_tests(test_files)
        _validate_canonical_coverage(canonical_tests, evidence)
        wiki = json.loads(_run("wiki-lint", [sys.executable, str(WIKI_LINT), "--json"]).stdout)
        if any(wiki.values()):
            raise FinalAuditError("wiki-lint", "wiki lint JSON contains issues")
        try:
            final_sandbox = patch_evidence.audit_sandbox_verifier()
        except (patch_evidence.EvidenceError, subprocess.SubprocessError, OSError) as exc:
            raise FinalAuditError(
                "sandbox-final-verifier",
                f"post-canonical sandbox verifier failed: {exc}",
            ) from exc
        final_sandbox_passed = final_sandbox.get("passed")
        if not isinstance(final_sandbox_passed, int) or final_sandbox_passed <= 0:
            raise FinalAuditError(
                "sandbox-final-verifier",
                "post-canonical sandbox verifier reported no executed tests",
            )
        if final_sandbox_passed != sandbox_passed:
            raise FinalAuditError(
                "sandbox-final-verifier",
                f"sandbox regression count changed during final audit: "
                f"initial={sandbox_passed} final={final_sandbox_passed}",
            )

        report.update(
            {
                "status": "ok",
                "mode": "full",
                "target_sha": _run("target-sha", ["git", "rev-parse", "HEAD"], cwd=INNER).stdout.strip(),
                "transaction": "none",
                "patch_evidence": evidence,
                "canonical_patch_tests": canonical_tests,
                "sandbox": {
                    "initial_passed": sandbox_passed,
                    "final_passed": final_sandbox_passed,
                },
                "wiki_lint": {"checks_with_issues": 0},
                "derived": _derived_checks(patched_files, evidence, canonical_tests),
                "runtime": _gateway_runtime(),
                "doctor": _doctor_health(),
                "repository": _repository_checks(patched_files),
            }
        )
        report["cleanup"] = _cleanup_final()
        outer_status = _run("outer-git-status", ["git", "status", "--short"], cwd=ROOT).stdout.splitlines()
        if args.require_clean_outer and outer_status:
            raise FinalAuditError("outer-git-status", f"outer repository is not clean: {outer_status}")
        report["outer_git_status"] = outer_status
        report["inner_git_status_count"] = report["repository"]["inner_overlay_paths"]
    except (
        FinalAuditError,
        subprocess.SubprocessError,
        OSError,
        ValueError,
        KeyError,
        IndexError,
        AttributeError,
        StopIteration,
        json.JSONDecodeError,
    ) as exc:
        report.update(
            {
                "status": "failed",
                "failed_step": getattr(exc, "step", "internal"),
                "error": str(exc),
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["duration_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 3)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
