#!/usr/bin/env python3
"""Audit operational scripts and move policy-approved transient artifacts.

The default mode is dry-run. ``--apply`` moves only blacklist-classified
artifacts to a timestamped Trash directory. Unclassified scripts are never
deleted and can fail a Gateway restart gate via ``--fail-on-review``.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Artifact:
    path: str
    reason: str
    size_bytes: int
    age_seconds: int


@dataclass(frozen=True)
class ScriptAudit:
    path: str
    classification: str
    reason: str
    tracked: bool
    executable: bool
    size_bytes: int


@dataclass(frozen=True)
class IgnoredAudit:
    path: str
    classification: str
    reason: str
    repository: str


@dataclass(frozen=True)
class Skipped:
    path: str
    reason: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", "--dryrun", action="store_true", help="Preview only (default).")
    mode.add_argument("--apply", action="store_true", help="Move blacklist candidates to Trash.")
    parser.add_argument("--json", action="store_true", help="Emit one machine-readable JSON object.")
    parser.add_argument(
        "--min-age-minutes",
        type=float,
        default=10.0,
        help="Minimum age for blacklist-classified transient scripts (default: 10).",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--policy", type=Path, default=Path(__file__).with_name("cleanup_policy.json"))
    parser.add_argument("--trash-root", type=Path, default=Path.home() / ".Trash")
    parser.add_argument("--fail-if-found", action="store_true", help="Exit 3 when cleanup candidates exist.")
    parser.add_argument("--fail-on-review", action="store_true", help="Exit 4 when scripts need classification.")
    return parser.parse_args(argv)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _path_size(path: Path) -> int:
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
    except OSError:
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for filename in filenames:
            item = Path(dirpath) / filename
            try:
                total += item.lstat().st_size
            except OSError:
                pass
    return total


def _git_repo_and_relative(root: Path, path: Path) -> tuple[Path, Path]:
    inner = root / "hermes-agent"
    if inner.joinpath(".git").exists() and _is_within(path, inner):
        return inner, path.relative_to(inner)
    return root, path.relative_to(root)


def _is_git_tracked(root: Path, path: Path) -> bool:
    repo, relative = _git_repo_and_relative(root, path)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--", str(relative)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return True
    return bool(result.stdout.strip())


def load_policy(path: Path) -> dict[str, Any]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("cleanup policy must be an object with version=1")
    required_types = {
        "script_audit_globs": list,
        "script_extensions": list,
        "required_scripts": dict,
        "required_files": dict,
        "removable_script_globs": dict,
        "ignored_keep_globs": dict,
        "ignored_remove_globs": dict,
        "protected_prefixes": list,
        "removable_directory_names": dict,
        "removable_file_names": dict,
        "python_cache_roots": list,
        "active_process_markers": list,
    }
    for key, expected_type in required_types.items():
        if not isinstance(data.get(key), expected_type):
            raise ValueError(f"cleanup policy field {key!r} must be {expected_type.__name__}")
    for required in data["required_scripts"]:
        if any(fnmatch.fnmatch(required, pattern) for pattern in data["removable_script_globs"]):
            raise ValueError(f"required script also matches removable blacklist: {required}")
    return data


def _is_protected(relative: str, prefixes: list[str]) -> bool:
    return any(relative == prefix or relative.startswith(f"{prefix}/") for prefix in prefixes)


def _script_like(path: Path, extensions: set[str]) -> bool:
    return path.suffix.lower() in extensions or os.access(path, os.X_OK)


def audit_scripts(root: Path, policy: dict[str, Any]) -> tuple[list[ScriptAudit], list[str]]:
    root = root.expanduser().resolve()
    extensions = {str(value).lower() for value in policy["script_extensions"]}
    required: dict[str, str] = policy["required_scripts"]
    removable: dict[str, str] = policy["removable_script_globs"]
    found: dict[str, Path] = {}
    errors: list[str] = []
    for pattern in policy["script_audit_globs"]:
        for path in root.glob(pattern):
            if not path.is_file() or not _script_like(path, extensions):
                continue
            found[_relative(path, root)] = path
    for relative, reason in required.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing required script: {relative} ({reason})")
            continue
        found[relative] = path
    for relative, reason in policy["required_files"].items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing required policy file: {relative} ({reason})")
        elif not _is_git_tracked(root, path):
            errors.append(f"required policy file is not Git-tracked: {relative}")
    audits: list[ScriptAudit] = []
    for relative, path in sorted(found.items()):
        if relative in required:
            classification = "keep"
            reason = required[relative]
        else:
            matches = [pattern for pattern in removable if fnmatch.fnmatch(relative, pattern)]
            if matches:
                classification = "remove"
                reason = removable[matches[0]]
            else:
                classification = "review"
                reason = "Script-like file matched audit scope but has no whitelist/blacklist decision."
        tracked = _is_git_tracked(root, path)
        if classification == "keep" and not tracked:
            errors.append(f"required script is not Git-tracked: {relative}")
        audits.append(
            ScriptAudit(
                path=relative,
                classification=classification,
                reason=reason,
                tracked=tracked,
                executable=os.access(path, os.X_OK),
                size_bytes=_path_size(path),
            )
        )
    return audits, errors


def _first_match(relative: str, rules: dict[str, str]) -> tuple[str, str] | None:
    for pattern, reason in rules.items():
        if fnmatch.fnmatch(relative, pattern):
            return pattern, reason
    return None


def _ignored_entries(repo: Path, prefix: str) -> tuple[list[str], str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--ignored", "--porcelain=v1", "-z"],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        return [], str(exc)
    if result.returncode != 0:
        return [], result.stderr.decode(errors="replace").strip() or f"git status exited {result.returncode}"
    entries: list[str] = []
    for raw in result.stdout.split(b"\0"):
        if not raw.startswith(b"!! "):
            continue
        relative = raw[3:].decode(errors="surrogateescape")
        entries.append(f"{prefix}{relative}" if prefix else relative)
    return entries, None


def audit_ignored(root: Path, policy: dict[str, Any]) -> tuple[list[IgnoredAudit], list[str]]:
    keep_rules: dict[str, str] = policy["ignored_keep_globs"]
    remove_rules: dict[str, str] = policy["ignored_remove_globs"]
    errors: list[str] = []
    entries: list[tuple[str, str]] = []
    outer_entries, outer_error = _ignored_entries(root, "")
    if outer_error:
        errors.append(f"outer ignored audit failed: {outer_error}")
    entries.extend((path, "outer") for path in outer_entries)
    inner = root / "hermes-agent"
    if inner.joinpath(".git").exists():
        inner_entries, inner_error = _ignored_entries(inner, "hermes-agent/")
        if inner_error:
            errors.append(f"inner ignored audit failed: {inner_error}")
        entries.extend((path, "inner") for path in inner_entries)
    audits: list[IgnoredAudit] = []
    for relative, repository in sorted(set(entries)):
        keep_match = _first_match(relative, keep_rules)
        remove_match = _first_match(relative, remove_rules)
        if keep_match and remove_match:
            errors.append(
                f"ignored path matches keep and remove rules: {relative} ({keep_match[0]} vs {remove_match[0]})"
            )
        if remove_match:
            classification = "remove"
            reason = remove_match[1]
        elif keep_match:
            classification = "keep"
            reason = keep_match[1]
        else:
            classification = "review"
            reason = "Ignored path has no whitelist/blacklist decision."
        audits.append(IgnoredAudit(relative, classification, reason, repository))
    return audits, errors


def _candidate_paths(
    root: Path,
    policy: dict[str, Any],
    script_audit: list[ScriptAudit],
    ignored_audit: list[IgnoredAudit],
) -> Iterable[tuple[Path, str, bool]]:
    protected = [str(value).strip("/") for value in policy["protected_prefixes"]]
    removable_dirs: dict[str, str] = policy["removable_directory_names"]
    removable_files: dict[str, str] = policy["removable_file_names"]
    python_roots = {str(value).strip("/") for value in policy["python_cache_roots"]}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        current_relative = _relative(current, root) if current != root else ""
        for dirname in list(dirnames):
            child = current / dirname
            relative = _relative(child, root)
            if _is_protected(relative, protected):
                dirnames.remove(dirname)
                continue
            if dirname in removable_dirs:
                yield child, removable_dirs[dirname], False
                dirnames.remove(dirname)
                continue
            if dirname == "__pycache__" and current_relative.split("/", 1)[0] in python_roots:
                yield child, "Project Python bytecode cache under an approved cleanup root.", False
                dirnames.remove(dirname)
        for filename in filenames:
            path = current / filename
            relative = _relative(path, root)
            if _is_protected(relative, protected):
                continue
            if filename in removable_files:
                yield path, removable_files[filename], False
    for item in script_audit:
        if item.classification == "remove":
            yield root / item.path, item.reason, True
    for item in ignored_audit:
        if item.classification == "remove":
            yield root / item.path, item.reason, False


def discover_artifacts(
    root: Path,
    policy: dict[str, Any],
    script_audit: list[ScriptAudit],
    ignored_audit: list[IgnoredAudit],
    *,
    min_age_seconds: float,
    now: float | None = None,
) -> tuple[list[Artifact], list[Skipped]]:
    root = root.expanduser().resolve()
    current_time = time.time() if now is None else now
    artifacts: list[Artifact] = []
    skipped: list[Skipped] = []
    seen: set[Path] = set()
    for path, reason, age_gated in _candidate_paths(root, policy, script_audit, ignored_audit):
        absolute = path.absolute()
        if absolute in seen:
            continue
        seen.add(absolute)
        if not _is_within(absolute, root):
            skipped.append(Skipped(str(path), "outside cleanup root"))
            continue
        if _is_git_tracked(root, absolute):
            skipped.append(Skipped(_relative(path, root), "Git-tracked"))
            continue
        try:
            age_seconds = max(0, int(current_time - path.lstat().st_mtime))
        except OSError:
            skipped.append(Skipped(_relative(path, root), "disappeared during scan"))
            continue
        if age_gated and age_seconds < min_age_seconds:
            skipped.append(Skipped(_relative(path, root), f"recent ({age_seconds}s old)"))
            continue
        artifacts.append(
            Artifact(
                path=_relative(path, root),
                reason=reason,
                size_bytes=_path_size(path),
                age_seconds=age_seconds,
            )
        )
    artifacts.sort(key=lambda item: item.path)
    skipped.sort(key=lambda item: item.path)
    return artifacts, skipped


def active_test_processes(policy: dict[str, Any]) -> list[str]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    markers = [str(value).lower() for value in policy["active_process_markers"]]
    current_pid = os.getpid()
    active: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        first, _, command = stripped.partition(" ")
        try:
            pid = int(first)
        except ValueError:
            continue
        if pid == current_pid:
            continue
        lowered = command.lower()
        if any(marker in lowered for marker in markers):
            active.append(stripped[:500])
    return active


def _trash_destination(trash_dir: Path, relative: Path) -> Path:
    destination = trash_dir / relative
    if not destination.exists() and not destination.is_symlink():
        return destination
    index = 2
    while True:
        candidate = destination.with_name(f"{destination.name}-{index}")
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        index += 1


def apply_cleanup(root: Path, artifacts: list[Artifact], trash_root: Path) -> tuple[Path | None, list[Skipped]]:
    if not artifacts:
        return None, []
    trash_root = trash_root.expanduser()
    trash_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    trash_dir = trash_root / f"hermes-cleanup-{stamp}-{os.getpid()}"
    trash_dir.mkdir(mode=0o700)
    skipped: list[Skipped] = []
    for artifact in artifacts:
        source = root / artifact.path
        if not source.exists() and not source.is_symlink():
            skipped.append(Skipped(artifact.path, "disappeared before apply"))
            continue
        destination = _trash_destination(trash_dir, Path(artifact.path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    return trash_dir, skipped


def run(args: argparse.Namespace, *, processes: list[str] | None = None) -> tuple[dict[str, object], int]:
    root = args.root.expanduser().resolve()
    policy = load_policy(args.policy)
    script_audit, script_errors = audit_scripts(root, policy)
    ignored_audit, ignored_errors = audit_ignored(root, policy)
    policy_errors = script_errors + ignored_errors
    artifacts, skipped = discover_artifacts(
        root,
        policy,
        script_audit,
        ignored_audit,
        min_age_seconds=max(0.0, args.min_age_minutes * 60),
    )
    active = active_test_processes(policy) if processes is None else processes
    script_reviews = [item for item in script_audit if item.classification == "review"]
    ignored_reviews = [item for item in ignored_audit if item.classification == "review"]
    trash_dir: Path | None = None
    exit_code = 0
    if policy_errors:
        exit_code = 1
    elif args.fail_on_review and (script_reviews or ignored_reviews):
        exit_code = 4
    elif args.apply and active:
        skipped.extend(Skipped("<process>", f"active: {process}") for process in active)
        exit_code = 2
    elif args.apply:
        trash_dir, apply_skips = apply_cleanup(root, artifacts, args.trash_root)
        skipped.extend(apply_skips)
    elif args.fail_if_found and artifacts:
        exit_code = 3
    result: dict[str, object] = {
        "mode": "apply" if args.apply else "dry-run",
        "root": str(root),
        "policy": str(args.policy.expanduser().resolve()),
        "trash_dir": str(trash_dir) if trash_dir else None,
        "active_processes": active,
        "policy_errors": policy_errors,
        "script_audit": [asdict(item) for item in script_audit],
        "ignored_audit": [asdict(item) for item in ignored_audit],
        "candidates": [asdict(item) for item in artifacts],
        "skipped": [asdict(item) for item in skipped],
        "summary": {
            "script_keep": sum(item.classification == "keep" for item in script_audit),
            "script_remove": sum(item.classification == "remove" for item in script_audit),
            "script_review": len(script_reviews),
            "ignored_keep": sum(item.classification == "keep" for item in ignored_audit),
            "ignored_remove": sum(item.classification == "remove" for item in ignored_audit),
            "ignored_review": len(ignored_reviews),
            "candidate_count": len(artifacts),
            "candidate_bytes": sum(item.size_bytes for item in artifacts),
            "skipped_count": len(skipped),
        },
    }
    return result, exit_code


def print_text(result: dict[str, object]) -> None:
    print(f"mode={result['mode']} root={result['root']} policy={result['policy']}")
    for item in result["script_audit"]:
        print(
            "script "
            f"class={item['classification']} tracked={str(item['tracked']).lower()} "
            f"exec={str(item['executable']).lower()} reason={item['reason']} path={item['path']}"
        )
    for error in result["policy_errors"]:
        print(f"policy_error {error}")
    for item in result["ignored_audit"]:
        print(
            "ignored "
            f"class={item['classification']} repo={item['repository']} "
            f"reason={item['reason']} path={item['path']}"
        )
    for item in result["candidates"]:
        print(
            "candidate "
            f"size={item['size_bytes']} age={item['age_seconds']}s "
            f"reason={item['reason']} path={item['path']}"
        )
    for item in result["skipped"]:
        print(f"skipped reason={item['reason']} path={item['path']}")
    summary = result["summary"]
    print(
        "summary "
        f"scripts_keep={summary['script_keep']} scripts_remove={summary['script_remove']} "
        f"scripts_review={summary['script_review']} ignored_keep={summary['ignored_keep']} "
        f"ignored_remove={summary['ignored_remove']} ignored_review={summary['ignored_review']} "
        f"candidates={summary['candidate_count']} "
        f"bytes={summary['candidate_bytes']} skipped={summary['skipped_count']}"
    )
    if result["trash_dir"]:
        print(f"trash_dir={result['trash_dir']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result, exit_code = run(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"cleanup error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print_text(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
