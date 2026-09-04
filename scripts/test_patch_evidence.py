#!/usr/bin/env python3
"""Audit durable regression evidence for every Hermes PATCH definition.

This is intentionally a repository-level audit rather than another source
sentinel.  A PATCH is accepted only when its lifecycle is registered, its
validation section names a real regression boundary, and the corresponding
current artifact/test entry exists on disk. Full mode runs every PATCH in a
separate pytest process, profiles non-import execution, and requires
source-owning PATCHes to execute every declared Python production file unless
that exact module-level data file has an explicit import-evidence exception.
Runtime, dedicated, archive, and external-verifier PATCHes are executed from
one probe registry and must leave a fresh per-PATCH receipt; prose tokens or an
unconditional contract status cannot turn them green.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INNER = ROOT / "hermes-agent"
PATCHES = ROOT / "patches" / "PATCHES.md"
SCRIPT = ROOT / "hermes-update.sh"
BUNDLE = ROOT / "patches" / "local-patches.diff"
PYTEST_STRICT_WARNING_ARGS = (
    "-W",
    "error::pytest.PytestUnhandledThreadExceptionWarning",
    "-W",
    "error::pytest.PytestUnraisableExceptionWarning",
    "-W",
    "error::RuntimeWarning",
    "-W",
    "error::pytest.PytestReturnNotNoneWarning",
    "-W",
    "error::pytest.PytestCollectionWarning",
)


class EvidenceError(RuntimeError):
    pass


def _run(
    argv: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _hermetic_test_env() -> dict[str, str]:
    """Match the canonical runner's credential-free environment."""
    keep = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "TZ": "UTC",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONHASHSEED": "0",
        "PYTHONUTF8": "1",
    }
    for name in (
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "APPDATA",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
    ):
        if os.environ.get(name):
            keep[name] = os.environ[name]
    return keep


def _blocks(text: str, *, archive: bool) -> dict[str, str]:
    section = text.split("\n## Archive", 1)[1] if archive else text.split("\n## Archive", 1)[0]
    matches = list(re.finditer(r"^### \[(PATCH-[A-Z0-9-]+)\] .+$", section, re.MULTILINE))
    ids = [match.group(1) for match in matches]
    duplicates = sorted({patch_id for patch_id in ids if ids.count(patch_id) > 1})
    if duplicates:
        lifecycle = "archive" if archive else "active"
        raise EvidenceError(f"duplicate {lifecycle} PATCH definitions: {duplicates}")
    return {
        m.group(1): section[m.start() : matches[i + 1].start() if i + 1 < len(matches) else len(section)]
        for i, m in enumerate(matches)
    }


def _validation(block: str) -> str:
    match = re.search(r"\*\*验证\*\*：(.*?)(?=\n\n\*\*上游吸收判断\*\*)", block, re.DOTALL)
    if not match:
        raise EvidenceError("PATCH block has no validation section")
    return match.group(1)


def _files(block: str) -> str:
    match = re.search(r"\*\*文件\*\*\s*\|\s*(.+)", block)
    return match.group(1) if match else ""


def _expand_braces(pattern: str) -> set[str]:
    match = re.search(r"\{([^{}]+)\}", pattern)
    if not match:
        return {pattern}
    expanded: set[str] = set()
    for choice in match.group(1).split(","):
        replaced = f"{pattern[: match.start()]}{choice.strip()}{pattern[match.end() :]}"
        expanded.update(_expand_braces(replaced))
    return expanded


def _declared_file_patterns(block: str) -> list[str]:
    patterns: set[str] = set()
    for token in re.findall(r"`([^`]+)`", _files(block)):
        patterns.update(_expand_braces(token))
    return sorted(patterns)


def _declared_upstream_overlap(
    block: str,
    changed_paths: set[str],
    *,
    include: bool,
) -> list[str]:
    if not include:
        return []
    patterns = _declared_file_patterns(block)
    return sorted(
        path
        for path in changed_paths
        if any(fnmatch.fnmatchcase(path, pattern.replace("...", "*")) for pattern in patterns)
    )


def _owned_managed_files(block: str, managed_files: list[str]) -> list[str]:
    patterns = _declared_file_patterns(block)
    return sorted(
        path
        for path in managed_files
        if any(fnmatch.fnmatchcase(path, pattern.replace("...", "*")) for pattern in patterns)
    )


def _test_tokens(validation: str) -> set[str]:
    path_pattern = r"(?:tests|scripts)/[A-Za-z0-9_./-]*test_[A-Za-z0-9_.-]+\.py"
    paths = set(re.findall(path_pattern, validation))
    without_paths = re.sub(path_pattern, "", validation)
    functions = set(re.findall(r"\btest_[A-Za-z0-9_]+\b(?!\.py)", without_paths))
    return paths | functions


def _explicit_test_nodes(validation: str) -> set[str]:
    """Return path-qualified pytest node IDs written in PATCH validation prose."""
    pattern = (
        r"tests/[A-Za-z0-9_./-]+\.py"
        r"(?:::[A-Za-z_][A-Za-z0-9_.-]*(?:\[[^\]\n`]*\])?)+"
    )
    return {_base_node_id(node) for node in re.findall(pattern, validation)}


def _audit_active_patch_ownership(active: dict[str, str], managed_files: list[str]) -> None:
    """Every non-runtime active PATCH must own at least one managed path."""
    for patch_id, block in active.items():
        if patch_id in RUNTIME_EVIDENCE or patch_id in EXTERNAL_EVIDENCE_AUDITS:
            continue
        if not _owned_managed_files(block, managed_files):
            raise EvidenceError(f"{patch_id}: active engineering/dedicated PATCH owns no PATCHED_FILES path")
    unknown_import_exceptions = set(MODULE_IMPORT_EVIDENCE) - set(active)
    if unknown_import_exceptions:
        raise EvidenceError(
            f"module-import evidence maps unknown active PATCH IDs: {sorted(unknown_import_exceptions)}"
        )
    for patch_id, paths in MODULE_IMPORT_EVIDENCE.items():
        owned = set(_owned_managed_files(active[patch_id], managed_files))
        invalid = sorted(set(paths) - owned)
        if invalid:
            raise EvidenceError(f"{patch_id}: module-import evidence references unowned paths: {invalid}")


RUNTIME_EVIDENCE: dict[str, tuple[str, ...]] = {
    "PATCH-NPM-DEPENDENCY-HYGIENE": ("npm audit fix", "npm audit --json", "--force"),
    "PATCH-REPLAY-BUNDLE-FULL-INDEX": (
        "--full-index",
        "git apply --cached --check",
        "反向 worktree",
    ),
    "PATCH-UPDATE-GATE-EXIT-STATUS": (
        "--self-test-patch-gates",
        "FINAL_RC=1",
        "old/new PID",
    ),
    "PATCH-GATEWAY-RESTART-CLEANUP": (
        "scripts/test_cleanup_transient_artifacts.py",
        "final-audit",
        "candidate/review/policy error",
    ),
    "PATCH-UPDATE-GIT-FETCH-RETRY": (
        "fake `git`",
        "3 次 transport-fail",
        "Authentication failed",
    ),
    "PATCH-UPDATE-TRANSACTION-PIN": ("--self-test-transaction", "0600", "symlink"),
    "PATCH-SKILLS-MIRROR-METADATA": ("隔离临时目录", "rsync", "runtime state"),
}


# Every non-pytest PATCH must name the callable that proves it in this exact
# invocation.  Keeping this separate from the prose needles above is
# deliberate: audit_registry() checks the key sets are identical, then
# _run_registered_patch_audits() drives execution from this table.  A new
# runtime PATCH therefore cannot acquire a green report by being added to the
# classification table while its actual probe is forgotten in main().
RUNTIME_EVIDENCE_AUDITS: dict[str, tuple[str, str]] = {
    "PATCH-NPM-DEPENDENCY-HYGIENE": ("audit_npm_dependency_hygiene", "quick"),
    "PATCH-REPLAY-BUNDLE-FULL-INDEX": ("audit_bundle", "full"),
    "PATCH-UPDATE-GATE-EXIT-STATUS": ("audit_patch_gate_self_test", "quick"),
    "PATCH-GATEWAY-RESTART-CLEANUP": ("audit_gateway_restart_cleanup", "quick"),
    "PATCH-UPDATE-GIT-FETCH-RETRY": ("audit_fetch_retry_self_test", "quick"),
    "PATCH-UPDATE-TRANSACTION-PIN": ("audit_transaction_self_test", "quick"),
    "PATCH-SKILLS-MIRROR-METADATA": ("audit_skills_mirror", "quick"),
}


DEDICATED_EVIDENCE_AUDITS: dict[str, tuple[str, str]] = {
    "PATCH-FEISHU-SOCKS-DEPENDENCY": (
        "scripts/test_patch_evidence.py",
        "audit_socks_dependency",
    ),
    "PATCH-OPENCLAW-TOKEN-MIGRATION": (
        "scripts/test_patch_evidence.py",
        "audit_openclaw_token_migration",
    ),
    "PATCH-FTS5-CJK-DARWIN": (
        "scripts/test_patch_evidence.py",
        "audit_fts5_build",
    ),
}


