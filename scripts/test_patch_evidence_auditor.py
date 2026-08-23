from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_patch_evidence as evidence
from final_upgrade_audit import _markdown_table_summary


def patch_block(validation: str) -> str:
    return (
        "### [PATCH-TEST-CONTRACT] synthetic\n\n"
        "**问题**：problem\n\n"
        "**修复**：fix\n\n"
        f"**验证**：{validation}\n\n"
        "**上游吸收判断**：absorb\n"
    )


class PatchEvidenceAuditorTest(unittest.TestCase):
    def test_readme_summary_length_ignores_prettier_table_padding(self) -> None:
        row = "| v1.2.3 | 2026-08-23 | semantic summary" + (" " * 500) + " |"
        self.assertEqual(_markdown_table_summary(row), "semantic summary")

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
                {"PATCH-TEST-CONTRACT": ["tests/test_contract.py::TestContract::test_contract"]}
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
