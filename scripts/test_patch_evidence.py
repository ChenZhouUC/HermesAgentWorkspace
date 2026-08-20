#!/usr/bin/env python3
"""Audit durable regression evidence for every Hermes PATCH definition.

This is intentionally a repository-level audit rather than another source
sentinel.  A PATCH is accepted only when its lifecycle is registered, its
validation section names a real regression boundary, and the corresponding
current artifact/test entry exists on disk.  Runtime PATCHes use their
operator-level evidence (transaction, replay, cleanup, mirror, npm or
verifier checks) instead of pretending that a source grep is a behavioral
test.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INNER = ROOT / "hermes-agent"
PATCHES = ROOT / "patches" / "PATCHES.md"
SCRIPT = ROOT / "hermes-update.sh"
BUNDLE = ROOT / "patches" / "local-patches.diff"


class EvidenceError(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: Path = ROOT, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def _blocks(text: str, *, archive: bool) -> dict[str, str]:
    section = text.split("\n## Archive", 1)[1] if archive else text.split("\n## Archive", 1)[0]
    matches = list(re.finditer(r"^### \[(PATCH-[A-Z0-9-]+)\] .+$", section, re.M))
    return {
        m.group(1): section[m.start() : matches[i + 1].start() if i + 1 < len(matches) else len(section)]
        for i, m in enumerate(matches)
    }


def _validation(block: str) -> str:
    match = re.search(r"\*\*验证\*\*：(.*?)(?=\n\n\*\*上游吸收判断\*\*)", block, re.S)
    if not match:
        raise EvidenceError("PATCH block has no validation section")
    return match.group(1)


def _files(block: str) -> str:
    match = re.search(r"\*\*文件\*\*\s*\|\s*(.+)", block)
    return match.group(1) if match else ""


def _test_tokens(validation: str) -> set[str]:
    return set(re.findall(r"(?:[A-Za-z0-9_/-]*test_[A-Za-z0-9_/-]+|scripts/test_[A-Za-z0-9_./-]+)", validation))


RUNTIME_EVIDENCE: dict[str, tuple[str, ...]] = {
    "PATCH-NPM-DEPENDENCY-HYGIENE": ("npm audit fix", "npm audit --json", "--force"),
    "PATCH-REPLAY-BUNDLE-FULL-INDEX": ("--full-index", "git apply --cached --check", "反向 worktree"),
    "PATCH-UPDATE-GATE-EXIT-STATUS": ("--self-test-patch-gates", "FINAL_RC=1", "PID 替换"),
    "PATCH-GATEWAY-RESTART-CLEANUP": (
        "scripts/test_cleanup_transient_artifacts.py",
        "--dry-run --json --fail-on-review",
    ),
    "PATCH-UPDATE-GIT-FETCH-RETRY": ("fake `git`", "3 次 transport-fail", "Authentication failed"),
    "PATCH-UPDATE-TRANSACTION-PIN": ("--self-test-transaction", "0600", "symlink"),
    "PATCH-SKILLS-MIRROR-METADATA": ("隔离临时目录", "rsync", "runtime state"),
}


def audit_registry() -> tuple[dict[str, str], dict[str, str]]:
    text = PATCHES.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    gate_region = script.split("# -- 8b.", 1)[1].split("# -- 8c.", 1)[0]
    active = _blocks(text, archive=False)
    archived = _blocks(text, archive=True)
    all_ids = list(active) + list(archived)
    if len(all_ids) != len(set(all_ids)):
        raise EvidenceError("PATCH IDs are not globally unique")
    if "## Active PATCH definitions (continued)" in text:
        raise EvidenceError("active PATCH definitions resume after Archive")
    if not active or not archived:
        raise EvidenceError("PATCH registry is missing active or archive definitions")
    for patch_id, block in archived.items():
        if "**验证**" not in block and not re.search(r"test_[A-Za-z0-9_]+", block):
            raise EvidenceError(f"{patch_id}: archive definition has no retained regression evidence")
    for patch_id, block in active.items():
        validation = _validation(block)
        files = _files(block)
        if not validation.strip():
            raise EvidenceError(f"{patch_id}: empty validation section")
        if patch_id == "PATCH-FEISHU-GROUP-SANDBOX":
            if "plugins/sandbox/verify.sh" not in validation and "verifier" not in validation:
                raise EvidenceError(f"{patch_id}: missing verifier evidence")
            continue
        if patch_id in RUNTIME_EVIDENCE:
            missing = [needle for needle in RUNTIME_EVIDENCE[patch_id] if needle not in validation]
            if missing:
                raise EvidenceError(f"{patch_id}: validation omits runtime evidence {missing}")
            continue
        if not _test_tokens(validation):
            # Shared gate blocks are allowed only when the block itself names
            # concrete tests; a generic “回归覆盖” sentence is not evidence.
            position = gate_region.find(patch_id)
            window = gate_region[max(0, position - 1200) : position + 5000] if position >= 0 else ""
            if not re.search(r"test_[A-Za-z0-9_]+", window):
                raise EvidenceError(f"{patch_id}: no concrete regression token in validation or its gate")
        if files and "hermes-update.sh" not in files:
            inner_paths = re.findall(r"(?:tests|scripts)/[A-Za-z0-9_./{}-]+\.py", validation)
            for rel in inner_paths:
                if "{" in rel:
                    continue
                candidate = ROOT / rel
                if not candidate.exists():
                    candidate = INNER / rel
                if not candidate.exists():
                    raise EvidenceError(f"{patch_id}: validation references missing test path {rel}")
    return active, archived


def audit_gate_links(active: dict[str, str], archived: dict[str, str]) -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    gate_region = script.split("# -- 8b.", 1)[1].split("# -- 8c.", 1)[0]
    for patch_id in active:
        if patch_id == "PATCH-FEISHU-GROUP-SANDBOX":
            continue
        if patch_id in RUNTIME_EVIDENCE:
            continue
        if patch_id not in gate_region and patch_id not in script:
            raise EvidenceError(f"{patch_id}: no executable lifecycle reference in hermes-update.sh")
    # Archived sentinels may be retired once upstream carries the behavior;
    # the registry's validation section remains the durable evidence instead.


def audit_runtime_artifacts() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    required = {
        "PATCH-NPM-DEPENDENCY-HYGIENE": ("npm audit fix", "npm audit --json", "do not use --force"),
        "PATCH-REPLAY-BUNDLE-FULL-INDEX": (
            "--full-index",
            "_bundle_matches_patched_files",
            "git apply --check --reverse",
        ),
        "PATCH-UPDATE-GATE-EXIT-STATUS": ("FINAL_RC=1", "_self_test_patch_gate_coverage", "_GW_OLD_PID"),
        "PATCH-GATEWAY-RESTART-CLEANUP": ("cleanup_transient_artifacts.py", "--fail-on-review", "gateway restart"),
        "PATCH-UPDATE-GIT-FETCH-RETRY": ("_max_attempts=3", "Transient GitHub fetch failure", "Authentication failed"),
        "PATCH-UPDATE-TRANSACTION-PIN": ("_self_test_transaction", "TRANSACTION_TARGET_REF", "chmod 600"),
        "PATCH-SKILLS-MIRROR-METADATA": ("rsync -a --delete", "_SKILLS_RUNTIME_EXCLUDES", "FINAL_RC=1"),
    }
    for patch_id, needles in required.items():
        missing = [needle for needle in needles if needle not in script]
        if missing:
            raise EvidenceError(f"{patch_id}: executable evidence missing {missing}")
    if not (ROOT / "plugins/sandbox/verify.sh").is_file():
        raise EvidenceError("PATCH-FEISHU-GROUP-SANDBOX: verifier is missing")
    if not (ROOT / "plugins/sandbox/verify.sh").stat().st_mode & 0o111:
        raise EvidenceError("PATCH-FEISHU-GROUP-SANDBOX: verifier is not executable")
    if not BUNDLE.is_file():
        raise EvidenceError("replay bundle is missing")


def audit_socks_dependency() -> None:
    pyproject = (INNER / "pyproject.toml").read_text(encoding="utf-8")
    lazy = (INNER / "tools/lazy_deps.py").read_text(encoding="utf-8")
    if "python-socks==2.8.1" not in pyproject or "python-socks==2.8.1" not in lazy:
        raise EvidenceError("python-socks pin is missing from the eager/lazy Feishu paths")
    result = _run(
        [
            str(INNER / "venv/bin/python"),
            "-c",
            "import python_socks, importlib.metadata; assert importlib.metadata.version('python-socks') == '2.8.1'; print(python_socks.__name__)",
        ]
    )
    if result.returncode:
        raise EvidenceError(f"python-socks cannot be imported: {result.stderr.strip()}")


def audit_openclaw_token_migration() -> None:
    import tempfile

    source_text = {
        "gateway": {"auth": {"token": "must-not-be-migrated"}},
        "agents": {"defaults": {}},
    }
    with tempfile.TemporaryDirectory(prefix="hermes-openclaw-evidence-") as temp:
        root = Path(temp)
        source = root / "openclaw"
        target = root / "hermes"
        source.mkdir()
        (source / "openclaw.json").write_text(json.dumps(source_text), encoding="utf-8")
        result = _run(
            [
                str(INNER / "venv/bin/python"),
                str(INNER / "optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"),
                "--source",
                str(source),
                "--target",
                str(target),
                "--json",
            ],
        )
        if result.returncode:
            raise EvidenceError(f"OpenClaw migration dry-run failed: {result.stderr.strip()}")
        combined = f"{result.stdout}\n{result.stderr}"
        forbidden = ("HERMES_GATEWAY_TOKEN", "gateway.auth.token", "must-not-be-migrated")
        if any(token in combined for token in forbidden):
            raise EvidenceError("OpenClaw migration leaked the deprecated gateway token")
        if target.exists() and any(token in target.read_text(encoding="utf-8", errors="ignore") for token in forbidden):
            raise EvidenceError("OpenClaw migration wrote the deprecated gateway token to target output")


def audit_npm_dependency_hygiene() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for needle in ("npm audit fix", "npm audit --json", "do not use --force"):
        if needle not in script:
            raise EvidenceError(f"npm audit evidence is missing {needle!r}")
    result = _run(["npm", "audit", "--json"], cwd=INNER, timeout=180)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"npm audit did not return JSON: {exc}") from exc
    vulnerabilities = report.get("metadata", {}).get("vulnerabilities", {})
    if vulnerabilities.get("critical", 0):
        raise EvidenceError(f"npm audit found critical vulnerabilities: {vulnerabilities}")


def audit_skills_mirror() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for needle in ("rsync -a --delete", "_SKILLS_RUNTIME_EXCLUDES", "/.bundled_manifest", "__pycache__/"):
        if needle not in script:
            raise EvidenceError(f"skills mirror evidence is missing {needle!r}")
    if not (INNER / "skills").is_dir() or not (ROOT / "skills").is_dir():
        raise EvidenceError("skills mirror source or destination is missing")
    result = _run(["rsync", "--version"], timeout=30)
    if result.returncode:
        raise EvidenceError("rsync is unavailable for the Skills mirror regression")


def audit_fts5_build() -> None:
    result = _run(
        [str(INNER / "venv/bin/python"), "-m", "pytest", "-q", "tests/test_fts_cjk_bigram.py"],
        cwd=INNER,
        timeout=180,
    )
    if result.returncode:
        raise EvidenceError(f"FTS5 CJK regression failed: {result.stdout[-1000:]}{result.stderr[-1000:]}")


def audit_bundle() -> None:
    import os

    files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
    if not files:
        raise EvidenceError("PATCHED_FILES is empty")
    status = _run(["git", "diff", "--cached", "--quiet"], cwd=INNER)
    if status.returncode != 0:
        raise EvidenceError("inner index is staged")
    # Use a temporary index but intentionally leave the OS temp directory for
    # normal cleanup; this audit must never delete user paths.
    temp = Path(__import__("tempfile").mkdtemp(prefix="hermes-patch-evidence-"))
    index = temp / "index"
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(index)
    subprocess.run(["git", "read-tree", "HEAD"], cwd=INNER, env=env, check=True, timeout=30)
    for rel in files:
        path = INNER / rel
        if path.exists() or path.is_symlink():
            subprocess.run(["git", "add", "-f", "--", rel], cwd=INNER, env=env, check=True, timeout=30)
    live = temp / "live.diff"
    result = subprocess.run(
        ["git", "diff", "--cached", "--full-index", "HEAD", "--", *files],
        cwd=INNER,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode:
        raise EvidenceError(f"isolated bundle diff failed: {result.stderr.strip()}")
    live.write_text(result.stdout, encoding="utf-8")
    if live.read_bytes() != BUNDLE.read_bytes():
        raise EvidenceError("isolated full-index live diff differs from canonical bundle")
    for argv in (
        ("git", "apply", "--cached", "--check", str(BUNDLE)),
        ("git", "apply", "--check", "--reverse", str(BUNDLE)),
    ):
        result = _run(list(argv), cwd=INNER, timeout=60)
        if result.returncode:
            raise EvidenceError(f"replay check failed: {' '.join(argv)}: {result.stderr.strip()}")


def audit_current_tests() -> dict[str, int]:
    test_files = [line for line in _run(["bash", str(SCRIPT), "--print-patched-tests"]).stdout.splitlines() if line]
    missing = [rel for rel in test_files if not (INNER / rel).exists()]
    if missing:
        raise EvidenceError(f"PATCH_TESTS contains missing files: {missing}")
    collected = _run(
        [str(INNER / "venv/bin/python"), "-m", "pytest", "--collect-only", "-q", *test_files], cwd=INNER, timeout=180
    )
    if collected.returncode:
        raise EvidenceError(f"patched test collection failed: {collected.stdout[-1000:]}{collected.stderr[-1000:]}")
    match = re.search(r"(\d+) tests? collected", collected.stdout)
    if not match or int(match.group(1)) <= 0:
        raise EvidenceError("patched test collection reported no tests")
    return {"files": len(test_files), "collected": int(match.group(1))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip the expensive full test collection.")
    args = parser.parse_args()
    try:
        active, archived = audit_registry()
        audit_gate_links(active, archived)
        audit_runtime_artifacts()
        audit_socks_dependency()
        audit_openclaw_token_migration()
        audit_npm_dependency_hygiene()
        audit_skills_mirror()
        audit_fts5_build()
        audit_bundle()
        tests = {"files": 0, "collected": 0}
        if not args.quick:
            tests = audit_current_tests()
    except (EvidenceError, subprocess.SubprocessError, OSError) as exc:
        print(f"patch-evidence self-test FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "active": len(active), "archived": len(archived), **tests}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