EXTERNAL_EVIDENCE_AUDITS: dict[str, tuple[str, str, str]] = {
    "PATCH-FEISHU-GROUP-SANDBOX": (
        "plugins/sandbox/verify.sh",
        "audit_sandbox_verifier",
        "full",
    ),
}


# A small number of PATCHes intentionally modify module-level configuration
# constants. Import execution is meaningful evidence only for these exact
# PATCH/file pairs; every other production file requires a non-module call.
MODULE_IMPORT_EVIDENCE: dict[str, tuple[str, ...]] = {
    "PATCH-PLATFORM-CAPABILITY-SCOPE": ("hermes_cli/config_defaults.py",),
}


ARCHIVED_EVIDENCE_AUDITS: dict[str, str] = {
    "PATCH-LAUNCHD-WRAPPER-SUPERVISOR": "audit_archived_launchd_wrapper_supervisor",
    "PATCH-COMPACTION-LIFECYCLE-SILENCE": "audit_archived_compaction_lifecycle_silence",
    "PATCH-VERTEX-FALLBACK": "audit_archived_vertex_fallback",
    "PATCH-GEMINI-CUSTOM-NATIVE-BASE": "audit_archived_gemini_custom_native_base",
    "PATCH-LAZY-ACTIVATION": "audit_archived_lazy_activation",
    "PATCH-DOCTOR-ENABLED-TOOLSETS": "audit_archived_doctor_enabled_toolsets",
    "PATCH-ZSH-COMPLETION-SYNTAX": "audit_archived_zsh_completion_syntax",
    "PATCH-DASHBOARD-BUILD-CACHE": "audit_archived_dashboard_build_cache",
    "PATCH-GEMINI-THOUGHT-SIGNATURE": "audit_archived_gemini_thought_signature",
    "PATCH-DELEGATE-ACP-ROUTING": "audit_archived_delegate_acp_routing",
}


REQUIRED_PATCH_SECTIONS = ("问题", "修复", "验证", "上游吸收判断")
MODE_RANK = {"quick": 0, "full": 1}


def _audit_section_shape(patch_id: str, block: str) -> None:
    counts = {
        label: len(re.findall(rf"^\*\*{re.escape(label)}\*\*：", block, re.MULTILINE))
        for label in REQUIRED_PATCH_SECTIONS
    }
    invalid = {label: count for label, count in counts.items() if count != 1}
    if invalid:
        raise EvidenceError(
            f"{patch_id}: PATCH definition must contain exactly one 问题/修复/验证/上游吸收判断 section; got {invalid}"
        )


def _resolve_audit_function(function_name: str):
    function = globals().get(function_name)
    if not callable(function):
        raise EvidenceError(f"registered PATCH evidence audit is missing or not callable: {function_name}")
    return function


def _audit_registered_probe_contract(active: dict[str, str], archived: dict[str, str]) -> None:
    active_ids = set(active)
    runtime_ids = set(RUNTIME_EVIDENCE)
    runtime_audit_ids = set(RUNTIME_EVIDENCE_AUDITS)
    runtime_artifact_ids = set(RUNTIME_ARTIFACT_NEEDLES)
    dedicated_ids = set(DEDICATED_EVIDENCE_AUDITS)
    external_ids = set(EXTERNAL_EVIDENCE_AUDITS)
    classified = runtime_ids | dedicated_ids | external_ids
    overlaps = {
        patch_id
        for patch_id in classified
        if sum(patch_id in group for group in (runtime_ids, dedicated_ids, external_ids)) > 1
    }
    if overlaps:
        raise EvidenceError(f"active PATCH evidence classifications overlap: {sorted(overlaps)}")
    if runtime_ids != runtime_audit_ids or runtime_ids != runtime_artifact_ids:
        raise EvidenceError(
            "runtime PATCH evidence mappings drift: "
            f"contracts_only={sorted(runtime_ids - runtime_audit_ids)}, "
            f"audits_only={sorted(runtime_audit_ids - runtime_ids)}, "
            f"artifact_only={sorted(runtime_artifact_ids - runtime_ids)}, "
            f"missing_artifacts={sorted(runtime_ids - runtime_artifact_ids)}"
        )
    unknown_active = classified - active_ids
    if unknown_active:
        raise EvidenceError(f"non-pytest evidence maps unknown active PATCH IDs: {sorted(unknown_active)}")
    if set(ARCHIVED_EVIDENCE_AUDITS) != set(archived):
        raise EvidenceError(
            "archive PATCH evidence mapping drift: "
            f"missing={sorted(set(archived) - set(ARCHIVED_EVIDENCE_AUDITS))}, "
            f"unknown={sorted(set(ARCHIVED_EVIDENCE_AUDITS) - set(archived))}"
        )

    registered_functions = {function_name for function_name, _minimum_mode in RUNTIME_EVIDENCE_AUDITS.values()}
    registered_functions.update(function_name for _path, function_name in DEDICATED_EVIDENCE_AUDITS.values())
    registered_functions.update(
        function_name for _path, function_name, _minimum_mode in EXTERNAL_EVIDENCE_AUDITS.values()
    )
    registered_functions.update(ARCHIVED_EVIDENCE_AUDITS.values())
    for function_name in sorted(registered_functions):
        _resolve_audit_function(function_name)


def _registered_probe_specs(active: dict[str, str], archived: dict[str, str]) -> dict[str, tuple[str, str]]:
    _audit_registered_probe_contract(active, archived)
    specs: dict[str, tuple[str, str]] = dict(RUNTIME_EVIDENCE_AUDITS)
    specs.update(
        {patch_id: (function_name, "quick") for patch_id, (_path, function_name) in DEDICATED_EVIDENCE_AUDITS.items()}
    )
    specs.update(
        {
            patch_id: (function_name, minimum_mode)
            for patch_id, (
                _path,
                function_name,
                minimum_mode,
            ) in EXTERNAL_EVIDENCE_AUDITS.items()
        }
    )
    specs.update({patch_id: (function_name, "quick") for patch_id, function_name in ARCHIVED_EVIDENCE_AUDITS.items()})
    return specs


def _run_registered_patch_audits(
    active: dict[str, str], archived: dict[str, str], *, mode: str
) -> dict[str, list[dict[str, object]]]:
    if mode not in MODE_RANK:
        raise EvidenceError(f"unknown PATCH evidence mode: {mode}")
    results: dict[str, list[dict[str, object]]] = defaultdict(list)
    for patch_id, (function_name, minimum_mode) in _registered_probe_specs(active, archived).items():
        if minimum_mode not in MODE_RANK:
            raise EvidenceError(f"{patch_id}: unknown minimum evidence mode: {minimum_mode}")
        if MODE_RANK[mode] < MODE_RANK[minimum_mode]:
            continue
        details = _resolve_audit_function(function_name)()
        result: dict[str, object] = {"probe": function_name, "status": "passed"}
        if details is not None:
            result["details"] = details
        results[patch_id].append(result)
    return dict(results)


def _patch_test_inventory() -> tuple[set[str], set[str]]:
    result = _run(["bash", str(SCRIPT), "--print-patched-tests"])
    if result.returncode:
        raise EvidenceError(f"could not read PATCH_TESTS: {result.stderr.strip()}")
    test_files = {line for line in result.stdout.splitlines() if line}
    invalid_names = sorted(path for path in test_files if not Path(path).name.startswith("test_"))
    if invalid_names:
        raise EvidenceError(f"PATCH_TESTS contains non-test support files: {invalid_names}")
    missing = [rel for rel in sorted(test_files) if not (INNER / rel).is_file()]
    if missing:
        raise EvidenceError(f"PATCH_TESTS contains missing files: {missing}")
    test_functions: set[str] = set()
    for rel in test_files:
        source = (INNER / rel).read_text(encoding="utf-8", errors="ignore")
        test_functions.update(re.findall(r"(?m)^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", source))
    return test_files, test_functions


def _patch_test_support_files() -> list[str]:
    result = _run(["bash", str(SCRIPT), "--print-patched-files"])
    if result.returncode:
        raise EvidenceError(f"could not read PATCHED_FILES: {result.stderr.strip()}")
    support_files = sorted(
        path
        for path in result.stdout.splitlines()
        if path.startswith("tests/") and path.endswith(".py") and not Path(path).name.startswith("test_")
    )
    missing = [rel for rel in support_files if not (INNER / rel).is_file()]
    if missing:
        raise EvidenceError(f"PATCH test support contains missing files: {missing}")
    for rel in support_files:
        try:
            ast.parse((INNER / rel).read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError) as exc:
            raise EvidenceError(f"PATCH test support is not valid Python: {rel}: {exc}") from exc
    return support_files


