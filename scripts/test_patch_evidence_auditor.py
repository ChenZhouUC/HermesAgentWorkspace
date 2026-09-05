from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import final_upgrade_audit as final_audit
import test_patch_evidence as evidence
from final_upgrade_audit import _current_week_readme_rows, _markdown_table_summary


def patch_block(validation: str) -> str:
    return (
        "### [PATCH-TEST-CONTRACT] synthetic\n\n"
        "| **文件** | `tests/test_contract.py` |\n\n"
        "**问题**：problem\n\n"
        "**修复**：fix\n\n"
        f"**验证**：{validation}\n\n"
        "**上游吸收判断**：absorb\n"
    )


class PatchEvidenceAuditorTest(unittest.TestCase):
    def test_final_audit_runs_independent_checks_concurrently(self) -> None:
        barrier = threading.Barrier(4)

        def wait_and_return(value):
            barrier.wait(timeout=2)
            return value

        with tempfile.TemporaryDirectory() as temp_raw:
            with (
                patch.dict(os.environ, {"HERMES_FINAL_AUDIT_PARALLELISM": "4"}),
                patch.object(
                    final_audit,
                    "_load_full_patch_evidence",
                    side_effect=lambda _path: wait_and_return(({"status": "ok"}, {"passed": 1})),
                ),
                patch.object(
                    final_audit,
                    "_run_canonical_patch_tests",
                    side_effect=lambda _files: wait_and_return({"files": 1}),
                ),
                patch.object(
                    final_audit,
                    "_run_wiki_lint",
                    side_effect=lambda: wait_and_return({"issues": 0}),
                ),
                patch.object(
                    final_audit,
                    "_doctor_health",
                    side_effect=lambda: wait_and_return({"issue_count": 0}),
                ),
            ):
                results, durations = final_audit._run_parallel_readonly_audits(
                    ["tests/test_contract.py"],
                    Path(temp_raw) / "evidence.json",
                )

        self.assertEqual(set(results), {"patch_evidence", "canonical_tests", "wiki_lint", "doctor"})
        self.assertEqual(results["canonical_tests"], {"files": 1})
        self.assertEqual(set(durations), {*results, "parallel_wall"})

    def test_patch_evidence_parallelism_is_bounded(self) -> None:
        with patch.dict(os.environ, {"HERMES_PATCH_EVIDENCE_JOBS": "999"}):
            self.assertEqual(evidence._patch_evidence_parallelism(100), 8)
        with patch.dict(os.environ, {"HERMES_PATCH_EVIDENCE_JOBS": "invalid"}):
            self.assertEqual(evidence._patch_evidence_parallelism(3), 3)

    def test_registered_patch_audits_run_concurrently_with_stable_results(self) -> None:
        barrier = threading.Barrier(3)
        specs = {
            "PATCH-A": ("audit_a", "quick"),
            "PATCH-B": ("audit_b", "quick"),
            "PATCH-C": ("audit_c", "quick"),
        }

        def resolve(name):
            def run():
                barrier.wait(timeout=2)
                return {"name": name}

            return run

        with (
            patch.dict(os.environ, {"HERMES_PATCH_EVIDENCE_JOBS": "3"}),
            patch.object(evidence, "_registered_probe_specs", return_value=specs),
            patch.object(evidence, "_resolve_audit_function", side_effect=resolve),
        ):
            result = evidence._run_registered_patch_audits({}, {}, mode="full")

        self.assertEqual(list(result), list(specs))
        self.assertEqual(
            [result[patch_id][0]["details"]["name"] for patch_id in specs],
            ["audit_a", "audit_b", "audit_c"],
        )

    def test_npm_audit_timeout_is_reported_as_telemetry_unavailable(self) -> None:
        timeout = subprocess.TimeoutExpired(["npm", "audit", "--json"], 180)
        with patch.object(evidence, "_run", side_effect=timeout):
            result = evidence.audit_npm_dependency_hygiene()
        self.assertEqual(result["status"], "telemetry_unavailable")
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["timeout_seconds"], 180)

    def test_patch_trace_plugin_caches_code_filename_resolution(self) -> None:
        source = evidence._patch_trace_plugin_source()
        self.assertIn("_relative_cache", source)
        self.assertIn("os.path.realpath(filename)", source)
        self.assertIn("if filename in _relative_cache", source)
        self.assertNotIn("Path(frame.f_code.co_filename).resolve()", source)

    def test_duplicate_patch_definition_in_one_lifecycle_is_rejected(self) -> None:
        duplicate = patch_block("test_first") + "\n" + patch_block("test_second")
        with self.assertRaisesRegex(evidence.EvidenceError, "duplicate active PATCH definitions"):
            evidence._blocks(duplicate, archive=False)

    def test_quick_mode_defers_bundle_parity_until_full_audit(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["test_patch_evidence.py", "--quick"]))
            stack.enter_context(patch.object(evidence, "audit_registry", return_value=({}, {})))
            stack.enter_context(patch.object(evidence, "audit_gate_links"))
            stack.enter_context(patch.object(evidence, "audit_runtime_artifacts"))
            registered = stack.enter_context(patch.object(evidence, "_run_registered_patch_audits", return_value={}))
            stack.enter_context(patch.object(evidence, "_registered_probe_specs", return_value={}))
            stack.enter_context(patch.object(evidence, "_evidence_records", return_value=[]))
            self.assertEqual(evidence.main(), 0)
        registered.assert_called_once_with({}, {}, mode="quick")

    def test_failed_evidence_run_replaces_stale_success_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            report = Path(temp_raw) / "report.json"
            report.write_text('{"status":"ok"}\n', encoding="utf-8")
            with (
                patch.object(sys, "argv", ["test_patch_evidence.py", "--report-json", str(report)]),
                patch.object(
                    evidence,
                    "audit_registry",
                    side_effect=evidence.EvidenceError("synthetic failure"),
                ),
            ):
                self.assertEqual(evidence.main(), 1)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"], "failed")

    def test_runtime_patch_without_registered_probe_is_rejected(self) -> None:
        patch_id = "PATCH-TEST-RUNTIME"
        active = {patch_id: patch_block("runtime contract")}
        with (
            patch.dict(evidence.RUNTIME_EVIDENCE, {patch_id: ("runtime contract",)}, clear=True),
            patch.dict(evidence.RUNTIME_EVIDENCE_AUDITS, {}, clear=True),
            patch.dict(evidence.RUNTIME_ARTIFACT_NEEDLES, {patch_id: ("artifact",)}, clear=True),
            patch.dict(evidence.DEDICATED_EVIDENCE_AUDITS, {}, clear=True),
            patch.dict(evidence.EXTERNAL_EVIDENCE_AUDITS, {}, clear=True),
            patch.dict(evidence.ARCHIVED_EVIDENCE_AUDITS, {}, clear=True),
            self.assertRaisesRegex(evidence.EvidenceError, "runtime PATCH evidence mappings drift"),
        ):
            evidence._audit_registered_probe_contract(active, {})

    def test_direct_update_pytest_gates_require_every_strict_warning_filter(self) -> None:
        filters = "\n".join(evidence.PYTEST_STRICT_WARNING_ARGS)
        command = (
            '"${VENV_PY}" -m pytest -q "${PYTEST_STRICT_WARNING_ARGS[@]}" tests/test_contract.py >/dev/null 2>&1; then'
        )
        script = f"PYTEST_STRICT_WARNING_ARGS=(\n{filters}\n)\n{command}\n"
        self.assertEqual(evidence._validate_update_pytest_warning_filters(script), 1)
        with self.assertRaisesRegex(evidence.EvidenceError, "omit strict warning filters"):
            evidence._validate_update_pytest_warning_filters(script.replace(' "${PYTEST_STRICT_WARNING_ARGS[@]}"', ""))
        with self.assertRaisesRegex(evidence.EvidenceError, "array is incomplete"):
            evidence._validate_update_pytest_warning_filters(
                script.replace("error::pytest.PytestUnraisableExceptionWarning", "")
            )
        with self.assertRaisesRegex(evidence.EvidenceError, "inventory is incomplete"):
            evidence._validate_update_pytest_warning_filters(
                script + '\n"${VENV_PY}" -m pytest tests/test_unchecked.py\n'
            )

    def test_sandbox_pytest_command_requires_every_strict_warning_filter(self) -> None:
        filters = " ".join(f"-W {warning_filter}" for warning_filter in evidence.PYTEST_STRICT_WARNING_ARGS[1::2])
        command = f'"${{VENV_PYTHON}}" -m pytest -q {filters} --junitxml="$JUNIT" tests 2>&1'
        self.assertEqual(evidence._validate_verifier_pytest_warning_filters(command), 1)
        with self.assertRaisesRegex(evidence.EvidenceError, "omit strict warning filters"):
            evidence._validate_verifier_pytest_warning_filters(
                command.replace("-W error::pytest.PytestCollectionWarning", "")
            )
        with self.assertRaisesRegex(evidence.EvidenceError, "inventory is incomplete"):
            evidence._validate_verifier_pytest_warning_filters(
                command + '\n"${VENV_PYTHON}" -m pytest tests/test_unchecked.py\n'
            )

    def test_sandbox_mcp_receipt_must_bind_current_gateway_pid(self) -> None:
        exact = (
            "grep \"MCP server 'hypertex'.*pid=${gateway_pid}.*"
            "mcp__hypertex__tasks_get.*mcp__hypertex__tasks_cancel.*"
            'mcp__hypertex__tasks_update"'
        )
        evidence._validate_sandbox_runtime_pid_binding(exact)
        with self.assertRaisesRegex(evidence.EvidenceError, "current gateway PID"):
            evidence._validate_sandbox_runtime_pid_binding(exact.replace(".*pid=${gateway_pid}", ""))

    def test_registered_probe_is_executed_once_and_recorded(self) -> None:
        patch_id = "PATCH-TEST-RUNTIME"
        active = {patch_id: patch_block("runtime contract")}
        probe = Mock(return_value={"proof": "fresh"})
        with (
            patch.dict(evidence.RUNTIME_EVIDENCE, {patch_id: ("runtime contract",)}, clear=True),
            patch.dict(
                evidence.RUNTIME_EVIDENCE_AUDITS,
                {patch_id: ("audit_synthetic_runtime", "quick")},
                clear=True,
            ),
            patch.dict(evidence.RUNTIME_ARTIFACT_NEEDLES, {patch_id: ("artifact",)}, clear=True),
            patch.dict(evidence.DEDICATED_EVIDENCE_AUDITS, {}, clear=True),
            patch.dict(evidence.EXTERNAL_EVIDENCE_AUDITS, {}, clear=True),
            patch.dict(evidence.ARCHIVED_EVIDENCE_AUDITS, {}, clear=True),
            patch.object(evidence, "audit_synthetic_runtime", probe, create=True),
        ):
            result = evidence._run_registered_patch_audits(active, {}, mode="full")
        probe.assert_called_once_with()
        self.assertEqual(
            result,
            {
                patch_id: [
                    {
                        "probe": "audit_synthetic_runtime",
                        "status": "passed",
                        "details": {"proof": "fresh"},
                    }
                ]
            },
        )

    def test_full_report_cannot_promote_an_unexecuted_probe(self) -> None:
        text = evidence.PATCHES.read_text(encoding="utf-8")
        active = evidence._blocks(text, archive=False)
        archived = evidence._blocks(text, archive=True)
        with self.assertRaisesRegex(evidence.EvidenceError, "was not executed exactly once"):
            evidence._evidence_records(
                active,
                archived,
                {},
                mode="full",
                probe_results={},
            )

    def test_final_canonical_suite_disables_flake_retries(self) -> None:
        completed = subprocess.CompletedProcess(
            ["run_tests.sh"],
            0,
            "=== Summary: 1 files, 2 tests passed, 0 failed (100% complete) in 1.0s (1 workers) ===\n",
            "",
        )
        with patch.object(final_audit, "_run", return_value=completed) as run:
            final_audit._run_canonical_patch_tests(["tests/test_contract.py"])
        argv = run.call_args.args[1]
        self.assertIn(
            ["--file-retries", "0"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )
        self.assertIn("--", argv)
        self.assertIn(
            ["-W", "error::pytest.PytestUnhandledThreadExceptionWarning"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )
        self.assertIn(
            ["-W", "error::pytest.PytestUnraisableExceptionWarning"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )
        self.assertIn(
            ["-W", "error::RuntimeWarning"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )
        self.assertIn(
            ["-W", "error::pytest.PytestReturnNotNoneWarning"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )
        self.assertIn(
            ["-W", "error::pytest.PytestCollectionWarning"],
            [argv[index : index + 2] for index in range(len(argv) - 1)],
        )

    def test_final_canonical_suite_rejects_flaky_green_output(self) -> None:
        completed = subprocess.CompletedProcess(
            ["run_tests.sh"],
            0,
            "=== Summary: 1 files, 2 tests passed, 0 failed (100% complete) in 1.0s (1 workers) ===\n"
            "=== ⚠ 1 FLAKY file (failed once, passed on retry — fix these) ===\n",
            "",
        )
        with (
            patch.object(final_audit, "_run", return_value=completed),
            self.assertRaisesRegex(final_audit.FinalAuditError, "pass-on-retry flake"),
        ):
            final_audit._run_canonical_patch_tests(["tests/test_contract.py"])

    def test_final_canonical_coverage_must_match_collected_nodes(self) -> None:
        final_audit._validate_canonical_coverage(
            {"files": 2, "passed": 7, "failed": 0, "skipped": 1},
            {"files": 2, "collected": 8},
        )
        with self.assertRaisesRegex(
            final_audit.FinalAuditError,
            "do not cover the full collected PATCH suite",
        ):
            final_audit._validate_canonical_coverage(
                {"files": 2, "passed": 6, "failed": 0, "skipped": 1},
                {"files": 2, "collected": 8},
            )

    def test_absorption_matrix_covers_every_overlap_once(self) -> None:
        records = [
            {"id": "PATCH-A", "lifecycle": "active", "upstream_overlap": ["a.py"]},
            {"id": "PATCH-B", "lifecycle": "active", "upstream_overlap": []},
            {"id": "PATCH-C", "lifecycle": "archived", "upstream_overlap": ["c.py"]},
        ]
        counts = "本轮 1 个 active 与 1 个受管路径相交，1 个 Archive 与 1 个声明路径相交；active/Archive 去重后 2 条；"
        self.assertEqual(
            final_audit._validate_absorption_matrix(
                records,
                counts + "`PATCH-A`=部分吸收；`PATCH-C`=完全吸收；无路径相交=1",
            ),
            {
                "overlap_verdicts": 2,
                "active_no_overlap": 1,
                "active_patches": 1,
                "active_paths": 1,
                "archived_patches": 1,
                "archived_paths": 1,
                "unique_paths": 2,
            },
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "matrix drift"):
            final_audit._validate_absorption_matrix(
                records,
                counts + "`PATCH-C`=完全吸收；无路径相交=1",
            )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "conflicts with lifecycle"):
            final_audit._validate_absorption_matrix(
                records,
                counts + "`PATCH-A`=完全吸收；`PATCH-C`=完全吸收；无路径相交=1",
            )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "path count drift"):
            final_audit._validate_absorption_matrix(
                records,
                counts.replace("去重后 2 条", "去重后 3 条") + "`PATCH-A`=部分吸收；`PATCH-C`=完全吸收；无路径相交=1",
            )

    def test_evidence_upgrade_range_must_end_at_current_head(self) -> None:
        old_sha = "a" * 40
        head = "b" * 40
        records = [
            {"upgrade_range": {"old_sha": old_sha, "new_sha": head}},
            {"upgrade_range": {"old_sha": old_sha, "new_sha": head}},
        ]
        self.assertEqual(
            final_audit._validate_evidence_upgrade_range(records, head),
            {"old_sha": old_sha, "new_sha": head},
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "stale or invalid"):
            final_audit._validate_evidence_upgrade_range(
                [{"upgrade_range": {"old_sha": old_sha, "new_sha": "c" * 40}}],
                head,
            )

    def test_patch_count_claims_must_match_evidence_lifecycles(self) -> None:
        records = [
            {"lifecycle": "active", "evidence_type": "pytest_node"},
            {"lifecycle": "active", "evidence_type": "runtime_contract"},
            {"lifecycle": "active", "evidence_type": "external_verifier"},
            {
                "lifecycle": "archived",
                "evidence_type": "archive_behavior_or_retirement_audit",
            },
        ]
        patches = "当前共 3 个语义补丁。1 个工程内补丁"
        readme = "维护 3 个按职责命名的活跃语义补丁：1 个工程内补丁"
        summary = "终态为 3 active + 1 Archive"
        self.assertEqual(
            final_audit._validate_patch_count_claims(records, patches, readme, summary),
            {"active": 3, "archived": 1, "engineering": 1},
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "count claims drift"):
            final_audit._validate_patch_count_claims(
                records,
                "当前共 4 个语义补丁。1 个工程内补丁",
                readme,
                summary,
            )

    def test_documented_regression_counts_must_match_final_results(self) -> None:
        canonical = {"files": 2, "passed": 7, "failed": 0, "skipped": 1}
        records = [{"id": "PATCH-A"}, {"id": "PATCH-B"}]
        summary = "final **2 files / 7 passed / 0 failed / 1 skipped**; 2/2 full PATCH evidence"
        self.assertEqual(
            final_audit._validate_documented_regression_counts(
                canonical,
                records,
                summary,
                summary,
            )["patch_evidence"],
            2,
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "canonical test count drift"):
            final_audit._validate_documented_regression_counts(
                canonical,
                records,
                "final **2 files / 6 passed / 0 failed / 1 skipped**",
                summary,
            )

    def test_documented_artifact_counts_must_match_full_evidence(self) -> None:
        evidence_report = {
            "collected": 42,
            "probes": {"registered": 7, "executed": 7, "deferred": 0},
        }
        summary = "42 collected、7/7 probe；9-file bundle"
        self.assertEqual(
            final_audit._validate_documented_artifact_counts(
                evidence_report,
                [f"file-{index}" for index in range(9)],
                summary,
            ),
            {
                "collected": 42,
                "registered_probes": 7,
                "executed_probes": 7,
                "deferred_probes": 0,
                "bundle_files": 9,
            },
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "artifact count drift"):
            final_audit._validate_documented_artifact_counts(
                evidence_report,
                [f"file-{index}" for index in range(9)],
                "41 collected、7/7 probe；9-file bundle",
            )

    def test_patch_base_requires_exact_sha_and_utc_timestamp(self) -> None:
        sha = "a" * 40
        self.assertEqual(
            final_audit._parse_patch_base(f"{sha} 2026-09-03T12:34:56Z\n"),
            (sha, "2026-09-03T12:34:56Z"),
        )
        for invalid in (
            f"{sha}\n",
            f"{sha} not-a-time\n",
            f"{sha} 2026-09-03T12:34:56Z\nextra\n",
        ):
            with self.assertRaisesRegex(final_audit.FinalAuditError, "must be exactly"):
                final_audit._parse_patch_base(invalid)

    def test_audit_snapshot_change_is_rejected(self) -> None:
        before = {"head": "a", "base": "a", "bundle_sha256": "one"}
        final_audit._validate_audit_snapshot(before, dict(before))
        with self.assertRaisesRegex(final_audit.FinalAuditError, "inputs changed"):
            final_audit._validate_audit_snapshot(
                before,
                {"head": "b", "base": "a", "bundle_sha256": "one"},
            )

    def test_workspace_snapshot_binds_clean_head_and_untracked_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "audit-test"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "audit@example.invalid"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", "/dev/null"], check=True)
            tracked = root / "tracked.txt"
            tracked.write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "one"], check=True)

            first = final_audit._workspace_snapshot(root, step="test")
            tracked.write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "commit", "-qam", "two"], check=True)
            second = final_audit._workspace_snapshot(root, step="test")
            self.assertNotEqual(first["head"], second["head"])
            self.assertNotEqual(first["digest"], second["digest"])

            untracked = root / "draft.txt"
            untracked.write_text("first", encoding="utf-8")
            third = final_audit._workspace_snapshot(root, step="test")
            untracked.write_text("second", encoding="utf-8")
            fourth = final_audit._workspace_snapshot(root, step="test")
            self.assertNotEqual(third["digest"], fourth["digest"])

    def test_dirty_package_lock_requires_matching_review_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            lock = root / "package-lock.json"
            receipt = root / "package-lock.review"
            lock.write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
            base_blob = "b" * 40
            digest = final_audit._sha256_file(lock)
            receipt.write_text(f"{base_blob} {digest}\n", encoding="utf-8")

            final_audit._validate_reviewed_package_lock(
                base_blob=base_blob,
                lock_path=lock,
                review_path=receipt,
            )
            receipt.write_text(f"{'c' * 40} {digest}\n", encoding="utf-8")
            with self.assertRaisesRegex(final_audit.FinalAuditError, "does not match"):
                final_audit._validate_reviewed_package_lock(
                    base_blob=base_blob,
                    lock_path=lock,
                    review_path=receipt,
                )

    def test_documented_sandbox_count_must_match_clean_verifier_result(self) -> None:
        summary = "sandbox/identity-sync **60 passed**"
        self.assertEqual(
            final_audit._validate_documented_sandbox_count(60, summary, summary),
            60,
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "sandbox regression count drift"):
            final_audit._validate_documented_sandbox_count(
                59,
                summary,
                summary,
            )

    def test_documented_test_support_count_must_match_evidence(self) -> None:
        summary = "另有 2 个 test support modules 做独立校验"
        self.assertEqual(
            final_audit._validate_documented_support_count(2, summary, summary),
            2,
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "support count drift"):
            final_audit._validate_documented_support_count(
                1,
                summary,
                summary,
            )

    def test_documented_gate_counts_must_match_declared_gates(self) -> None:
        script = """\
# -- 8b. Patch invariant gates
_FIRST_PATCH_OK=false
_SECOND_PATCH_OK=false
_ARCHIVED_ONE_OK=false
# -- 8c. Refresh saved diff
"""
        summary = "2 active + 1 archived gates"
        self.assertEqual(
            final_audit._validate_documented_gate_counts(script, summary, summary),
            {"active": 2, "archived": 1},
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "gate count drift"):
            final_audit._validate_documented_gate_counts(
                script,
                "1 active + 1 archived gates",
                summary,
            )

    def test_readme_summary_length_ignores_prettier_table_padding(self) -> None:
        row = "| v1.2.3 | 2026-08-23 | semantic summary" + (" " * 500) + " |"
        self.assertEqual(_markdown_table_summary(row), "semantic summary")

    def test_current_week_readme_rows_allow_same_version_across_weeks(self) -> None:
        readme = "\n".join(
            (
                "| v0.20.5 | 2026-08-26 | current week |",
                "| v0.20.5 | 2026-08-23 | previous week |",
            )
        )
        self.assertEqual(
            _current_week_readme_rows(readme, date(2026, 8, 26)),
            ["| v0.20.5 | 2026-08-26 | current week |"],
        )

    def test_final_repository_status_allows_only_unstaged_package_lock(self) -> None:
        self.assertEqual(
            final_audit._validate_inner_status(
                [
                    " M agent/feature.py",
                    "?? tests/test_feature.py",
                    " M package-lock.json",
                ],
                ["agent/feature.py", "tests/test_feature.py"],
            ),
            ["package-lock.json"],
        )

        with self.assertRaisesRegex(final_audit.FinalAuditError, "extra=.*notes.txt"):
            final_audit._validate_inner_status(
                [" M agent/feature.py", "?? notes.txt"],
                ["agent/feature.py"],
            )

        with self.assertRaisesRegex(final_audit.FinalAuditError, "invalid_reviewed"):
            final_audit._validate_inner_status(
                [" M agent/feature.py", "M  package-lock.json"],
                ["agent/feature.py"],
            )

    def test_exact_four_section_shape_rejects_missing_validation(self) -> None:
        block = patch_block("test_contract").replace("**验证**：test_contract\n\n", "")
        with self.assertRaises(evidence.EvidenceError):
            evidence._audit_section_shape("PATCH-TEST-CONTRACT", block)

    def test_active_test_function_must_resolve_to_one_node(self) -> None:
        active = {"PATCH-TEST-CONTRACT": patch_block("test_contract")}
        resolved = evidence._resolve_active_patch_nodes(
            active,
            ["tests/test_contract.py::TestContract::test_contract"],
            ["tests/test_contract.py"],
        )
        self.assertEqual(
            resolved,
            {"PATCH-TEST-CONTRACT": ["tests/test_contract.py::TestContract::test_contract"]},
        )
        with self.assertRaises(evidence.EvidenceError):
            evidence._resolve_active_patch_nodes(
                active,
                [
                    "tests/test_a.py::TestA::test_contract",
                    "tests/test_b.py::TestB::test_contract",
                ],
                ["tests/test_a.py", "tests/test_b.py"],
            )

    def test_explicit_evidence_node_binds_path_class_and_function(self) -> None:
        active = {
            "PATCH-TEST-CONTRACT": (
                "| **文件** | `tests/test_a.py`, `tests/test_b.py` |\n\n"
                + patch_block("tests/test_a.py::TestContract::test_contract")
            )
        }
        with self.assertRaisesRegex(evidence.EvidenceError, "explicit evidence node was not collected"):
            evidence._resolve_active_patch_nodes(
                active,
                ["tests/test_b.py::TestContract::test_contract"],
                ["tests/test_a.py", "tests/test_b.py"],
            )

    def test_every_patch_test_file_must_collect_at_least_one_node(self) -> None:
        completed = subprocess.CompletedProcess(
            ["pytest", "--collect-only"],
            0,
            "tests/test_a.py::test_a\n\n1 test collected\n",
            "",
        )
        with (
            patch.object(evidence.subprocess, "run", return_value=completed),
            self.assertRaisesRegex(evidence.EvidenceError, "zero_collected=.*tests/test_b.py"),
        ):
            evidence._collect_patch_nodes({"tests/test_a.py", "tests/test_b.py"})

    def test_patch_test_support_files_are_validated_but_not_counted_as_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            inner = Path(temp_raw)
            (inner / "tests/gateway").mkdir(parents=True)
            (inner / "tests/conftest.py").write_text("VALUE = 1\n", encoding="utf-8")
            (inner / "tests/gateway/feishu_helpers.py").write_text("VALUE = 2\n", encoding="utf-8")
            (inner / "tests/gateway/test_real.py").write_text(
                "from tests.gateway.feishu_helpers import VALUE\n\ndef test_real():\n    assert VALUE == 2\n",
                encoding="utf-8",
            )
            managed = subprocess.CompletedProcess(
                ["bash"],
                0,
                "tests/conftest.py\ntests/gateway/feishu_helpers.py\ntests/test_real.py\n",
                "",
            )
            with (
                patch.object(evidence, "INNER", inner),
                patch.object(evidence, "_run", return_value=managed),
            ):
                self.assertEqual(
                    evidence._patch_test_support_files(),
                    ["tests/conftest.py", "tests/gateway/feishu_helpers.py"],
                )
                self.assertEqual(
                    evidence._patch_test_support_consumers(
                        ["tests/conftest.py", "tests/gateway/feishu_helpers.py"],
                        {"tests/gateway/test_real.py"},
                    ),
                    {
                        "tests/conftest.py": ["tests/gateway/test_real.py"],
                        "tests/gateway/feishu_helpers.py": ["tests/gateway/test_real.py"],
                    },
                )

    def test_unused_patch_test_support_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            inner = Path(temp_raw)
            (inner / "tests").mkdir()
            (inner / "tests/helper.py").write_text("VALUE = 1\n", encoding="utf-8")
            (inner / "tests/test_real.py").write_text("def test_real():\n    assert True\n", encoding="utf-8")
            with (
                patch.object(evidence, "INNER", inner),
                self.assertRaisesRegex(evidence.EvidenceError, "no collected test consumers"),
            ):
                evidence._patch_test_support_consumers(
                    ["tests/helper.py"],
                    {"tests/test_real.py"},
                )

    def test_active_patches_cannot_borrow_the_same_evidence_node(self) -> None:
        active = {
            "PATCH-TEST-FIRST": patch_block("test_contract").replace("PATCH-TEST-CONTRACT", "PATCH-TEST-FIRST"),
            "PATCH-TEST-SECOND": patch_block("test_contract").replace("PATCH-TEST-CONTRACT", "PATCH-TEST-SECOND"),
        }
        with self.assertRaisesRegex(evidence.EvidenceError, "exclusive to one PATCH"):
            evidence._resolve_active_patch_nodes(
                active,
                ["tests/test_contract.py::TestContract::test_contract"],
                ["tests/test_contract.py"],
            )

    def test_evidence_node_must_come_from_patch_owned_test_file(self) -> None:
        active = {
            "PATCH-TEST-CONTRACT": (
                "| **文件** | `tests/test_owned.py`, `agent/feature.py` |\n\n" + patch_block("test_contract")
            )
        }
        with self.assertRaisesRegex(evidence.EvidenceError, "undeclared managed test files"):
            evidence._resolve_active_patch_nodes(
                active,
                ["tests/test_unowned.py::TestContract::test_contract"],
                ["tests/test_unowned.py"],
            )

    def test_owned_file_matching_is_token_exact_not_substring_based(self) -> None:
        block = "| **文件** | `tests/agent/feature.py` |\n"
        self.assertEqual(
            evidence._owned_managed_files(
                block,
                ["agent/feature.py", "tests/agent/feature.py"],
            ),
            ["tests/agent/feature.py"],
        )

    def test_archived_overlap_uses_declared_paths_not_current_managed_files(
        self,
    ) -> None:
        block = "| **文件** | 上游 `agent/retired.py`, `tests/test_retired.py` |\n"
        self.assertEqual(
            evidence._declared_upstream_overlap(
                block,
                {"agent/retired.py", "agent/unrelated.py"},
                include=True,
            ),
            ["agent/retired.py"],
        )

    def test_step8e_verifier_registry_must_match_external_patch_registry(self) -> None:
        script = 'PLUGIN_VERIFIERS=("${HERMES_HOME}/plugins/other/verify.sh")\n'
        with (
            patch.dict(
                evidence.EXTERNAL_EVIDENCE_AUDITS,
                {
                    "PATCH-TEST-EXTERNAL": (
                        "plugins/sandbox/verify.sh",
                        "audit_sandbox_verifier",
                        "full",
                    )
                },
                clear=True,
            ),
            self.assertRaisesRegex(evidence.EvidenceError, "Step 8e verifier registry drift"),
        ):
            evidence._validate_external_verifier_links(script)

    def test_active_engineering_patch_must_own_a_managed_path(self) -> None:
        active = {"PATCH-TEST-CONTRACT": ("| **文件** | `tests/test_missing.py` |\n\n" + patch_block("test_contract"))}
        with (
            patch.dict(evidence.RUNTIME_EVIDENCE, {}, clear=True),
            patch.dict(evidence.EXTERNAL_EVIDENCE_AUDITS, {}, clear=True),
            self.assertRaisesRegex(evidence.EvidenceError, "owns no PATCHED_FILES path"),
        ):
            evidence._audit_active_patch_ownership(active, ["tests/test_other.py"])

    def test_archived_step8_gate_must_map_to_a_registered_archive(self) -> None:
        script = """\
# -- 8b. Patch invariant gates
_ARCHIVED_TEST_OK=false
# Archived PATCH-UNKNOWN: synthetic
if true; then
    _ARCHIVED_TEST_OK=true
fi
# -- 8c. Refresh saved diff
if $_PATCH_APPLY_OK && $_ARCHIVED_TEST_OK; then
    :
fi
"""
        with tempfile.TemporaryDirectory() as temp_raw:
            script_path = Path(temp_raw) / "update.sh"
            script_path.write_text(script, encoding="utf-8")
            with (
                patch.object(evidence, "SCRIPT", script_path),
                self.assertRaisesRegex(evidence.EvidenceError, "unknown archived PATCH ID"),
            ):
                evidence.audit_gate_links({}, {"PATCH-ARCHIVE": patch_block("test_contract")})

    def test_step8_gate_success_assignment_must_be_unique(self) -> None:
        script = """\
# -- 8b. Patch invariant gates
_TEST_PATCH_OK=false
# PATCH-TEST-CONTRACT: synthetic
if true; then
    _TEST_PATCH_OK=true
    _TEST_PATCH_OK=true
fi
# -- 8c. Refresh saved diff
if $_PATCH_APPLY_OK && $_TEST_PATCH_OK; then
    :
fi
"""
        with tempfile.TemporaryDirectory() as temp_raw:
            script_path = Path(temp_raw) / "update.sh"
            script_path.write_text(script, encoding="utf-8")
            with (
                patch.object(evidence, "SCRIPT", script_path),
                self.assertRaisesRegex(evidence.EvidenceError, "exactly once"),
            ):
                evidence.audit_gate_links(
                    {"PATCH-TEST-CONTRACT": patch_block("test_contract")},
                    {},
                )

    def test_gateway_state_must_belong_to_live_non_pytest_gateway(self) -> None:
        head = "a" * 40
        payload = {
            "kind": "hermes-gateway",
            "pid": 42,
            "start_time": 1234,
            "argv": ["python", "-m", "hermes_cli.main", "gateway", "run"],
            "gateway_state": "running",
            "code_sha": head,
        }
        self.assertEqual(
            final_audit._validate_gateway_state_payload(
                payload,
                gateway_pid=42,
                gateway_start_time=1234,
                expected_sha=head,
            )["state_file_pid"],
            42,
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "pytest process"):
            final_audit._validate_gateway_state_payload(
                {**payload, "argv": ["python", "-m", "pytest"]},
                gateway_pid=42,
                gateway_start_time=1234,
                expected_sha=head,
            )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "not live Gateway PID"):
            final_audit._validate_gateway_state_payload(
                {**payload, "pid": 41},
                gateway_pid=42,
                gateway_start_time=1234,
                expected_sha=head,
            )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "start fingerprint"):
            final_audit._validate_gateway_state_payload(
                {**payload, "start_time": 9999},
                gateway_pid=42,
                gateway_start_time=1234,
                expected_sha=head,
            )

    def test_strict_pytest_probe_rejects_skipped_outcome(self) -> None:
        def fake_run(argv, **_kwargs):
            junit_arg = next(value for value in argv if value.startswith("--junitxml="))
            Path(junit_arg.split("=", 1)[1]).write_text(
                '<testsuite tests="1" skipped="1"><testcase name="test_contract">'
                '<skipped message="not covered" /></testcase></testsuite>',
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, "1 skipped", "")

        with (
            patch.object(evidence, "_run", side_effect=fake_run),
            self.assertRaisesRegex(evidence.EvidenceError, "non-passing outcomes"),
        ):
            evidence._run_strict_pytest_probe(
                "archive regression",
                "tests/test_contract.py::test_contract",
            )

    def test_strict_pytest_probe_rejects_unhandled_thread_exception(self) -> None:
        with tempfile.TemporaryDirectory(prefix="thread-warning-probe-") as temp_raw:
            test_file = Path(temp_raw) / "test_thread_warning.py"
            test_file.write_text(
                "import threading\n\n"
                "def test_background_failure():\n"
                "    def fail():\n"
                "        raise RuntimeError('background boom')\n"
                "    thread = threading.Thread(target=fail)\n"
                "    thread.start()\n"
                "    thread.join()\n"
                "    assert True\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.EvidenceError, "failed"):
                evidence._run_strict_pytest_probe(
                    "thread warning regression",
                    f"{test_file}::test_background_failure",
                )

    def test_strict_pytest_probe_rejects_unraisable_exception(self) -> None:
        with tempfile.TemporaryDirectory(prefix="unraisable-warning-probe-") as temp_raw:
            test_file = Path(temp_raw) / "test_unraisable_warning.py"
            test_file.write_text(
                "import gc\n\n"
                "class Boom:\n"
                "    def __del__(self):\n"
                "        raise RuntimeError('unraisable boom')\n\n"
                "def test_unraisable_failure():\n"
                "    item = Boom()\n"
                "    del item\n"
                "    gc.collect()\n"
                "    assert True\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.EvidenceError, "failed"):
                evidence._run_strict_pytest_probe(
                    "unraisable warning regression",
                    f"{test_file}::test_unraisable_failure",
                )

    def test_strict_pytest_probe_rejects_unawaited_coroutine(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coroutine-warning-probe-") as temp_raw:
            test_file = Path(temp_raw) / "test_coroutine_warning.py"
            test_file.write_text(
                "import gc\n\n"
                "async def work():\n"
                "    return 1\n\n"
                "def test_unawaited_coroutine():\n"
                "    coro = work()\n"
                "    del coro\n"
                "    gc.collect()\n"
                "    assert True\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.EvidenceError, "failed"):
                evidence._run_strict_pytest_probe(
                    "unawaited coroutine regression",
                    f"{test_file}::test_unawaited_coroutine",
                )

    def test_strict_pytest_probe_rejects_test_return_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="return-warning-probe-") as temp_raw:
            test_file = Path(temp_raw) / "test_return_warning.py"
            test_file.write_text(
                "def test_returns_false():\n    return False\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(evidence.EvidenceError, "failed"):
                evidence._run_strict_pytest_probe(
                    "return warning regression",
                    f"{test_file}::test_returns_false",
                )

    def test_patch_collection_rejects_partially_uncollected_test_class(self) -> None:
        original_inner = evidence.INNER
        with tempfile.TemporaryDirectory(prefix="collection-warning-probe-") as temp_raw:
            root = Path(temp_raw)
            tests = root / "tests"
            tests.mkdir()
            os.symlink(original_inner / "venv", root / "venv", target_is_directory=True)
            (tests / "test_collection_warning.py").write_text(
                "def test_collected():\n"
                "    assert True\n\n"
                "class TestLost:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def test_never_collected(self):\n"
                "        assert False\n",
                encoding="utf-8",
            )
            with (
                patch.object(evidence, "INNER", root),
                self.assertRaisesRegex(evidence.EvidenceError, "collection failed"),
            ):
                evidence._collect_patch_nodes({"tests/test_collection_warning.py"})

    def test_evidence_registry_requires_exact_ids_and_lifecycles(self) -> None:
        patches = (
            patch_block("test_contract")
            + "\n## Archive\n"
            + patch_block("test_archive").replace(
                "PATCH-TEST-CONTRACT",
                "PATCH-TEST-ARCHIVE",
            )
        )
        records = [
            {"id": "PATCH-TEST-CONTRACT", "lifecycle": "active"},
            {"id": "PATCH-TEST-ARCHIVE", "lifecycle": "archived"},
        ]
        self.assertEqual(
            final_audit._validate_evidence_registry(records, patches),
            {"active": 1, "archived": 1},
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "registry differs"):
            final_audit._validate_evidence_registry(
                [
                    {"id": "PATCH-TEST-CONTRACT", "lifecycle": "active"},
                    {"id": "PATCH-UNKNOWN", "lifecycle": "archived"},
                ],
                patches,
            )

    def test_sandbox_result_requires_clean_machine_receipt(self) -> None:
        clean = {
            "verifier": "plugins/sandbox/verify.sh",
            "passed": 60,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        }
        self.assertEqual(
            final_audit._validate_sandbox_result(clean, label="test"),
            clean,
        )
        with self.assertRaisesRegex(final_audit.FinalAuditError, "non-passing"):
            final_audit._validate_sandbox_result(
                {**clean, "passed": 59, "skipped": 1},
                label="test",
            )

    def test_outer_workspace_fingerprint_must_remain_stable(self) -> None:
        snapshot = {
            "digest": "abc",
            "status_bytes": 0,
            "tracked_diff_bytes": 0,
            "untracked_files": 0,
        }
        final_audit._validate_outer_workspace_stability(snapshot, dict(snapshot))
        with self.assertRaisesRegex(final_audit.FinalAuditError, "changed tracked"):
            final_audit._validate_outer_workspace_stability(
                snapshot,
                {**snapshot, "digest": "def"},
            )

    def test_post_test_bundle_reverification_is_fail_closed(self) -> None:
        with patch.object(
            final_audit.patch_evidence,
            "audit_bundle",
            side_effect=evidence.EvidenceError("changed after tests"),
        ):
            with self.assertRaisesRegex(
                final_audit.FinalAuditError,
                "post-test replay bundle verification failed",
            ):
                final_audit._reverify_bundle_after_tests()

    def test_bundle_audit_materializes_managed_deletions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            inner = root / "inner"
            inner.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=inner, check=True)
            subprocess.run(
                ["git", "config", "user.email", "audit@example.invalid"],
                cwd=inner,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Audit Test"],
                cwd=inner,
                check=True,
            )
            # This synthetic repository tests bundle mechanics, not the user's
            # global commit policy. Isolate it from core.hooksPath without
            # changing or bypassing hooks in the real workspace.
            hooks = root / "empty-hooks"
            hooks.mkdir()
            subprocess.run(
                ["git", "config", "core.hooksPath", str(hooks)],
                cwd=inner,
                check=True,
            )
            kept = inner / "kept.py"
            deleted = inner / "deleted.py"
            kept.write_text("VALUE = 1\n", encoding="utf-8")
            deleted.write_text("REMOVE = True\n", encoding="utf-8")
            subprocess.run(["git", "add", "kept.py", "deleted.py"], cwd=inner, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=inner, check=True)
            kept.write_text("VALUE = 2\n", encoding="utf-8")
            deleted.unlink()

            script = root / "update.sh"
            script.write_text(
                "#!/bin/sh\nprintf '%s\\n' kept.py deleted.py\n",
                encoding="utf-8",
            )
            bundle = root / "local-patches.diff"
            diff = subprocess.run(
                ["git", "diff", "--full-index", "HEAD", "--", "kept.py", "deleted.py"],
                cwd=inner,
                check=True,
                capture_output=True,
                text=True,
            )
            bundle.write_text(diff.stdout, encoding="utf-8")

            with (
                patch.object(evidence, "INNER", inner),
                patch.object(evidence, "SCRIPT", script),
                patch.object(evidence, "BUNDLE", bundle),
            ):
                evidence.audit_bundle()

    def test_patch_trace_requires_owned_production_execution(self) -> None:
        block = "| **文件** | `agent/feature.py`, `agent/helper.py`, `tests/test_feature.py` |\n\n" + patch_block(
            "test_feature"
        )
        active = {"PATCH-TEST-CONTRACT": block}
        resolved = {"PATCH-TEST-CONTRACT": ["tests/test_feature.py::TestFeature::test_feature"]}
        managed = ["agent/feature.py", "agent/helper.py", "tests/test_feature.py"]
        with self.assertRaisesRegex(
            evidence.EvidenceError,
            "without executing every owned Python production file",
        ):
            evidence._validate_patch_trace_hits(
                active,
                resolved,
                {"tests/test_feature.py::TestFeature::test_feature": {"agent/feature.py"}},
                managed,
            )
        self.assertEqual(
            evidence._validate_patch_trace_hits(
                active,
                resolved,
                {
                    "tests/test_feature.py::TestFeature::test_feature": {
                        "agent/feature.py",
                        "agent/helper.py",
                    }
                },
                managed,
            ),
            {"PATCH-TEST-CONTRACT": ["agent/feature.py", "agent/helper.py"]},
        )

    def test_module_import_coverage_requires_an_explicit_patch_file_exception(
        self,
    ) -> None:
        node = "tests/test_feature.py::test_feature"
        block = "| **文件** | `agent/feature.py`, `tests/test_feature.py` |\n\n" + patch_block("test_feature")
        active = {"PATCH-TEST-CONTRACT": block}
        resolved = {"PATCH-TEST-CONTRACT": [node]}
        managed = ["agent/feature.py", "tests/test_feature.py"]
        with (
            patch.dict(evidence.MODULE_IMPORT_EVIDENCE, {}, clear=True),
            self.assertRaisesRegex(
                evidence.EvidenceError,
                "without executing every owned Python production file",
            ),
        ):
            evidence._validate_patch_trace_hits(
                active,
                resolved,
                {node: set()},
                managed,
                {node: {"agent/feature.py"}},
            )
        with patch.dict(
            evidence.MODULE_IMPORT_EVIDENCE,
            {"PATCH-TEST-CONTRACT": ("agent/feature.py",)},
            clear=True,
        ):
            self.assertEqual(
                evidence._validate_patch_trace_hits(
                    active,
                    resolved,
                    {node: set()},
                    managed,
                    {node: {"agent/feature.py"}},
                ),
                {"PATCH-TEST-CONTRACT": ["agent/feature.py"]},
            )

    def test_fixture_setup_cannot_impersonate_test_call_coverage(self) -> None:
        interpreter = evidence.INNER / "venv/bin/python"
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            (root / "agent").mkdir()
            (root / "tests").mkdir()
            (root / "venv/bin").mkdir(parents=True)
            (root / "agent/__init__.py").write_text("", encoding="utf-8")
            (root / "agent/feature.py").write_text(
                "def touch():\n    return True\n",
                encoding="utf-8",
            )
            (root / "tests/test_feature.py").write_text(
                "import pytest\n"
                "from agent.feature import touch\n\n"
                "@pytest.fixture(autouse=True)\n"
                "def exercise_only_during_setup():\n"
                "    touch()\n\n"
                "def test_feature():\n"
                "    assert True\n",
                encoding="utf-8",
            )
            python_wrapper = root / "venv/bin/python"
            python_wrapper.write_text(
                f'#!/bin/sh\nexec "{interpreter}" "$@"\n',
                encoding="utf-8",
            )
            python_wrapper.chmod(0o755)
            active = {
                "PATCH-TEST-CONTRACT": (
                    "| **文件** | `agent/feature.py`, `tests/test_feature.py` |\n\n" + patch_block("test_feature")
                )
            }
            resolved = {"PATCH-TEST-CONTRACT": ["tests/test_feature.py::test_feature"]}
            managed = subprocess.CompletedProcess(
                ["bash"],
                0,
                "agent/feature.py\ntests/test_feature.py\n",
                "",
            )
            with (
                patch.object(evidence, "INNER", root),
                patch.object(evidence, "_run", return_value=managed),
                self.assertRaisesRegex(
                    evidence.EvidenceError,
                    "without executing every owned Python production file",
                ),
            ):
                evidence._run_active_patch_nodes(active, resolved)

    def test_import_only_cannot_impersonate_production_execution(self) -> None:
        interpreter = evidence.INNER / "venv/bin/python"
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            (root / "agent").mkdir()
            (root / "tests").mkdir()
            (root / "venv/bin").mkdir(parents=True)
            (root / "agent/__init__.py").write_text("", encoding="utf-8")
            (root / "agent/feature.py").write_text(
                "VALUE = 1\n\ndef touch():\n    return True\n",
                encoding="utf-8",
            )
            (root / "tests/test_feature.py").write_text(
                "def test_feature():\n    import agent.feature\n    assert agent.feature.VALUE == 1\n",
                encoding="utf-8",
            )
            python_wrapper = root / "venv/bin/python"
            python_wrapper.write_text(
                f'#!/bin/sh\nexec "{interpreter}" "$@"\n',
                encoding="utf-8",
            )
            python_wrapper.chmod(0o755)
            active = {
                "PATCH-TEST-CONTRACT": (
                    "| **文件** | `agent/feature.py`, `tests/test_feature.py` |\n\n" + patch_block("test_feature")
                )
            }
            resolved = {"PATCH-TEST-CONTRACT": ["tests/test_feature.py::test_feature"]}
            managed = subprocess.CompletedProcess(
                ["bash"],
                0,
                "agent/feature.py\ntests/test_feature.py\n",
                "",
            )
            with (
                patch.object(evidence, "INNER", root),
                patch.object(evidence, "_run", return_value=managed),
                self.assertRaisesRegex(
                    evidence.EvidenceError,
                    "without executing every owned Python production file",
                ),
            ):
                evidence._run_active_patch_nodes(active, resolved)

    def test_active_patch_nodes_run_in_separate_pytest_processes(self) -> None:
        calls: list[list[str]] = []

        def fake_run(argv, *, env=None, **_kwargs):
            calls.append(list(argv))
            node = argv[-1]
            function = node.rsplit("::", 1)[-1]
            junit_arg = next(value for value in argv if value.startswith("--junitxml="))
            Path(junit_arg.split("=", 1)[1]).write_text(
                f'<testsuite tests="1"><testcase name="{function}" /></testsuite>',
                encoding="utf-8",
            )
            Path(env["HERMES_PATCH_TRACE_OUT"]).write_text(
                json.dumps({node: []}),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, "1 passed", "")

        active = {
            "PATCH-TEST-FIRST": "| **文件** | `tests/test_first.py` |\n",
            "PATCH-TEST-SECOND": "| **文件** | `tests/test_second.py` |\n",
        }
        resolved = {
            "PATCH-TEST-FIRST": ["tests/test_first.py::test_first"],
            "PATCH-TEST-SECOND": ["tests/test_second.py::test_second"],
        }
        managed = subprocess.CompletedProcess(
            ["bash"],
            0,
            "tests/test_first.py\ntests/test_second.py\n",
            "",
        )
        with (
            patch.object(evidence.subprocess, "run", side_effect=fake_run),
            patch.object(evidence, "_run", return_value=managed),
        ):
            evidence._run_active_patch_nodes(active, resolved)

        self.assertEqual(len(calls), 2)
        self.assertEqual({call[-1] for call in calls}, {resolved[key][0] for key in resolved})
        for call in calls:
            self.assertIn(
                ["-W", "error::pytest.PytestUnhandledThreadExceptionWarning"],
                [call[index : index + 2] for index in range(len(call) - 1)],
            )
            self.assertIn(
                ["-W", "error::pytest.PytestUnraisableExceptionWarning"],
                [call[index : index + 2] for index in range(len(call) - 1)],
            )
            self.assertIn(
                ["-W", "error::RuntimeWarning"],
                [call[index : index + 2] for index in range(len(call) - 1)],
            )
            self.assertIn(
                ["-W", "error::pytest.PytestReturnNotNoneWarning"],
                [call[index : index + 2] for index in range(len(call) - 1)],
            )
            self.assertIn(
                ["-W", "error::pytest.PytestCollectionWarning"],
                [call[index : index + 2] for index in range(len(call) - 1)],
            )

    def test_dotenv_inventory_reads_names_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            path = Path(temp_raw) / ".env"
            path.write_text(
                "# comment\nexport FIRST_SECRET=do-not-print\nSECOND_SECRET = another-value\n",
                encoding="utf-8",
            )
            self.assertEqual(
                evidence._env_key_names(path),
                {"FIRST_SECRET", "SECOND_SECRET"},
            )

    def test_final_audit_rejects_literal_mcp_credentials(self) -> None:
        safe = """mcp_servers:
  service:
    headers:
      Authorization: "Bearer ${env:SERVICE_TOKEN}"
      X-API-Key: "${SERVICE_API_KEY}"
"""
        self.assertEqual(
            final_audit._validate_tracked_config_secret_refs(safe),
            {"sensitive_mcp_headers": 2, "literal_credentials": 0},
        )

        unsafe = """mcp_servers:
  service:
    headers:
      Authorization: "Bearer copied-secret"
"""
        with self.assertRaisesRegex(final_audit.FinalAuditError, "literal MCP credentials"):
            final_audit._validate_tracked_config_secret_refs(unsafe)

    def test_active_node_skip_is_not_accepted_as_real_regression(self) -> None:
        def fake_run(argv, **_kwargs):
            junit_arg = next(value for value in argv if value.startswith("--junitxml="))
            Path(junit_arg.split("=", 1)[1]).write_text(
                '<testsuite tests="1" skipped="1"><testcase name="test_contract">'
                '<skipped message="not covered" /></testcase></testsuite>',
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(argv, 0, "1 skipped", "")

        with (
            patch.object(evidence.subprocess, "run", side_effect=fake_run),
            self.assertRaises(evidence.EvidenceError),
        ):
            evidence._run_active_patch_nodes(
                {"PATCH-TEST-CONTRACT": patch_block("test_contract")},
                {"PATCH-TEST-CONTRACT": ["tests/test_contract.py::TestContract::test_contract"]},
            )

    def test_vertex_retirement_audit_does_not_require_a_specific_replacement_provider(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_raw:
            root = Path(temp_raw)
            inner = root / "hermes-agent"
            for rel in (
                "agent/vertex_adapter.py",
                "hermes_cli/auth.py",
                "hermes_cli/runtime_provider.py",
                "agent/auxiliary_client.py",
                "plugins/model-providers/vertex/__init__.py",
            ):
                path = inner / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# standard provider surface\n", encoding="utf-8")
            (root / "config.yaml").write_text(
                "model:\n  provider: bedrock\n  model: example-model\n",
                encoding="utf-8",
            )
            (root / ".env").write_text("SAFE_KEY=value\n", encoding="utf-8")
            (root / ".env.example").write_text("SAFE_KEY=\n", encoding="utf-8")
            bundle = root / "local-patches.diff"
            bundle.write_text("", encoding="utf-8")
            completed = subprocess.CompletedProcess(["python"], 0, "", "")
            with (
                patch.object(evidence, "ROOT", root),
                patch.object(evidence, "INNER", inner),
                patch.object(evidence, "BUNDLE", bundle),
                patch.object(evidence, "_run", return_value=completed),
            ):
                evidence.audit_archived_vertex_fallback()


if __name__ == "__main__":
    unittest.main()
