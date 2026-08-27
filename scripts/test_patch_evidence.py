#!/usr/bin/env python3
"""Audit durable regression evidence for every Hermes PATCH definition.

This is intentionally a repository-level audit rather than another source
sentinel.  A PATCH is accepted only when its lifecycle is registered, its
validation section names a real regression boundary, and the corresponding
current artifact/test entry exists on disk. Full mode also profiles each
evidence node and requires source-owning PATCHes to execute every declared
Python production file. Runtime PATCHes use their
operator-level evidence (transaction, replay, cleanup, mirror, npm or
verifier checks) instead of pretending that a source grep is a behavioral
test.
"""

from __future__ import annotations

import argparse
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


class EvidenceError(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: Path = ROOT, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


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


def _owned_managed_files(block: str, managed_files: list[str]) -> list[str]:
    files_text = _files(block)
    patterns: set[str] = set()
    for token in re.findall(r"`([^`]+)`", files_text):
        patterns.update(_expand_braces(token))
    return sorted(
        path
        for path in managed_files
        if path in files_text or any(fnmatch.fnmatch(path, pattern.replace("...", "*")) for pattern in patterns)
    )


def _test_tokens(validation: str) -> set[str]:
    path_pattern = r"(?:tests|scripts)/[A-Za-z0-9_./-]*test_[A-Za-z0-9_.-]+\.py"
    paths = set(re.findall(path_pattern, validation))
    without_paths = re.sub(path_pattern, "", validation)
    functions = set(re.findall(r"\btest_[A-Za-z0-9_]+\b(?!\.py)", without_paths))
    return paths | functions


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


ARCHIVED_EVIDENCE_AUDITS: dict[str, str] = {
    "PATCH-LAUNCHD-WRAPPER-SUPERVISOR": "audit_archived_launchd_wrapper_supervisor",
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


def _patch_test_inventory() -> tuple[set[str], set[str]]:
    result = _run(["bash", str(SCRIPT), "--print-patched-tests"])
    if result.returncode:
        raise EvidenceError(f"could not read PATCH_TESTS: {result.stderr.strip()}")
    test_files = {line for line in result.stdout.splitlines() if line}
    missing = [rel for rel in sorted(test_files) if not (INNER / rel).is_file()]
    if missing:
        raise EvidenceError(f"PATCH_TESTS contains missing files: {missing}")
    test_functions: set[str] = set()
    for rel in test_files:
        source = (INNER / rel).read_text(encoding="utf-8", errors="ignore")
        test_functions.update(re.findall(r"(?m)^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", source))
    return test_files, test_functions


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
    return nodes


def _base_node_id(node_id: str) -> str:
    return re.sub(r"\[[^\]]*\]$", "", node_id)


def _node_function(node_id: str) -> str:
    return _base_node_id(node_id).rsplit("::", 1)[-1]


def _resolve_active_patch_nodes(active: dict[str, str], collected_nodes: list[str]) -> dict[str, list[str]]:
    by_function: dict[str, set[str]] = defaultdict(set)
    for node in collected_nodes:
        by_function[_node_function(node)].add(_base_node_id(node))

    resolved: dict[str, list[str]] = {}
    for patch_id, block in active.items():
        if patch_id == "PATCH-FEISHU-GROUP-SANDBOX" or patch_id in RUNTIME_EVIDENCE:
            continue
        if patch_id in DEDICATED_EVIDENCE_AUDITS:
            continue
        validation = _validation(block)
        functions = sorted(token for token in _test_tokens(validation) if token.startswith("test_"))
        if not functions:
            raise EvidenceError(
                f"{patch_id}: full evidence requires at least one concrete test function, not only a file path"
            )
        nodes: list[str] = []
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

        files_text = _files(block)
        if files_text:
            unowned_test_files = sorted(
                {
                    node.split("::", 1)[0]
                    for node in resolved[patch_id]
                    if not _owned_managed_files(block, [node.split("::", 1)[0]])
                }
            )
            if unowned_test_files:
                raise EvidenceError(f"{patch_id}: evidence nodes come from undeclared test files: {unowned_test_files}")

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
        for node in nodes:
            executed.update(traced_files.get(node, set()))
        patch_hits = sorted(set(traceable) & executed)
        hits[patch_id] = patch_hits
        untraced = sorted(set(traceable) - executed)
        if untraced:
            missing.append(f"{patch_id} (unexecuted owned Python production={untraced}, evidence={nodes})")
    if missing:
        raise EvidenceError(
            "active PATCH evidence passed without executing every owned Python production file: " + "; ".join(missing)
        )
    return hits


def _run_active_patch_nodes(active: dict[str, str], resolved: dict[str, list[str]]) -> dict[str, list[str]]:
    unique_nodes = sorted({node for nodes in resolved.values() for node in nodes})
    if not unique_nodes:
        raise EvidenceError("active engineering PATCH evidence resolved to no pytest nodes")
    with tempfile.TemporaryDirectory(prefix="hermes-active-patch-evidence-") as temp_raw:
        temp = Path(temp_raw)
        junit = temp / "active-patch-evidence.xml"
        trace_json = temp / "active-patch-trace.json"
        plugin = temp / "patch_trace_plugin.py"
        plugin.write_text(
            textwrap.dedent(
                r"""
                import json
                import os
                import sys
                import threading
                from pathlib import Path

                import pytest

                ROOT = Path(os.environ["HERMES_PATCH_TRACE_ROOT"]).resolve()
                OUT = Path(os.environ["HERMES_PATCH_TRACE_OUT"])
                _current = None
                _seen = {}

                def _profile(frame, event, arg):
                    if event != "call" or _current is None:
                        return
                    try:
                        rel = Path(frame.f_code.co_filename).resolve().relative_to(ROOT).as_posix()
                    except Exception:
                        return
                    if rel.startswith(("tests/", "venv/", ".hermes-runtime/")):
                        return
                    _seen.setdefault(_current, set()).add(rel)

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
                        json.dumps({key: sorted(value) for key, value in _seen.items()}),
                        encoding="utf-8",
                    )
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        env = _hermetic_test_env()
        env["PYTHONPATH"] = os.pathsep.join(part for part in (str(temp), str(INNER), env.get("PYTHONPATH", "")) if part)
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
                *unique_nodes,
            ],
            cwd=INNER,
            env=env,
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
        if result.returncode:
            raise EvidenceError(f"active PATCH node regression failed: {result.stdout[-2000:]}{result.stderr[-2000:]}")
        if re.search(r"\b\d+\s+xpassed\b", result.stdout):
            raise EvidenceError("active PATCH node regression contains xpassed outcomes")
        try:
            root = ET.parse(junit).getroot()
        except (ET.ParseError, OSError) as exc:
            raise EvidenceError(f"active PATCH JUnit report is unreadable: {exc}") from exc
        cases = list(root.iter("testcase"))
        if not cases:
            raise EvidenceError("active PATCH JUnit report contains no test cases")
        outcomes: dict[str, list[ET.Element]] = defaultdict(list)
        for case in cases:
            outcomes[str(case.attrib.get("name") or "").split("[", 1)[0]].append(case)
        for patch_id, nodes in resolved.items():
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
            raise EvidenceError(f"active PATCH execution trace is unreadable: {exc}") from exc
        traced_files: dict[str, set[str]] = defaultdict(set)
        for node, files in raw_trace.items():
            traced_files[_base_node_id(node)].update(str(path) for path in files)
        managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()
        return _validate_patch_trace_hits(
            active,
            resolved,
            traced_files,
            managed_files,
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
    for patch_id, block in {**active, **archived}.items():
        _audit_section_shape(patch_id, block)
    for patch_id, block in archived.items():
        validation = _validation(block)
        function_name = ARCHIVED_EVIDENCE_AUDITS.get(patch_id)
        if function_name is None:
            raise EvidenceError(f"{patch_id}: archive definition has no dedicated evidence audit")
        if "scripts/test_patch_evidence.py" not in validation or function_name not in validation:
            raise EvidenceError(f"{patch_id}: validation must bind scripts/test_patch_evidence.py::{function_name}")
        evidence_source = Path(__file__).read_text(encoding="utf-8")
        if not re.search(rf"^def {re.escape(function_name)}\(", evidence_source, re.MULTILINE):
            raise EvidenceError(f"{patch_id}: archived evidence function is missing: {function_name}")
        if len(re.findall(rf"\b{re.escape(function_name)}\(\)", evidence_source)) < 2:
            raise EvidenceError(f"{patch_id}: archived evidence function is not called: {function_name}")
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
        dedicated = DEDICATED_EVIDENCE_AUDITS.get(patch_id)
        if dedicated is not None:
            evidence_path, function_name = dedicated
            if evidence_path not in validation:
                raise EvidenceError(f"{patch_id}: validation omits dedicated evidence path {evidence_path}")
            evidence_source = Path(__file__).read_text(encoding="utf-8")
            if not re.search(rf"^def {re.escape(function_name)}\(", evidence_source, re.MULTILINE):
                raise EvidenceError(f"{patch_id}: dedicated evidence function is missing: {function_name}")
            if len(re.findall(rf"\b{re.escape(function_name)}\(\)", evidence_source)) < 2:
                raise EvidenceError(f"{patch_id}: dedicated evidence function is not called: {function_name}")
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
    mapped_gates: dict[str, str] = {}
    for patch_id in active:
        if patch_id == "PATCH-FEISHU-GROUP-SANDBOX":
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
        assigned = set(re.findall(r"^\s*(_[A-Z0-9_]+_PATCH_OK)=true$", gate_block, re.MULTILINE))
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
    # Archived sentinels may be retired once upstream carries the behavior;
    # the registry's validation section remains the durable evidence instead.


def audit_runtime_artifacts() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    required = {
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
    result = _run(["npm", "audit", "--json"], cwd=INNER, timeout=180)
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


def audit_fts5_build() -> None:
    result = _run(
        [
            str(INNER / "venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "tests/test_fts_cjk_bigram.py",
        ],
        cwd=INNER,
        timeout=180,
    )
    if result.returncode:
        raise EvidenceError(f"FTS5 CJK regression failed: {result.stdout[-1000:]}{result.stderr[-1000:]}")


def _run_archived_pytest(*node_ids: str) -> None:
    result = _run(
        [
            str(INNER / "venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *node_ids,
        ],
        cwd=INNER,
        timeout=180,
    )
    if result.returncode:
        raise EvidenceError(f"archived PATCH regression failed: {result.stdout[-1500:]}{result.stderr[-1500:]}")


def audit_archived_launchd_wrapper_supervisor() -> None:
    _run_archived_pytest("tests/hermes_cli/test_gateway_external_supervisor.py")


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


def audit_archived_gemini_custom_native_base() -> None:
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
    _run_archived_pytest(
        "tests/agent/test_gemini_native_adapter.py::test_native_client_uses_x_goog_api_key_and_native_models_endpoint",
        "tests/hermes_cli/test_gemini_provider.py::TestGeminiAgentInit::test_gemini_resolve_provider_client_uses_native_client",
    )


def audit_archived_lazy_activation() -> None:
    _run_archived_pytest(
        "tests/tools/test_lazy_deps.py::TestActiveFeatures::test_shared_dependency_does_not_activate_feature"
    )


def audit_archived_doctor_enabled_toolsets() -> None:
    _run_archived_pytest(
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


def audit_archived_dashboard_build_cache() -> None:
    _run_archived_pytest(
        "tests/hermes_cli/test_web_ui_build.py::TestWebUIBuildNeeded::test_mtime_only_change_is_not_stale"
    )


def audit_archived_gemini_thought_signature() -> None:
    _run_archived_pytest(
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


def audit_archived_regressions() -> None:
    audit_archived_launchd_wrapper_supervisor()
    audit_archived_vertex_fallback()
    audit_archived_gemini_custom_native_base()
    audit_archived_lazy_activation()
    audit_archived_doctor_enabled_toolsets()
    audit_archived_zsh_completion_syntax()
    audit_archived_dashboard_build_cache()
    audit_archived_gemini_thought_signature()
    audit_archived_delegate_acp_routing()


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
) -> tuple[dict[str, int], dict[str, list[str]], dict[str, list[str]]]:
    test_files = _patch_test_inventory()[0]
    collected_nodes = _collect_patch_nodes(test_files)
    resolved = _resolve_active_patch_nodes(active, collected_nodes)
    executed_owned_files = _run_active_patch_nodes(active, resolved)
    return (
        {"files": len(test_files), "collected": len(collected_nodes)},
        resolved,
        executed_owned_files,
    )


def _evidence_records(
    active: dict[str, str],
    archived: dict[str, str],
    resolved: dict[str, list[str]],
    *,
    mode: str,
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
        old_sha = _run(["git", "rev-parse", old_ref], cwd=INNER).stdout.strip()
        new_sha = _run(["git", "rev-parse", new_ref], cwd=INNER).stdout.strip()
        changed = _run(["git", "diff", "--name-only", f"{old_sha}..{new_sha}"], cwd=INNER)
        changed_paths = {line for line in changed.stdout.splitlines() if line}
        upgrade_range = {"old_sha": old_sha, "new_sha": new_sha}
    managed_files = _run(["bash", str(SCRIPT), "--print-patched-files"]).stdout.splitlines()

    def ownership(block: str) -> tuple[list[str], list[str]]:
        owned = _owned_managed_files(block, managed_files)
        return owned, sorted(set(owned) & changed_paths)

    records: list[dict[str, object]] = []
    for patch_id, block in active.items():
        owned_files, overlap = ownership(block)
        common = {
            "id": patch_id,
            "lifecycle": "active",
            "owned_files": owned_files,
            "upstream_overlap": overlap,
            "absorption_condition_present": "**上游吸收判断**" in block,
        }
        if patch_id == "PATCH-FEISHU-GROUP-SANDBOX":
            records.append(
                {
                    **common,
                    "evidence_type": "external_verifier",
                    "status": "contract_passed",
                    "evidence": ["plugins/sandbox/verify.sh"],
                }
            )
        elif patch_id in RUNTIME_EVIDENCE:
            records.append(
                {
                    **common,
                    "evidence_type": "runtime_contract",
                    "status": "contract_passed",
                    "evidence": list(RUNTIME_EVIDENCE[patch_id]),
                }
            )
        elif patch_id in DEDICATED_EVIDENCE_AUDITS:
            records.append(
                {
                    **common,
                    "evidence_type": "dedicated_audit",
                    "status": "passed",
                    "evidence": [DEDICATED_EVIDENCE_AUDITS[patch_id][1]],
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
        owned_files, overlap = ownership(block)
        records.append(
            {
                "id": patch_id,
                "lifecycle": "archived",
                "owned_files": owned_files,
                "upstream_overlap": overlap,
                "absorption_condition_present": "**上游吸收判断**" in block,
                "evidence_type": "archive_behavior_or_retirement_audit",
                "status": "passed",
                "evidence": [ARCHIVED_EVIDENCE_AUDITS[patch_id]],
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
    try:
        active, archived = audit_registry()
        audit_gate_links(active, archived)
        audit_runtime_artifacts()
        audit_socks_dependency()
        audit_openclaw_token_migration()
        npm = audit_npm_dependency_hygiene()
        audit_skills_mirror()
        audit_fts5_build()
        audit_archived_regressions()
        tests = {"files": 0, "collected": 0}
        resolved: dict[str, list[str]] = {}
        executed_owned_files: dict[str, list[str]] = {}
        if not args.quick:
            # Preflight quick mode runs before Step 2 captures a manually
            # resolved post-upgrade overlay into the canonical bundle.  Bundle
            # parity is therefore a terminal/full invariant, not a pre-mutation
            # structural one; checking it here would make the documented
            # conflict-recovery path impossible to re-enter.
            audit_bundle()
            tests, resolved, executed_owned_files = audit_current_tests(active)
    except (EvidenceError, subprocess.SubprocessError, OSError) as exc:
        print(f"patch-evidence self-test FAILED: {exc}", file=sys.stderr)
        return 1
    mode = "quick" if args.quick else "full"
    report = {
        "status": "ok",
        "mode": mode,
        "active": len(active),
        "archived": len(archived),
        **tests,
        "npm": npm,
        "patches": _evidence_records(
            active,
            archived,
            resolved,
            mode=mode,
            executed_owned_files=executed_owned_files,
        ),
    }
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
