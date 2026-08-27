from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_patch_evidence as evidence
from final_upgrade_audit import _current_week_readme_rows, _markdown_table_summary


def patch_block(validation: str) -> str:
    return (
        "### [PATCH-TEST-CONTRACT] synthetic\n\n"
        "**问题**：problem\n\n"
        "**修复**：fix\n\n"
        f"**验证**：{validation}\n\n"
        "**上游吸收判断**：absorb\n"
    )


class PatchEvidenceAuditorTest(unittest.TestCase):
    def test_quick_mode_defers_bundle_parity_until_full_audit(self) -> None:
        audits = (
            "audit_gate_links",
            "audit_runtime_artifacts",
            "audit_socks_dependency",
            "audit_openclaw_token_migration",
            "audit_skills_mirror",
            "audit_fts5_build",
            "audit_archived_regressions",
        )
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["test_patch_evidence.py", "--quick"]))
            stack.enter_context(patch.object(evidence, "audit_registry", return_value=({}, {})))
            stack.enter_context(patch.object(evidence, "audit_npm_dependency_hygiene", return_value={}))
            bundle = stack.enter_context(patch.object(evidence, "audit_bundle"))
            stack.enter_context(patch.object(evidence, "_evidence_records", return_value=[]))
            for name in audits:
                stack.enter_context(patch.object(evidence, name))
            self.assertEqual(evidence.main(), 0)
        bundle.assert_not_called()

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

    def test_exact_four_section_shape_rejects_missing_validation(self) -> None:
        block = patch_block("test_contract").replace("**验证**：test_contract\n\n", "")
        with self.assertRaises(evidence.EvidenceError):
            evidence._audit_section_shape("PATCH-TEST-CONTRACT", block)

    def test_active_test_function_must_resolve_to_one_node(self) -> None:
        active = {"PATCH-TEST-CONTRACT": patch_block("test_contract")}
        resolved = evidence._resolve_active_patch_nodes(
            active,
            ["tests/test_contract.py::TestContract::test_contract"],
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
            )

    def test_evidence_node_must_come_from_patch_owned_test_file(self) -> None:
        active = {
            "PATCH-TEST-CONTRACT": (
                "| **文件** | `tests/test_owned.py`, `agent/feature.py` |\n\n" + patch_block("test_contract")
            )
        }
        with self.assertRaisesRegex(evidence.EvidenceError, "undeclared test files"):
            evidence._resolve_active_patch_nodes(
                active,
                ["tests/test_unowned.py::TestContract::test_contract"],
            )

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