def _patch_test_support_consumers(
    support_files: list[str],
    test_files: set[str],
) -> dict[str, list[str]]:
    imported_by: dict[str, set[str]] = defaultdict(set)
    for rel in test_files:
        tree = ast.parse((INNER / rel).read_text(encoding="utf-8"), filename=rel)
        package_parts = list(Path(rel).with_suffix("").parts[:-1])
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_by[rel].update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    keep = max(0, len(package_parts) - (node.level - 1))
                    prefix = package_parts[:keep]
                    module = ".".join([*prefix, *(node.module or "").split(".")]).strip(".")
                else:
                    module = node.module or ""
                if module:
                    imported_by[rel].add(module)

    consumers: dict[str, list[str]] = {}
    unused: list[str] = []
    for support in support_files:
        support_path = Path(support)
        if support_path.name == "conftest.py":
            parent = support_path.parent.as_posix().rstrip("/")
            matched = sorted(path for path in test_files if path == f"{parent}.py" or path.startswith(f"{parent}/"))
        else:
            module = support_path.with_suffix("").as_posix().replace("/", ".")
            matched = sorted(path for path, imports in imported_by.items() if module in imports)
        consumers[support] = matched
        if not matched:
            unused.append(support)
    if unused:
        raise EvidenceError(f"PATCH test support files have no collected test consumers: {unused}")
    return consumers


