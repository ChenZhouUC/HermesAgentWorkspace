#!/usr/bin/env python3
"""Run the single authoritative Hermes post-upgrade audit.

This entrypoint intentionally runs after the last reconcile. It executes the
canonical patched-file test suite, per-PATCH evidence matrix, archive probes,
runtime plugin verifier, documentation/schema checks, replay closure, and the
final recoverable cleanup. Output is one JSON object suitable for the final
report or a post-commit verification step.
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

ROOT = Path(__file__).resolve().parents[1]
INNER = ROOT / "hermes-agent"
UPDATE = ROOT / "hermes-update.sh"
EVIDENCE = ROOT / "scripts/test_patch_evidence.py"
CLEANUP = ROOT / "scripts/cleanup_transient_artifacts.py"
CLEANUP_POLICY = ROOT / "scripts/cleanup_policy.json"
WIKI_LINT = ROOT / "scripts/wiki_lint.py"
SANDBOX_VERIFY = ROOT / "plugins/sandbox/verify.sh"


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
        [str(INNER / "scripts/run_tests.sh"), *test_files],
        cwd=INNER,
        timeout=900,
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


def _markdown_table_summary(row: str) -> str:
    """Return semantic summary content, ignoring formatter alignment padding."""
    cells = row.split("|")
    return cells[3].strip() if len(cells) >= 5 else ""


def _derived_checks(patched_files: list[str], evidence: dict[str, object]) -> dict[str, object]:
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
    current_rows = [line for line in readme.splitlines() if line.startswith(f"| v{current_version}")]
    current_summary = _markdown_table_summary(current_rows[0]) if current_rows else ""
    if len(current_rows) != 1 or not current_summary or len(current_summary) > 1500:
        raise FinalAuditError(
            "derived-docs",
            f"current README row count/summary length invalid: count={len(current_rows)} length={len(current_summary)}",
        )

    array = re.findall(
        r'^\s+"([^"]+)"',
        script.split("PATCHED_FILES=(", 1)[1].split(")", 1)[0],
        re.MULTILINE,
    )
    snapshot_section = patches.split("受 `PATCHED_FILES` 管理的文件", 1)[1].split("> 以上", 1)
    snapshot = re.findall(r'"([^"]+)"', snapshot_section[0])
    note_count = int(re.search(r"（(\d+) 文件", snapshot_section[1]).group(1))
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
    overlap_paths = sorted(
        {
            path
            for record in evidence.get("patches", [])
            if record.get("lifecycle") == "active"
            for path in record.get("upstream_overlap", [])
        }
    )
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
    }


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
    return {"supervisor_pid": int(supervisor.group(1)), "gateway_pid": int(child)}


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


def _repository_checks(patched_files: list[str]) -> dict[str, object]:
    _run("outer-diff-check", ["git", "diff", "--check"], cwd=ROOT)
    _run("outer-cached-diff-check", ["git", "diff", "--cached", "--check"], cwd=ROOT)
    bundle = (ROOT / "patches/local-patches.diff").read_text(encoding="utf-8")
    marker = re.compile(r"^\+?(<<<<<<<($| )|=======$|>>>>>>>($| ))", re.MULTILINE)
    if marker.search(bundle):
        raise FinalAuditError("repository-checks", "replay bundle contains conflict markers")
    for rel in patched_files:
        path = INNER / rel
        if not path.exists():
            raise FinalAuditError("repository-checks", f"managed path is missing: {rel}")
        if re.search(
            r"^(<<<<<<<($| )|=======$|>>>>>>>($| ))",
            path.read_text(errors="ignore"),
            re.MULTILINE,
        ):
            raise FinalAuditError("repository-checks", f"managed path contains conflict markers: {rel}")

    inner_lines = _run("inner-git-status", ["git", "status", "--short"], cwd=INNER).stdout.splitlines()
    inner_paths = {line[3:] for line in inner_lines if len(line) >= 4}
    if inner_paths != set(patched_files):
        raise FinalAuditError(
            "repository-checks",
            f"inner status differs from PATCHED_FILES: missing={sorted(set(patched_files) - inner_paths)} "
            f"extra={sorted(inner_paths - set(patched_files))}",
        )
    return {
        "inner_overlay_paths": len(inner_paths),
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
        _run(
            "transaction-and-fetch-self-tests",
            ["bash", str(UPDATE), "--self-test-patch-evidence"],
            timeout=300,
        )
        _run(
            "outer-audit-tests",
            [
                sys.executable,
                "-m",
                "unittest",
                "scripts.test_cleanup_transient_artifacts",
                "scripts.test_patch_evidence_auditor",
            ],
        )

        patched_files = _patched_files()
        test_files = _patched_tests()
        with tempfile.TemporaryDirectory(prefix="hermes-final-audit-") as temp_raw:
            evidence_path = Path(temp_raw) / "patch-evidence.json"
            _run(
                "patch-evidence-full",
                [sys.executable, str(EVIDENCE), "--report-json", str(evidence_path)],
                timeout=600,
            )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence.get("status") != "ok" or evidence.get("mode") != "full":
                raise FinalAuditError("patch-evidence-full", "evidence report is not status=ok/mode=full")
            patch_records = evidence.get("patches", [])
            patch_ids = [record.get("id") for record in patch_records]
            if len(patch_ids) != len(set(patch_ids)) or any(
                record.get("status") not in {"passed", "contract_passed"} for record in patch_records
            ):
                raise FinalAuditError(
                    "patch-evidence-full",
                    "per-PATCH report has duplicates or non-passing outcomes",
                )

        canonical_tests = _run_canonical_patch_tests(test_files)
        wiki = json.loads(_run("wiki-lint", [sys.executable, str(WIKI_LINT), "--json"]).stdout)
        if any(wiki.values()):
            raise FinalAuditError("wiki-lint", "wiki lint JSON contains issues")
        sandbox = _run("sandbox-verifier", ["bash", str(SANDBOX_VERIFY)], timeout=300)
        sandbox_tests = re.search(r"(\d+) passed", sandbox.stdout)
        if not sandbox_tests:
            raise FinalAuditError("sandbox-verifier", "sandbox pytest count missing")
        for record in evidence["patches"]:
            if record.get("status") == "contract_passed":
                record["status"] = "passed"
                record["final_audit_runtime_evidence"] = True

        report.update(
            {
                "status": "ok",
                "mode": "full",
                "target_sha": _run("target-sha", ["git", "rev-parse", "HEAD"], cwd=INNER).stdout.strip(),
                "transaction": "none",
                "patch_evidence": evidence,
                "canonical_patch_tests": canonical_tests,
                "sandbox": {"passed": int(sandbox_tests.group(1))},
                "wiki_lint": {"checks_with_issues": 0},
                "derived": _derived_checks(patched_files, evidence),
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