def _collect_patch_nodes(test_files: set[str]) -> list[str]:
    result = subprocess.run(
        [
            str(INNER / "venv/bin/python"),
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *PYTEST_STRICT_WARNING_ARGS,
            *sorted(test_files),
        ],
        cwd=INNER,
        env=_hermetic_test_env(),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode:
        raise EvidenceError(f"patched test collection failed: {result.stdout[-1000:]}{result.stderr[-1000:]}")
    nodes = [line.strip() for line in result.stdout.splitlines() if line.strip().startswith("tests/") and "::" in line]
    if not nodes:
        raise EvidenceError("patched test collection reported no node IDs")
    duplicate_nodes = sorted(node for node in set(nodes) if nodes.count(node) > 1)
    if duplicate_nodes:
        raise EvidenceError(f"patched test collection reported duplicate node IDs: {duplicate_nodes}")
    collected_files = {node.split("::", 1)[0] for node in nodes}
    missing_files = sorted(test_files - collected_files)
    unexpected_files = sorted(collected_files - test_files)
    if missing_files or unexpected_files:
        raise EvidenceError(
            f"PATCH_TESTS collection is not file-complete: zero_collected={missing_files} unexpected={unexpected_files}"
        )
    return nodes


def _base_node_id(node_id: str) -> str:
    return re.sub(r"\[[^\]]*\]$", "", node_id)


def _node_function(node_id: str) -> str:
    return _base_node_id(node_id).rsplit("::", 1)[-1]


def _resolve_active_patch_nodes(
    active: dict[str, str],
    collected_nodes: list[str],
    managed_files: list[str],
) -> dict[str, list[str]]:
    by_function: dict[str, set[str]] = defaultdict(set)
    for node in collected_nodes:
        by_function[_node_function(node)].add(_base_node_id(node))

    resolved: dict[str, list[str]] = {}
    collected_bases = {_base_node_id(node) for node in collected_nodes}
    for patch_id, block in active.items():
        if patch_id in EXTERNAL_EVIDENCE_AUDITS or patch_id in RUNTIME_EVIDENCE:
            continue
        if patch_id in DEDICATED_EVIDENCE_AUDITS:
            continue
        validation = _validation(block)
        explicit_nodes = sorted(_explicit_test_nodes(validation))
        explicit_functions = {_node_function(node) for node in explicit_nodes}
        functions = sorted(
            token for token in _test_tokens(validation) if token.startswith("test_") and token not in explicit_functions
        )
        if not explicit_nodes and not functions:
            raise EvidenceError(
                f"{patch_id}: full evidence requires at least one concrete test function, not only a file path"
            )
        nodes: list[str] = list(explicit_nodes)
        missing_explicit = sorted(set(explicit_nodes) - collected_bases)
        if missing_explicit:
            raise EvidenceError(
                f"{patch_id}: explicit evidence node was not collected exactly as documented: {missing_explicit}"
            )
        for function in functions:
            candidates = sorted(by_function.get(function, set()))
            if not candidates:
                raise EvidenceError(f"{patch_id}: evidence function was not collected: {function}")
            if len(candidates) != 1:
                raise EvidenceError(
                    f"{patch_id}: evidence function is ambiguous; use a unique/full node ID: {function} -> {candidates}"
                )
            nodes.append(candidates[0])
        resolved[patch_id] = sorted(set(nodes))

        owned = set(_owned_managed_files(block, managed_files))
        unowned_test_files = sorted(
            {node.split("::", 1)[0] for node in resolved[patch_id] if node.split("::", 1)[0] not in owned}
        )
        if unowned_test_files:
            raise EvidenceError(
                f"{patch_id}: evidence nodes come from undeclared managed test files: {unowned_test_files}"
            )

    node_owners: dict[str, list[str]] = defaultdict(list)
    for patch_id, nodes in resolved.items():
        for node in nodes:
            node_owners[node].append(patch_id)
    shared = {node: owners for node, owners in node_owners.items() if len(owners) > 1}
    if shared:
        raise EvidenceError(
            "active PATCH evidence nodes must be exclusive to one PATCH: "
            + "; ".join(f"{node} -> {', '.join(owners)}" for node, owners in sorted(shared.items()))
        )
    return resolved


def _validate_patch_trace_hits(
    active: dict[str, str],
    resolved: dict[str, list[str]],
    traced_files: dict[str, set[str]],
    managed_files: list[str],
    imported_files: dict[str, set[str]] | None = None,
) -> dict[str, list[str]]:
    """Require each source-owning PATCH's tests to execute all owned Python production code."""
    hits: dict[str, list[str]] = {}
    missing: list[str] = []
    for patch_id, nodes in resolved.items():
        owned = _owned_managed_files(active[patch_id], managed_files)
        production = [path for path in owned if not path.startswith(("tests/", "website/"))]
        traceable = [path for path in production if path.endswith(".py")]
        if not traceable:
            # Test-only portability/hermeticity PATCHes have no production
            # Python implementation file to trace; their exclusive, clean
            # pytest node remains the relevant behavioral evidence. Non-Python
            # production surfaces are covered by their declared runtime/gate
            # contracts because sys.setprofile cannot observe them.
            hits[patch_id] = []
            continue
        executed: set[str] = set()
        imported: set[str] = set()
        for node in nodes:
            executed.update(traced_files.get(node, set()))
            imported.update((imported_files or {}).get(node, set()))
        allowed_imports = set(MODULE_IMPORT_EVIDENCE.get(patch_id, ()))
        effective_hits = executed | (imported & allowed_imports)
        patch_hits = sorted(set(traceable) & effective_hits)
        hits[patch_id] = patch_hits
        untraced = sorted(set(traceable) - effective_hits)
        if untraced:
            missing.append(f"{patch_id} (unexecuted owned Python production={untraced}, evidence={nodes})")
    if missing:
        raise EvidenceError(
            "active PATCH evidence passed without executing every owned Python production file: " + "; ".join(missing)
        )
    return hits


def _patch_trace_plugin_source() -> str:
    return (
        textwrap.dedent(
            r"""
                import json
                import os
                import sys
                import threading
                from pathlib import Path

                import pytest

                ROOT = os.path.realpath(os.environ["HERMES_PATCH_TRACE_ROOT"])
                ROOT_PREFIX = ROOT + os.sep
                OUT = Path(os.environ["HERMES_PATCH_TRACE_OUT"])
                _current = None
                _seen = {}
                _imports = {}
                _relative_cache = {}

                def _relative_filename(filename):
                    if filename in _relative_cache:
                        return _relative_cache[filename]
                    try:
                        resolved = os.path.realpath(filename)
                        if resolved == ROOT:
                            relative = ""
                        elif resolved.startswith(ROOT_PREFIX):
                            relative = resolved[len(ROOT_PREFIX):].replace(os.sep, "/")
                        else:
                            relative = None
                    except Exception:
                        relative = None
                    _relative_cache[filename] = relative
                    return relative

                def _profile(frame, event, arg):
                    if event != "call" or _current is None:
                        return
                    rel = _relative_filename(frame.f_code.co_filename)
                    if rel is None:
                        return
                    if rel.startswith(("tests/", "venv/", ".hermes-runtime/")):
                        return
                    target = _imports if frame.f_code.co_name == "<module>" else _seen
                    target.setdefault(_current, set()).add(rel)

                @pytest.hookimpl(hookwrapper=True)
                def pytest_runtest_call(item):
                    global _current
                    _current = item.nodeid
                    sys.setprofile(_profile)
                    threading.setprofile(_profile)
                    try:
                        yield
                    finally:
                        sys.setprofile(None)
                        threading.setprofile(None)
                        _current = None

                def pytest_sessionfinish(session, exitstatus):
                    OUT.write_text(
                        json.dumps({
                            "calls": {key: sorted(value) for key, value in _seen.items()},
                            "imports": {key: sorted(value) for key, value in _imports.items()},
                        }),
                        encoding="utf-8",
                    )
                """
        ).strip()
        + "\n"
    )


def _run_active_patch_nodes(active: dict[str, str], resolved: dict[str, list[str]]) -> dict[str, list[str]]:
    if not any(resolved.values()):
        raise EvidenceError("active engineering PATCH evidence resolved to no pytest nodes")
    with tempfile.TemporaryDirectory(prefix="hermes-active-patch-evidence-") as temp_raw:
        temp = Path(temp_raw)
        plugin = temp / "patch_trace_plugin.py"
        plugin.write_text(
            _patch_trace_plugin_source(),
            encoding="utf-8",
        )
        traced_files: dict[str, set[str]] = defaultdict(set)
        imported_files: dict[str, set[str]] = defaultdict(set)
        for patch_index, (patch_id, nodes) in enumerate(sorted(resolved.items())):
            if not nodes:
                raise EvidenceError(f"{patch_id}: resolved to no pytest nodes")
            junit = temp / f"patch-{patch_index}.xml"
            trace_json = temp / f"patch-{patch_index}-trace.json"
            env = _hermetic_test_env()
            env["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(temp), str(INNER), env.get("PYTHONPATH", "")) if part
            )
            env["HERMES_PATCH_TRACE_ROOT"] = str(INNER)
            env["HERMES_PATCH_TRACE_OUT"] = str(trace_json)
            result = subprocess.run(
                [
                    str(INNER / "venv/bin/python"),
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    "patch_trace_plugin",
                    "-o",
                    "junit_family=xunit2",
                    f"--junitxml={junit}",
                    *PYTEST_STRICT_WARNING_ARGS,
                    *nodes,
                ],
                cwd=INNER,
                env=env,
                text=True,
                capture_output=True,
                timeout=300,
                check=False,
            )
            if result.returncode:
                raise EvidenceError(
                    f"{patch_id}: active PATCH node regression failed: {result.stdout[-2000:]}{result.stderr[-2000:]}"
                )
            if re.search(r"\b\d+\s+xpassed\b", result.stdout):
                raise EvidenceError(f"{patch_id}: active PATCH node regression contains xpassed outcomes")
            try:
                root = ET.parse(junit).getroot()
            except (ET.ParseError, OSError) as exc:
                raise EvidenceError(f"{patch_id}: active PATCH JUnit report is unreadable: {exc}") from exc
            cases = list(root.iter("testcase"))
            if not cases:
                raise EvidenceError(f"{patch_id}: active PATCH JUnit report contains no test cases")
            outcomes: dict[str, list[ET.Element]] = defaultdict(list)
            for case in cases:
                outcomes[str(case.attrib.get("name") or "").split("[", 1)[0]].append(case)
            for node in nodes:
                function = _node_function(node)
                matched = outcomes.get(function, [])
                if not matched:
                    raise EvidenceError(f"{patch_id}: evidence node produced no JUnit case: {node}")
                for case in matched:
                    if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
                        raise EvidenceError(f"{patch_id}: evidence node did not pass cleanly: {node}")
            try:
                raw_trace = json.loads(trace_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvidenceError(f"{patch_id}: active PATCH execution trace is unreadable: {exc}") from exc
            for node, files in raw_trace.get("calls", {}).items():
                traced_files[_base_node_id(node)].update(str(path) for path in files)
            for node, files in raw_trace.get("imports", {}).items():
                imported_files[_base_node_id(node)].update(str(path) for path in files)
        managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
        return _validate_patch_trace_hits(
            active,
            resolved,
            traced_files,
            managed_files,
            imported_files,
        )


def audit_registry() -> tuple[dict[str, str], dict[str, str]]:
    text = PATCHES.read_text(encoding="utf-8")
    active = _blocks(text, archive=False)
    archived = _blocks(text, archive=True)
    test_files, test_functions = _patch_test_inventory()
    all_ids = list(active) + list(archived)
    if len(all_ids) != len(set(all_ids)):
        raise EvidenceError("PATCH IDs are not globally unique")
    if "## Active PATCH definitions (continued)" in text:
        raise EvidenceError("active PATCH definitions resume after Archive")
    if not active or not archived:
        raise EvidenceError("PATCH registry is missing active or archive definitions")
    managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
    for patch_id, block in {**active, **archived}.items():
        _audit_section_shape(patch_id, block)
    _audit_registered_probe_contract(active, archived)
    _audit_active_patch_ownership(active, managed_files)
    for patch_id, block in archived.items():
        validation = _validation(block)
        function_name = ARCHIVED_EVIDENCE_AUDITS.get(patch_id)
        if function_name is None:
            raise EvidenceError(f"{patch_id}: archive definition has no dedicated evidence audit")
        if "scripts/test_patch_evidence.py" not in validation or function_name not in validation:
            raise EvidenceError(f"{patch_id}: validation must bind scripts/test_patch_evidence.py::{function_name}")
    for patch_id, block in active.items():
        validation = _validation(block)
        files = _files(block)
        if not validation.strip():
            raise EvidenceError(f"{patch_id}: empty validation section")
        external = EXTERNAL_EVIDENCE_AUDITS.get(patch_id)
        if external is not None:
            evidence_path, function_name, _minimum_mode = external
            if evidence_path not in validation and "verifier" not in validation:
                raise EvidenceError(f"{patch_id}: missing external verifier evidence")
            if function_name not in validation:
                raise EvidenceError(f"{patch_id}: validation must bind {function_name}")
            continue
        if patch_id in RUNTIME_EVIDENCE:
            missing = [needle for needle in RUNTIME_EVIDENCE[patch_id] if needle not in validation]
            if missing:
                raise EvidenceError(f"{patch_id}: validation omits runtime evidence {missing}")
            continue
        dedicated = DEDICATED_EVIDENCE_AUDITS.get(patch_id)
        if dedicated is not None:
            evidence_path, function_name = dedicated
            if evidence_path not in validation or function_name not in validation:
                raise EvidenceError(f"{patch_id}: validation must bind {evidence_path}::{function_name}")
            continue

        tokens = _test_tokens(validation)
        if not tokens:
            raise EvidenceError(f"{patch_id}: validation names no concrete regression test")
        invalid_tokens = []
        for token in sorted(tokens):
            if token.startswith("tests/"):
                if token not in test_files:
                    invalid_tokens.append(token)
            elif token.startswith("scripts/") or token not in test_functions:
                invalid_tokens.append(token)
        if invalid_tokens:
            raise EvidenceError(f"{patch_id}: validation test evidence is missing from PATCH_TESTS: {invalid_tokens}")
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
    declared_active_gates = set(re.findall(r"^(_[A-Z0-9_]+_PATCH_OK)=false$", gate_region, re.MULTILINE))
    declared_archived_gates = set(re.findall(r"^(_ARCHIVED_[A-Z0-9_]+_OK)=false$", gate_region, re.MULTILINE))
    mapped_gates: dict[str, str] = {}
    for patch_id in active:
        if patch_id in EXTERNAL_EVIDENCE_AUDITS:
            continue
        if patch_id in RUNTIME_EVIDENCE:
            continue
        headers = list(re.finditer(rf"^# {re.escape(patch_id)}(?::|\s*$)", gate_region, re.MULTILINE))
        if len(headers) != 1:
            raise EvidenceError(f"{patch_id}: expected exactly one Step 8b gate header, found {len(headers)}")
        next_header = re.search(
            r"^# (?:PATCH-[A-Z0-9-]+|Archived PATCH-[A-Z0-9-]+)(?::|\s*$)",
            gate_region[headers[0].end() :],
            re.MULTILINE,
        )
        block_end = headers[0].end() + next_header.start() if next_header else len(gate_region)
        gate_block = gate_region[headers[0].start() : block_end]
        assignments = re.findall(r"^\s*(_[A-Z0-9_]+_PATCH_OK)=true$", gate_block, re.MULTILINE)
        assigned = set(assignments)
        if len(assignments) != 1:
            raise EvidenceError(
                f"{patch_id}: Step 8b block must activate its engineering gate exactly once; found {assignments}"
            )
        if len(assigned) != 1:
            raise EvidenceError(
                f"{patch_id}: Step 8b block must activate exactly one engineering gate, found {sorted(assigned)}"
            )
        gate_name = next(iter(assigned))
        if gate_name in mapped_gates.values():
            owner = next(pid for pid, name in mapped_gates.items() if name == gate_name)
            raise EvidenceError(f"{patch_id}: gate {gate_name} is already owned by {owner}")
        mapped_gates[patch_id] = gate_name
    mapped = set(mapped_gates.values())
    if mapped != declared_active_gates:
        raise EvidenceError(
            "Step 8b active gate ownership drift: "
            f"unowned={sorted(declared_active_gates - mapped)}, "
            f"unknown={sorted(mapped - declared_active_gates)}"
        )

    archived_headers = list(re.finditer(r"^# Archived (PATCH-[A-Z0-9-]+)(?::|\s*$)", gate_region, re.MULTILINE))
    mapped_archived: dict[str, str] = {}
    for index, header in enumerate(archived_headers):
        patch_id = header.group(1)
        if patch_id not in archived:
            raise EvidenceError(f"Step 8b references unknown archived PATCH ID: {patch_id}")
        if patch_id in mapped_archived:
            raise EvidenceError(f"{patch_id}: duplicate archived Step 8b gate header")
        block_end = archived_headers[index + 1].start() if index + 1 < len(archived_headers) else len(gate_region)
        next_active = re.search(
            r"^# PATCH-[A-Z0-9-]+(?::|\s*$)",
            gate_region[header.end() : block_end],
            re.MULTILINE,
        )
        if next_active:
            block_end = header.end() + next_active.start()
        gate_block = gate_region[header.start() : block_end]
        assignments = re.findall(r"^\s*(_ARCHIVED_[A-Z0-9_]+_OK)=true$", gate_block, re.MULTILINE)
        if len(assignments) != 1:
            raise EvidenceError(
                f"{patch_id}: archived Step 8b block must activate its gate exactly once; found {assignments}"
            )
        gate_name = assignments[0]
        if gate_name in mapped_archived.values():
            owner = next(pid for pid, name in mapped_archived.items() if name == gate_name)
            raise EvidenceError(f"{patch_id}: archived gate {gate_name} is already owned by {owner}")
        mapped_archived[patch_id] = gate_name
    mapped_archived_gates = set(mapped_archived.values())
    if mapped_archived_gates != declared_archived_gates:
        raise EvidenceError(
            "Step 8b archived gate ownership drift: "
            f"unowned={sorted(declared_archived_gates - mapped_archived_gates)}, "
            f"unknown={sorted(mapped_archived_gates - declared_archived_gates)}"
        )


def _configured_plugin_verifiers(script: str) -> list[str]:
    match = re.search(r"PLUGIN_VERIFIERS=\((.*?)\)", script, re.DOTALL)
    if match is None:
        raise EvidenceError("Step 8e PLUGIN_VERIFIERS registry is missing")
    entries = re.findall(r'"([^"]+)"', match.group(1))
    prefix = "${HERMES_HOME}/"
    invalid = sorted(entry for entry in entries if not entry.startswith(prefix))
    if invalid:
        raise EvidenceError(f"Step 8e verifier paths are not rooted at HERMES_HOME: {invalid}")
    paths = [entry[len(prefix) :] for entry in entries]
    duplicates = sorted(path for path in set(paths) if paths.count(path) > 1)
    if duplicates:
        raise EvidenceError(f"Step 8e verifier registry contains duplicates: {duplicates}")
    return paths


def _validate_external_verifier_links(script: str) -> list[str]:
    configured = sorted(_configured_plugin_verifiers(script))
    registered = sorted(path for path, _function_name, _mode in EXTERNAL_EVIDENCE_AUDITS.values())
    if configured != registered:
        raise EvidenceError(f"Step 8e verifier registry drift: configured={configured} registered={registered}")
    return configured


def _validate_sandbox_runtime_pid_binding(verifier_text: str) -> None:
    """Require the live MCP receipt to be tied to the Gateway child PID."""
    required = (
        "MCP server 'hypertex'.*pid=${gateway_pid}.*"
        "mcp__hypertex__tasks_get.*mcp__hypertex__tasks_cancel.*"
        "mcp__hypertex__tasks_update"
    )
    if required not in verifier_text:
        raise EvidenceError("sandbox verifier MCP registration is not bound to the current gateway PID")


RUNTIME_ARTIFACT_NEEDLES: dict[str, tuple[str, ...]] = {
    "PATCH-NPM-DEPENDENCY-HYGIENE": (
        "npm audit fix",
        "npm audit --json",
        "do not use --force",
    ),
    "PATCH-REPLAY-BUNDLE-FULL-INDEX": (
        "--full-index",
        "_bundle_matches_patched_files",
        "git apply --check --reverse",
    ),
    "PATCH-UPDATE-GATE-EXIT-STATUS": (
        "FINAL_RC=1",
        "_self_test_patch_gate_coverage",
        "_GW_OLD_PID",
        "PytestUnhandledThreadExceptionWarning",
        "PytestUnraisableExceptionWarning",
        "error::RuntimeWarning",
        "PytestReturnNotNoneWarning",
        "PytestCollectionWarning",
    ),
    "PATCH-GATEWAY-RESTART-CLEANUP": (
        "cleanup_transient_artifacts.py",
        "--fail-on-review",
        "gateway restart",
    ),
    "PATCH-UPDATE-GIT-FETCH-RETRY": (
        "_max_attempts=3",
        "Transient GitHub fetch failure",
        "Authentication failed",
    ),
    "PATCH-UPDATE-TRANSACTION-PIN": (
        "_self_test_transaction",
        "TRANSACTION_TARGET_REF",
        "chmod 600",
    ),
    "PATCH-SKILLS-MIRROR-METADATA": (
        "rsync -a --delete",
        "_SKILLS_RUNTIME_EXCLUDES",
        "FINAL_RC=1",
    ),
}


def _validate_update_pytest_warning_filters(script: str) -> int:
    array_match = re.search(r"PYTEST_STRICT_WARNING_ARGS=\((.*?)\)", script, re.DOTALL)
    if array_match is None:
        raise EvidenceError("hermes-update.sh is missing PYTEST_STRICT_WARNING_ARGS")
    missing_filters = [
        warning_filter
        for warning_filter in PYTEST_STRICT_WARNING_ARGS[1::2]
        if warning_filter not in array_match.group(1)
    ]
    if missing_filters:
        raise EvidenceError(f"hermes-update.sh strict pytest warning array is incomplete: {missing_filters}")
    direct_commands = re.findall(
        r'"\$\{VENV_PY\}" -m pytest(?P<body>.*?)(?:>/dev/null 2>&1; then)',
        script,
        re.DOTALL,
    )
    invocation_count = len(re.findall(r'"\$\{VENV_PY\}"\s+-m\s+pytest\b', script))
    if not direct_commands or len(direct_commands) != invocation_count:
        raise EvidenceError(
            "hermes-update.sh direct pytest smoke-gate inventory is incomplete: "
            f"invocations={invocation_count} auditable={len(direct_commands)}"
        )
    missing_usage = [
        index
        for index, command in enumerate(direct_commands, start=1)
        if '"${PYTEST_STRICT_WARNING_ARGS[@]}"' not in command
    ]
    if missing_usage:
        raise EvidenceError(
            f"hermes-update.sh direct pytest smoke gates omit strict warning filters: commands={missing_usage}"
        )
    return len(direct_commands)


def _validate_verifier_pytest_warning_filters(verifier_text: str) -> int:
    direct_commands = re.findall(
        r'"\$\{VENV_PYTHON\}" -m pytest(?P<body>.*?)(?:2>&1)',
        verifier_text,
        re.DOTALL,
    )
    invocation_count = len(re.findall(r'"\$\{VENV_PYTHON\}"\s+-m\s+pytest\b', verifier_text))
    if not direct_commands or len(direct_commands) != invocation_count:
        raise EvidenceError(
            "sandbox verifier pytest inventory is incomplete: "
            f"invocations={invocation_count} auditable={len(direct_commands)}"
        )
    missing = {
        index: [warning_filter for warning_filter in PYTEST_STRICT_WARNING_ARGS[1::2] if warning_filter not in command]
        for index, command in enumerate(direct_commands, start=1)
    }
    missing = {index: filters for index, filters in missing.items() if filters}
    if missing:
        raise EvidenceError(f"sandbox verifier pytest commands omit strict warning filters: {missing}")
    return len(direct_commands)


def audit_runtime_artifacts() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for patch_id, needles in RUNTIME_ARTIFACT_NEEDLES.items():
        missing = [needle for needle in needles if needle not in script]
        if missing:
            raise EvidenceError(f"{patch_id}: executable evidence missing {missing}")
    _validate_update_pytest_warning_filters(script)
    for patch_id, (
        evidence_path,
        _function_name,
        _minimum_mode,
    ) in EXTERNAL_EVIDENCE_AUDITS.items():
        verifier = ROOT / evidence_path
        if not verifier.is_file():
            raise EvidenceError(f"{patch_id}: verifier is missing: {evidence_path}")
        if not verifier.stat().st_mode & 0o111:
            raise EvidenceError(f"{patch_id}: verifier is not executable: {evidence_path}")
    _validate_external_verifier_links(script)
    if not BUNDLE.is_file():
        raise EvidenceError("replay bundle is missing")


def _run_update_self_test(option: str, expected: str) -> dict[str, object]:
    result = _run(["bash", str(SCRIPT), option], timeout=300)
    if result.returncode:
        raise EvidenceError(f"{option} failed: {result.stdout[-1000:]}{result.stderr[-1000:]}")
    combined = f"{result.stdout}\n{result.stderr}"
    if expected not in combined:
        raise EvidenceError(f"{option} did not emit its success sentinel: {expected}")
    return {"command": option, "sentinel": expected}


def _run_unittest_probe(module: str, label: str) -> dict[str, object]:
    result = _run([sys.executable, "-m", "unittest", module], timeout=300)
    if result.returncode:
        raise EvidenceError(f"{label} failed: {result.stdout[-1500:]}{result.stderr[-1500:]}")
    combined = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"Ran (\d+) tests?", combined)
    if match is None or int(match.group(1)) <= 0:
        raise EvidenceError(f"{label} reported no executed tests")
    return {"tests": int(match.group(1))}


def _run_strict_pytest_probe(
    label: str,
    *node_ids: str,
    timeout: int = 180,
) -> dict[str, object]:
    """Run a pytest probe and require every collected case to pass cleanly."""
    if not node_ids:
        raise EvidenceError(f"{label} has no pytest nodes")
    with tempfile.TemporaryDirectory(prefix="hermes-patch-probe-") as temp_raw:
        junit = Path(temp_raw) / "results.xml"
        result = _run(
            [
                str(INNER / "venv/bin/python"),
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-o",
                "xfail_strict=true",
                f"--junitxml={junit}",
                *PYTEST_STRICT_WARNING_ARGS,
                *node_ids,
            ],
            cwd=INNER,
            env=_hermetic_test_env(),
            timeout=timeout,
        )
        if result.returncode:
            raise EvidenceError(f"{label} failed: {result.stdout[-1500:]}{result.stderr[-1500:]}")
        try:
            root = ET.parse(junit).getroot()
        except (ET.ParseError, OSError) as exc:
            raise EvidenceError(f"{label} JUnit report is unreadable: {exc}") from exc
        cases = list(root.iter("testcase"))
        if not cases:
            raise EvidenceError(f"{label} reported no executed test cases")
        nonpassing = [
            str(case.attrib.get("name") or "<unnamed>")
            for case in cases
            if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
        ]
        if nonpassing:
            raise EvidenceError(f"{label} contains non-passing outcomes: {nonpassing}")
        if re.search(r"\b\d+\s+xpassed\b", result.stdout):
            raise EvidenceError(f"{label} contains xpassed outcomes")
        return {"passed": len(cases), "nodes": list(node_ids)}


def audit_patch_gate_self_test() -> dict[str, object]:
    result = _run_update_self_test("--self-test-patch-gates", "patch-gate self-test OK")
    result["auditor_tests"] = _run_unittest_probe(
        "scripts.test_patch_evidence_auditor",
        "PATCH evidence auditor regression",
    )["tests"]
    return result


def audit_fetch_retry_self_test() -> dict[str, object]:
    return _run_update_self_test("--self-test-fetch-retry", "fetch-retry self-test OK")


def audit_transaction_self_test() -> dict[str, object]:
    return _run_update_self_test("--self-test-transaction", "transaction-state self-test OK")


def audit_gateway_restart_cleanup() -> dict[str, object]:
    return _run_unittest_probe(
        "scripts.test_cleanup_transient_artifacts",
        "gateway cleanup regression",
    )


def audit_sandbox_verifier() -> dict[str, object]:
    verifier_rel = EXTERNAL_EVIDENCE_AUDITS["PATCH-FEISHU-GROUP-SANDBOX"][0]
    verifier = ROOT / verifier_rel
    verifier_text = verifier.read_text(encoding="utf-8")
    _validate_verifier_pytest_warning_filters(verifier_text)
    _validate_sandbox_runtime_pid_binding(verifier_text)
    result = _run(["bash", str(verifier)], timeout=300)
    if result.returncode:
        raise EvidenceError(f"sandbox verifier failed: {result.stdout[-2000:]}{result.stderr[-2000:]}")
    combined = f"{result.stdout}\n{result.stderr}"
    matches = re.findall(
        r"^PATCH_VERIFY_RESULT sandbox passed=(\d+) skipped=(\d+) failed=(\d+) errors=(\d+)$",
        combined,
        re.MULTILINE,
    )
    if len(matches) != 1:
        raise EvidenceError("sandbox verifier did not report exactly one machine-readable result")
    passed, skipped, failed, errors = (int(value) for value in matches[0])
    if passed <= 0 or skipped or failed or errors:
        raise EvidenceError(
            "sandbox verifier did not execute a clean regression set: "
            f"passed={passed} skipped={skipped} failed={failed} errors={errors}"
        )
    return {
        "verifier": verifier_rel,
        "passed": passed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


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
        forbidden = (
            "HERMES_GATEWAY_TOKEN",
            "gateway.auth.token",
            "must-not-be-migrated",
        )
        if any(token in combined for token in forbidden):
            raise EvidenceError("OpenClaw migration leaked the deprecated gateway token")
        if target.exists() and any(token in target.read_text(encoding="utf-8", errors="ignore") for token in forbidden):
            raise EvidenceError("OpenClaw migration wrote the deprecated gateway token to target output")


def audit_npm_dependency_hygiene() -> dict[str, object]:
    """Keep the PATCH contract offline-safe; live advisory telemetry is P2.

    A registry outage must not masquerade as missing regression evidence. A
    successfully parsed critical advisory remains release-blocking.
    """
    script = SCRIPT.read_text(encoding="utf-8")
    for needle in ("npm audit fix", "npm audit --json", "do not use --force"):
        if needle not in script:
            raise EvidenceError(f"npm audit evidence is missing {needle!r}")
    try:
        result = _run(["npm", "audit", "--json"], cwd=INNER, timeout=180)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "telemetry_unavailable",
            "reason": "timeout",
            "timeout_seconds": exc.timeout,
            "stderr_tail": str(exc.stderr or "")[-500:],
        }
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "telemetry_unavailable",
            "returncode": result.returncode,
            "stderr_tail": result.stderr[-500:],
        }
    vulnerabilities = report.get("metadata", {}).get("vulnerabilities", {})
    if vulnerabilities.get("critical", 0):
        raise EvidenceError(f"npm audit found critical vulnerabilities: {vulnerabilities}")
    return {
        "status": "reported",
        "returncode": result.returncode,
        "vulnerabilities": vulnerabilities,
    }


def audit_skills_mirror() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "rsync -a --delete",
        "_SKILLS_RUNTIME_EXCLUDES",
        "/.bundled_manifest",
        "__pycache__/",
    ):
        if needle not in script:
            raise EvidenceError(f"skills mirror evidence is missing {needle!r}")
    if not (INNER / "skills").is_dir() or not (ROOT / "skills").is_dir():
        raise EvidenceError("skills mirror source or destination is missing")
    result = _run(["rsync", "--version"], timeout=30)
    if result.returncode:
        raise EvidenceError("rsync is unavailable for the Skills mirror regression")
    with tempfile.TemporaryDirectory(prefix="hermes-skills-mirror-evidence-") as temp_raw:
        root = Path(temp_raw)
        source = root / "source"
        target = root / "target"
        (source / "demo").mkdir(parents=True)
        (source / "demo/SKILL.md").write_text("new-content\n", encoding="utf-8")
        target.mkdir()
        (target / "stale.txt").write_text("remove-me\n", encoding="utf-8")
        (target / ".bundled_manifest").write_text("keep-manifest\n", encoding="utf-8")
        (target / ".usage.json").write_text("keep-usage\n", encoding="utf-8")
        (target / ".hub").mkdir()
        (target / ".hub/state").write_text("keep-hub\n", encoding="utf-8")
        mirror = _run(
            [
                "rsync",
                "-a",
                "--delete",
                "--exclude=/.bundled_manifest",
                "--exclude=/.curator_state",
                "--exclude=/.usage.json",
                "--exclude=/.hub/",
                "--exclude=/.archive/",
                "--exclude=__pycache__/",
                f"{source}/",
                f"{target}/",
            ],
            timeout=30,
        )
        if mirror.returncode:
            raise EvidenceError(f"isolated Skills mirror failed: {mirror.stderr.strip()}")
        if (target / "demo/SKILL.md").read_text(encoding="utf-8") != "new-content\n":
            raise EvidenceError("isolated Skills mirror did not update bundled content")
        if (target / "stale.txt").exists():
            raise EvidenceError("isolated Skills mirror did not delete stale bundled content")
        for rel, expected in (
            (".bundled_manifest", "keep-manifest\n"),
            (".usage.json", "keep-usage\n"),
            (".hub/state", "keep-hub\n"),
        ):
            if (target / rel).read_text(encoding="utf-8") != expected:
                raise EvidenceError(f"isolated Skills mirror did not preserve runtime state: {rel}")


def audit_fts5_build() -> dict[str, object]:
    return _run_strict_pytest_probe(
        "FTS5 CJK regression",
        "tests/test_fts_cjk_bigram.py",
    )


def _run_archived_pytest(*node_ids: str) -> dict[str, object]:
    return _run_strict_pytest_probe("archived PATCH regression", *node_ids)


def audit_archived_launchd_wrapper_supervisor() -> dict[str, object]:
    return _run_archived_pytest("tests/hermes_cli/test_gateway_external_supervisor.py")


def audit_archived_compaction_lifecycle_silence() -> dict[str, object]:
    return _run_archived_pytest(
        "tests/gateway/test_telegram_noise_filter.py::test_all_routine_compression_statuses_suppressed_from_source_constants",
        "tests/gateway/test_compression_progress_notices.py::test_compaction_completion_notice_respects_progress_notices_gate",
        "tests/gateway/test_compression_progress_notices.py::test_progress_regex_covers_every_routine_sample",
    )


def _env_key_names(path: Path) -> set[str]:
    """Read dotenv key names without loading, expanding, or exposing values."""
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match:
            keys.add(match.group(1))
    return keys


def audit_archived_vertex_fallback() -> None:
    """Prove the retired second-Vertex surface has not silently returned."""
    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    source_paths = (
        "agent/vertex_adapter.py",
        "hermes_cli/auth.py",
        "hermes_cli/runtime_provider.py",
        "agent/auxiliary_client.py",
        "plugins/model-providers/vertex/__init__.py",
    )
    source = "\n".join((INNER / rel).read_text(encoding="utf-8") for rel in source_paths)
    forbidden = (
        "vertex-fallback",
        "vertex-secondary",
        "vertex2",
        "VERTEX_FALLBACK_CREDENTIALS_PATH",
        "VERTEX_FALLBACK_PROJECT_ID",
        "get_vertex_fallback_config",
    )
    env_keys = _env_key_names(ROOT / ".env") | _env_key_names(ROOT / ".env.example")
    bundle = BUNDLE.read_text(encoding="utf-8")
    for needle in forbidden:
        if needle in config or needle in source or needle in bundle or needle in env_keys:
            raise EvidenceError(f"archived Vertex fallback surface returned: {needle}")
    code = r"""
from hermes_cli.auth import PROVIDER_REGISTRY
from providers import get_provider_profile

for provider in ("vertex-fallback", "vertex2", "vertex-secondary"):
    assert provider not in PROVIDER_REGISTRY
    assert get_provider_profile(provider) is None
"""
    result = _run([str(INNER / "venv/bin/python"), "-c", code], cwd=INNER, timeout=60)
    if result.returncode:
        raise EvidenceError(f"retired Vertex fallback still resolves: {result.stderr[-1000:]}")


def audit_archived_gemini_custom_native_base() -> dict[str, object]:
    """Prove the private-base overlay stays retired while native Gemini still works."""
    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    env_keys = _env_key_names(ROOT / ".env") | _env_key_names(ROOT / ".env.example")
    source = "\n".join(
        (INNER / rel).read_text(encoding="utf-8")
        for rel in (
            "agent/gemini_native_adapter.py",
            "agent/agent_runtime_helpers.py",
            "agent/auxiliary_client.py",
        )
    )
    if "GEMINI_BASE_URL" in config or {"GEMINI_BASE_URL", "GOOGLE_GEMINI_BASE_URL"} & env_keys:
        raise EvidenceError("retired custom Gemini base is configured again")
    if "is_native_gemini_provider_base_url" in source or "is_native_gemini_provider_base_url" in BUNDLE.read_text(
        encoding="utf-8"
    ):
        raise EvidenceError("retired provider-aware custom Gemini helper returned")
    return _run_archived_pytest(
        "tests/agent/test_gemini_native_adapter.py::test_native_client_uses_x_goog_api_key_and_native_models_endpoint",
        "tests/hermes_cli/test_gemini_provider.py::TestGeminiAgentInit::test_gemini_resolve_provider_client_uses_native_client",
    )


def audit_archived_lazy_activation() -> dict[str, object]:
    return _run_archived_pytest(
        "tests/tools/test_lazy_deps.py::TestActiveFeatures::test_shared_dependency_does_not_activate_feature"
    )


def audit_archived_doctor_enabled_toolsets() -> dict[str, object]:
    return _run_archived_pytest(
        "tests/hermes_cli/test_doctor.py::TestDoctorToolAvailabilitySummary::test_missing_api_key_summary_ignores_disabled_toolsets"
    )


def audit_archived_zsh_completion_syntax() -> None:
    result = _run([str(INNER / "venv/bin/hermes"), "completion", "zsh"], cwd=INNER, timeout=60)
    if result.returncode:
        raise EvidenceError(f"zsh completion generation failed: {result.stderr[-1000:]}")
    output = result.stdout
    required = ("'(-)'{-h,--help}", "'(-)'{-V,--version}", "'(-)'{-p,--profile}")
    forbidden = ("){-h,--help}", "){-V,--version}", "){-p,--profile}")
    if any(token not in output for token in required) or any(token in output for token in forbidden):
        raise EvidenceError("zsh completion output no longer satisfies the archived syntax invariant")


def audit_archived_dashboard_build_cache() -> dict[str, object]:
    return _run_archived_pytest(
        "tests/hermes_cli/test_web_ui_build.py::TestWebUIBuildNeeded::test_mtime_only_change_is_not_stale"
    )


def audit_archived_gemini_thought_signature() -> dict[str, object]:
    return _run_archived_pytest(
        "tests/agent/transports/test_types.py::TestToolCallBackwardCompat::test_extra_content_getattr_pattern"
    )


def audit_archived_delegate_acp_routing() -> None:
    code = r"""
import threading
from unittest.mock import MagicMock, patch
from tools.delegate_tool import _build_child_agent

parent = MagicMock()
parent.base_url = "https://example.invalid/v1"
parent.api_key = "test-key"
parent.provider = "openrouter"
parent.api_mode = "chat_completions"
parent.model = "test-model"
parent.platform = "cli"
parent.providers_allowed = None
parent.providers_ignored = None
parent.providers_order = None
parent.provider_sort = None
parent._session_db = None
parent._delegate_depth = 0
parent._active_children = []
parent._active_children_lock = threading.Lock()
parent._print_fn = None
parent.tool_progress_callback = None
parent.thinking_callback = None
parent._fallback_chain = None
with patch("tools.delegate_tool._load_config", return_value={}), \
     patch("shutil.which", return_value="/usr/bin/copilot"), \
     patch("run_agent.AIAgent") as mock_agent:
    mock_agent.return_value = MagicMock()
    _build_child_agent(
        task_index=0,
        goal="archived ACP routing audit",
        context=None,
        toolsets=None,
        model=None,
        max_iterations=10,
        parent_agent=parent,
        task_count=1,
        override_acp_command="copilot",
    )
kwargs = mock_agent.call_args.kwargs
assert kwargs["provider"] == "copilot-acp"
assert kwargs["acp_command"] == "copilot"
"""
    result = _run([str(INNER / "venv/bin/python"), "-c", code], cwd=INNER, timeout=60)
    if result.returncode:
        raise EvidenceError(f"archived delegate ACP routing regression failed: {result.stderr[-1500:]}")


def audit_bundle() -> None:
    import os
    import tempfile

    files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
    if not files:
        raise EvidenceError("PATCHED_FILES is empty")
    status = _run(["git", "diff", "--cached", "--quiet"], cwd=INNER)
    if status.returncode != 0:
        raise EvidenceError("inner index is staged")
    # A private temporary index keeps the real index untouched. The context
    # manager proves cleanup is scoped to the directory created by this audit,
    # so repeated AI runs do not leak /tmp/hermes-patch-evidence-* sediment.
    with tempfile.TemporaryDirectory(prefix="hermes-patch-evidence-") as temp_raw:
        temp = Path(temp_raw)
        index = temp / "index"
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(index)
        subprocess.run(["git", "read-tree", "HEAD"], cwd=INNER, env=env, check=True, timeout=30)
        for rel in files:
            path = INNER / rel
            if path.exists() or path.is_symlink():
                subprocess.run(
                    ["git", "add", "-f", "--", rel],
                    cwd=INNER,
                    env=env,
                    check=True,
                    timeout=30,
                )
            else:
                subprocess.run(
                    ["git", "rm", "-f", "--cached", "--ignore-unmatch", "--", rel],
                    cwd=INNER,
                    env=env,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
        live = temp / "live.diff"
        result = subprocess.run(
            ["git", "diff", "--cached", "--full-index", "HEAD", "--", *files],
            cwd=INNER,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
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


def audit_current_tests(
    active: dict[str, str],
) -> tuple[dict[str, object], dict[str, list[str]], dict[str, list[str]]]:
    test_files = _patch_test_inventory()[0]
    support_files = _patch_test_support_files()
    support_consumers = _patch_test_support_consumers(support_files, test_files)
    managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
    collected_nodes = _collect_patch_nodes(test_files)
    resolved = _resolve_active_patch_nodes(active, collected_nodes, managed_files)
    executed_owned_files = _run_active_patch_nodes(active, resolved)
    return (
        {
            "files": len(test_files),
            "collected": len(collected_nodes),
            "support_files": len(support_files),
            "support_file_paths": support_files,
            "support_file_consumers": support_consumers,
        },
        resolved,
        executed_owned_files,
    )


def _evidence_records(
    active: dict[str, str],
    archived: dict[str, str],
    resolved: dict[str, list[str]],
    *,
    mode: str,
    probe_results: dict[str, list[dict[str, object]]],
    executed_owned_files: dict[str, list[str]] | None = None,
) -> list[dict[str, object]]:
    range_match = re.search(
        r"\*\*最近一次升级.*?`([0-9a-f]{7,40})`\s*→\s*`([0-9a-f]{7,40})`",
        PATCHES.read_text(encoding="utf-8"),
    )
    changed_paths: set[str] = set()
    upgrade_range: dict[str, str] | None = None
    if range_match:
        old_ref, new_ref = range_match.groups()
        old_result = _run(["git", "rev-parse", old_ref], cwd=INNER)
        new_result = _run(["git", "rev-parse", new_ref], cwd=INNER)
        if old_result.returncode or new_result.returncode:
            raise EvidenceError("PATCHES current upgrade range does not resolve in the inner repository")
        old_sha = old_result.stdout.strip()
        new_sha = new_result.stdout.strip()
        if old_sha == new_sha:
            raise EvidenceError("PATCHES current upgrade range is empty")
        ancestor = _run(
            ["git", "merge-base", "--is-ancestor", old_sha, new_sha],
            cwd=INNER,
        )
        if ancestor.returncode:
            raise EvidenceError("PATCHES current upgrade range is not an ancestor-to-descendant range")
        changed = _run(["git", "diff", "--name-only", f"{old_sha}..{new_sha}"], cwd=INNER)
        if changed.returncode:
            raise EvidenceError(f"could not compute PATCH upstream overlap: {changed.stderr.strip()}")
        changed_paths = {line for line in changed.stdout.splitlines() if line}
        upgrade_range = {"old_sha": old_sha, "new_sha": new_sha}
    managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()

    def ownership(
        patch_id: str,
        block: str,
        *,
        lifecycle: str,
    ) -> tuple[list[str], list[str], list[str]]:
        owned = _owned_managed_files(block, managed_files)
        declared_patterns = _declared_file_patterns(block)
        include_upstream = patch_id not in RUNTIME_EVIDENCE and patch_id not in EXTERNAL_EVIDENCE_AUDITS
        if lifecycle == "archived" and "工程外" in _files(block):
            include_upstream = False
        overlap = _declared_upstream_overlap(
            block,
            changed_paths,
            include=include_upstream,
        )
        return owned, overlap, declared_patterns

    probe_specs = _registered_probe_specs(active, archived)
    unknown_results = set(probe_results) - set(probe_specs)
    if unknown_results:
        raise EvidenceError(f"PATCH evidence produced results for unknown probes: {sorted(unknown_results)}")

    def probe_fields(patch_id: str) -> dict[str, object]:
        function_name, minimum_mode = probe_specs[patch_id]
        executed = probe_results.get(patch_id, [])
        executed_names = [str(result.get("probe") or "") for result in executed]
        eligible = MODE_RANK[mode] >= MODE_RANK[minimum_mode]
        if eligible and executed_names != [function_name]:
            raise EvidenceError(
                f"{patch_id}: registered probe was not executed exactly once in {mode} mode: "
                f"expected={[function_name]}, actual={executed_names}"
            )
        if not eligible and executed:
            raise EvidenceError(f"{patch_id}: full-only probe unexpectedly ran in quick mode")
        if any(result.get("status") != "passed" for result in executed):
            raise EvidenceError(f"{patch_id}: registered probe did not report passed")
        return {
            "status": "passed" if mode == "full" else ("checked_quick" if eligible else "deferred_full"),
            "evidence": [function_name],
            "probe_results": executed,
        }

    records: list[dict[str, object]] = []
    for patch_id, block in active.items():
        owned_files, overlap, declared_patterns = ownership(
            patch_id,
            block,
            lifecycle="active",
        )
        common = {
            "id": patch_id,
            "lifecycle": "active",
            "owned_files": owned_files,
            "declared_file_patterns": declared_patterns,
            "upstream_overlap": overlap,
            "absorption_condition_present": "**上游吸收判断**" in block,
        }
        if patch_id in EXTERNAL_EVIDENCE_AUDITS:
            evidence_path, _function_name, _minimum_mode = EXTERNAL_EVIDENCE_AUDITS[patch_id]
            records.append(
                {
                    **common,
                    "evidence_type": "external_verifier",
                    "evidence_path": evidence_path,
                    **probe_fields(patch_id),
                }
            )
        elif patch_id in RUNTIME_EVIDENCE:
            records.append(
                {
                    **common,
                    "evidence_type": "runtime_contract",
                    "contract": list(RUNTIME_EVIDENCE[patch_id]),
                    **probe_fields(patch_id),
                }
            )
        elif patch_id in DEDICATED_EVIDENCE_AUDITS:
            records.append(
                {
                    **common,
                    "evidence_type": "dedicated_audit",
                    **probe_fields(patch_id),
                }
            )
        else:
            records.append(
                {
                    **common,
                    "evidence_type": "pytest_node",
                    "status": "passed" if mode == "full" else "not_run_quick",
                    "evidence": resolved.get(patch_id, []),
                    "executed_owned_files": (executed_owned_files or {}).get(patch_id, []),
                }
            )
    for patch_id, block in archived.items():
        owned_files, overlap, declared_patterns = ownership(
            patch_id,
            block,
            lifecycle="archived",
        )
        records.append(
            {
                "id": patch_id,
                "lifecycle": "archived",
                "owned_files": owned_files,
                "declared_file_patterns": declared_patterns,
                "upstream_overlap": overlap,
                "absorption_condition_present": "**上游吸收判断**" in block,
                "evidence_type": "archive_behavior_or_retirement_audit",
                **probe_fields(patch_id),
            }
        )
    if upgrade_range is not None:
        for record in records:
            record["upgrade_range"] = upgrade_range
    active_owned = {
        path for record in records if record["lifecycle"] == "active" for path in record.get("owned_files", [])
    }
    missing_owners = sorted(set(managed_files) - active_owned)
    if missing_owners:
        raise EvidenceError(f"managed files have no active PATCH ownership: {missing_owners}")
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip the expensive full test collection.")
    parser.add_argument(
        "--report-json",
        help="Write the per-PATCH evidence matrix to this path, or '-' for stdout.",
    )
    args = parser.parse_args()
    mode = "quick" if args.quick else "full"
    report_path = Path(args.report_json) if args.report_json and args.report_json != "-" else None
    if report_path is not None:
        try:
            report_path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"patch-evidence self-test FAILED: could not clear stale report: {exc}", file=sys.stderr)
            return 1
    try:
        active, archived = audit_registry()
        audit_gate_links(active, archived)
        audit_runtime_artifacts()
        probe_results = _run_registered_patch_audits(active, archived, mode=mode)
        npm_probe = probe_results.get("PATCH-NPM-DEPENDENCY-HYGIENE", [])
        npm = npm_probe[0].get("details", {}) if npm_probe else {"status": "deferred_full"}
        tests: dict[str, object] = {
            "files": 0,
            "collected": 0,
            "support_files": 0,
            "support_file_paths": [],
            "support_file_consumers": {},
        }
        resolved: dict[str, list[str]] = {}
        executed_owned_files: dict[str, list[str]] = {}
        if not args.quick:
            tests, resolved, executed_owned_files = audit_current_tests(active)
        report = {
            "status": "ok",
            "mode": mode,
            "execution_scope": "per_patch_process" if mode == "full" else "deferred_full",
            "active": len(active),
            "archived": len(archived),
            **tests,
            "npm": npm,
            "probes": {
                "registered": len(_registered_probe_specs(active, archived)),
                "executed": sum(len(results) for results in probe_results.values()),
                "deferred": len(_registered_probe_specs(active, archived))
                - sum(len(results) for results in probe_results.values()),
            },
            "module_import_evidence": {
                patch_id: list(paths) for patch_id, paths in sorted(MODULE_IMPORT_EVIDENCE.items())
            },
            "patches": _evidence_records(
                active,
                archived,
                resolved,
                mode=mode,
                probe_results=probe_results,
                executed_owned_files=executed_owned_files,
            ),
        }
    except (EvidenceError, subprocess.SubprocessError, OSError) as exc:
        report = {"status": "failed", "mode": mode, "error": str(exc)}
        if args.report_json:
            payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            if args.report_json == "-":
                sys.stdout.write(payload)
            else:
                report_path.write_text(payload, encoding="utf-8")
        print(f"patch-evidence self-test FAILED: {exc}", file=sys.stderr)
        return 1
    if args.report_json:
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report_json == "-":
            sys.stdout.write(payload)
            return 0
        Path(args.report_json).write_text(payload, encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "mode",
                    "active",
                    "archived",
                    "files",
                    "collected",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
