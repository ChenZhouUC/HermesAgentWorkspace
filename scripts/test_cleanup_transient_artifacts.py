from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cleanup_transient_artifacts as cleanup


def write_policy(
    root: Path,
    *,
    required_scripts: dict[str, str] | None = None,
    ignored_keep: dict[str, str] | None = None,
    ignored_remove: dict[str, str] | None = None,
) -> Path:
    policy = {
        "version": 1,
        "script_audit_globs": ["scripts/**/*", "test-*.js"],
        "script_extensions": [".py", ".js"],
        "required_scripts": required_scripts or {},
        "required_files": {},
        "removable_script_globs": {"test-pager*.js": "temporary pager test"},
        "ignored_keep_globs": ignored_keep or {},
        "ignored_remove_globs": ignored_remove or {},
        "protected_prefixes": [".git"],
        "removable_directory_names": {".pytest-cache": "pytest cache"},
        "removable_file_names": {".DS_Store": "Finder metadata"},
        "python_cache_roots": ["scripts"],
        "active_process_markers": ["pytest", "test-pager"],
    }
    path = root / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return path


def args_for(root: Path, policy: Path, trash: Path, *, apply: bool, fail_on_review: bool = False) -> Namespace:
    return Namespace(
        apply=apply,
        dry_run=not apply,
        json=False,
        min_age_minutes=10.0,
        root=root,
        policy=policy,
        trash_root=trash,
        fail_if_found=False,
        fail_on_review=fail_on_review,
    )


class CleanupTransientArtifactsTest(unittest.TestCase):
    def test_active_process_probe_rejects_nonzero_ps(self) -> None:
        failed = subprocess.CompletedProcess(args=["ps"], returncode=1, stdout="", stderr="permission denied")
        with patch.object(cleanup.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(RuntimeError, "permission denied"):
                cleanup.active_test_processes({"active_process_markers": ["pytest"]})

    def test_active_process_probe_ignores_agents_in_other_workspaces(self) -> None:
        ps = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout="101 codex exec review\n102 qwen review\n",
            stderr="",
        )
        root = Path("/Users/test/.hermes")
        with (
            patch.object(cleanup.subprocess, "run", return_value=ps),
            patch.object(
                cleanup,
                "_process_cwd",
                side_effect=lambda pid: Path(f"/Users/test/other-{pid}"),
            ),
        ):
            active = cleanup.active_test_processes({"active_process_markers": ["codex", "qwen"]}, root)

        self.assertEqual(active, [])

    def test_active_process_probe_does_not_treat_root_prefix_sibling_as_workspace(self) -> None:
        ps = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout="101 pytest -q /Users/test/.hermes-copy/tests\n",
            stderr="",
        )
        root = Path("/Users/test/.hermes")
        with (
            patch.object(cleanup.subprocess, "run", return_value=ps),
            patch.object(cleanup, "_process_cwd", return_value=Path("/Users/test/.hermes-copy")),
        ):
            active = cleanup.active_test_processes({"active_process_markers": ["pytest"]}, root)

        self.assertEqual(active, [])

    def test_active_process_probe_resolves_relative_argv_from_parent_cwd(self) -> None:
        ps = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout="101 pytest -q .hermes/tests\n",
            stderr="",
        )
        root = Path("/Users/test/.hermes")
        with (
            patch.object(cleanup.subprocess, "run", return_value=ps),
            patch.object(cleanup, "_process_cwd", return_value=Path("/Users/test")),
        ):
            active = cleanup.active_test_processes({"active_process_markers": ["pytest"]}, root)

        self.assertEqual(active, ["101 pytest -q .hermes/tests"])

    def test_active_process_probe_keeps_workspace_scoped_agent(self) -> None:
        ps = subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout="101 claude review\n102 pytest -q /Users/test/.hermes/tests\n",
            stderr="",
        )
        root = Path("/Users/test/.hermes")
        with (
            patch.object(cleanup.subprocess, "run", return_value=ps),
            patch.object(cleanup, "_process_cwd", return_value=root / "hermes-agent"),
        ):
            active = cleanup.active_test_processes({"active_process_markers": ["pytest", "claude"]}, root)

        self.assertEqual(len(active), 2)

    def test_active_process_cwd_probe_failure_is_not_treated_as_external(self) -> None:
        ps = subprocess.CompletedProcess(args=["ps"], returncode=0, stdout="101 pytest -q\n", stderr="")
        with (
            patch.object(cleanup.subprocess, "run", return_value=ps),
            patch.object(
                cleanup,
                "_process_cwd",
                side_effect=RuntimeError("cwd unavailable"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "cwd unavailable"):
                cleanup.active_test_processes({"active_process_markers": ["pytest"]}, Path("/tmp/hermes"))

    def test_apply_fails_closed_when_process_probe_errors(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_raw,
            tempfile.TemporaryDirectory() as trash_raw,
        ):
            root = Path(root_raw)
            trash = Path(trash_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            policy_path = write_policy(root)

            with patch.object(
                cleanup,
                "active_test_processes",
                side_effect=RuntimeError("active process probe failed"),
            ):
                result, exit_code = cleanup.run(args_for(root, policy_path, trash, apply=True))

            self.assertEqual(exit_code, 1)
            self.assertIn("active process probe failed", result["policy_errors"])

    def test_repository_policy_tracks_final_audit_and_evidence_self_tests(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = cleanup.load_policy(root / "scripts/cleanup_policy.json")
        required = policy["required_scripts"]
        self.assertIn("scripts/final_upgrade_audit.py", required)
        self.assertIn("scripts/test_patch_evidence.py", required)
        self.assertIn("scripts/test_patch_evidence_auditor.py", required)
        self.assertIn("plugins/model-providers/claude-sc/verify.sh", required)

    def test_repository_policy_preserves_retired_wisdom_state_and_audits_nested_verifiers(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        policy = cleanup.load_policy(repository / "scripts/cleanup_policy.json")
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            verifier = root / "plugins/model-providers/example/verify.sh"
            verifier.parent.mkdir(parents=True)
            verifier.write_text("#!/bin/sh\nexit 0\n")
            scoped_policy = {**policy, "required_scripts": {}, "required_files": {}}
            audit, errors = cleanup.audit_scripts(root, scoped_policy)
            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {"plugins/model-providers/example/verify.sh": "review"},
            )
            (root / ".gitignore").write_text((repository / ".gitignore").read_text())
            (root / "fleet_restart_pending").write_text("expected_sha=test\n")
            (root / "shared-state.db").write_bytes(b"coordination state")
            (root / "shared-state.db-wal").write_bytes(b"journal")
            wisdom = root / "wisdom"
            wisdom.mkdir()
            for name in ("wisdom.db", "wisdom.db-wal", "wisdom.db-shm"):
                (wisdom / name).write_bytes(b"private runtime state")
                ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", f"wisdom/{name}"])
                self.assertEqual(ignored.returncode, 0, f"wisdom/{name} must remain outside Git")
            audit, errors = cleanup.audit_ignored(root, scoped_policy)
            self.assertEqual(errors, [])
            self.assertTrue(all(item.classification == "keep" for item in audit))
            self.assertIn("wisdom", {item.path.rstrip("/") for item in audit})

    def test_script_audit_classifies_keep_remove_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            scripts = root / "scripts"
            scripts.mkdir()
            keep = scripts / "keep.py"
            keep.write_text("print('keep')")
            review = scripts / "new.py"
            review.write_text("print('review')")
            removable = root / "test-pager-check.js"
            removable.write_text("remove")
            subprocess.run(["git", "-C", str(root), "add", "scripts/keep.py"], check=True)
            policy_path = write_policy(root, required_scripts={"scripts/keep.py": "required"})

            audit, errors = cleanup.audit_scripts(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {
                    "scripts/keep.py": "keep",
                    "scripts/new.py": "review",
                    "test-pager-check.js": "remove",
                },
            )

    def test_apply_moves_only_blacklist_candidates(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_raw,
            tempfile.TemporaryDirectory() as trash_raw,
        ):
            root = Path(root_raw)
            trash = Path(trash_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            policy_path = write_policy(root)
            cache = root / ".pytest-cache"
            cache.mkdir()
            (cache / "guard").write_text("x")
            review = root / "scripts" / "review.py"
            review.parent.mkdir()
            review.write_text("keep for review")
            removable = root / "test-pager-check.js"
            removable.write_text("remove")
            old = time.time() - 1200
            os.utime(removable, (old, old))

            result, exit_code = cleanup.run(args_for(root, policy_path, trash, apply=True), processes=[])

            self.assertEqual(exit_code, 0)
            self.assertFalse(cache.exists())
            self.assertFalse(removable.exists())
            self.assertTrue(review.exists())
            trash_dir = Path(str(result["trash_dir"]))
            self.assertTrue((trash_dir / ".pytest-cache/guard").is_file())
            self.assertTrue((trash_dir / "test-pager-check.js").is_file())

    def test_fail_on_review_blocks_apply_before_moving(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_raw,
            tempfile.TemporaryDirectory() as trash_raw,
        ):
            root = Path(root_raw)
            trash = Path(trash_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            policy_path = write_policy(root)
            review = root / "scripts" / "review.py"
            review.parent.mkdir()
            review.write_text("review")
            cache = root / ".pytest-cache"
            cache.mkdir()

            result, exit_code = cleanup.run(
                args_for(root, policy_path, trash, apply=True, fail_on_review=True),
                processes=[],
            )

            self.assertEqual(exit_code, 4)
            self.assertTrue(cache.exists())
            self.assertEqual(result["summary"]["script_review"], 1)

    def test_missing_or_untracked_required_script_is_policy_error(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            script = root / "scripts" / "required.py"
            script.parent.mkdir()
            script.write_text("required")
            policy_path = write_policy(root, required_scripts={"scripts/required.py": "required"})
            policy = cleanup.load_policy(policy_path)

            _audit, errors = cleanup.audit_scripts(root, policy)
            self.assertIn("required script is not Git-tracked: scripts/required.py", errors)

            script.unlink()
            _audit, errors = cleanup.audit_scripts(root, policy)
            self.assertTrue(any(error.startswith("missing required script") for error in errors))

    def test_ignored_audit_classifies_keep_remove_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("runtime/\n.pytest_cache/\nmystery/\n")
            for dirname in ("runtime", ".pytest_cache", "mystery"):
                (root / dirname).mkdir()
                (root / dirname / "value").write_text("x")
            policy_path = write_policy(
                root,
                ignored_keep={"runtime/": "required runtime"},
                ignored_remove={".pytest_cache/": "cache"},
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {".pytest_cache/": "remove", "mystery/": "review", "runtime/": "keep"},
            )

    def test_transaction_state_and_lock_are_explicitly_keep_classified(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text(".hermes-update-transaction\n.hermes-update-transaction.lock/\n")
            state_file = root / ".hermes-update-transaction"
            state_file.write_text("version=1\nphase=upstream_applied\n")
            lock_dir = root / ".hermes-update-transaction.lock"
            lock_dir.mkdir()
            (lock_dir / "owner").write_text("version=1\npid=123\nstart=Thu Sep  3 12:00:00 2026\ntoken=test-owner\n")
            policy_path = write_policy(
                root,
                ignored_keep={
                    ".hermes-update-transaction": "transaction state",
                    ".hermes-update-transaction.lock/": "transaction lock",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {
                    ".hermes-update-transaction": "keep",
                    ".hermes-update-transaction.lock/": "keep",
                },
            )

    def test_clean_shutdown_receipt_is_explicitly_keep_classified(self) -> None:
        """The restart gate must preserve Gateway's graceful-exit receipt."""
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text(".clean_shutdown\n")
            (root / ".clean_shutdown").touch()
            policy_path = write_policy(
                root,
                ignored_keep={
                    ".clean_shutdown": "graceful-shutdown receipt",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0].path, ".clean_shutdown")
            self.assertEqual(audit[0].classification, "keep")

    def test_spawn_ledger_is_explicitly_keep_classified(self) -> None:
        """The process-identity ledger is runtime state, not cleanup debris."""
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("spawn-ledger.json\nspawn-ledger.json.corrupt\n")
            (root / "spawn-ledger.json").write_text("[]\n")
            (root / "spawn-ledger.json.corrupt").write_text("not-json\n")
            policy_path = write_policy(
                root,
                ignored_keep={
                    "spawn-ledger.json*": "machine process identity ledger",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {entry.path: entry.classification for entry in audit},
                {
                    "spawn-ledger.json": "keep",
                    "spawn-ledger.json.corrupt": "keep",
                },
            )

    def test_persistent_skill_prompt_snapshot_is_explicitly_keep_classified(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text(".skills_prompt_snapshot.json\n")
            (root / ".skills_prompt_snapshot.json").write_text('{"version": 2, "manifest": {}, "skills": []}')
            policy_path = write_policy(
                root,
                ignored_keep={
                    ".skills_prompt_snapshot.json": "persistent skill prompt snapshot",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0].path, ".skills_prompt_snapshot.json")
            self.assertEqual(audit[0].classification, "keep")

    def test_config_corruption_recovery_snapshot_is_explicitly_keep_classified(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            backup_name = "config.yaml.corrupt.20260822-174328.bak"
            (root / ".gitignore").write_text("config.yaml.corrupt.*.bak\n")
            (root / backup_name).write_text("broken: [\n")
            policy_path = write_policy(
                root,
                ignored_keep={
                    "config.yaml.corrupt.*.bak": "config recovery snapshot",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0].path, backup_name)
            self.assertEqual(audit[0].classification, "keep")

    def test_runtime_session_pointers_are_explicitly_keep_classified(self) -> None:
        """Update-check throttle and per-TTY session pointers must never be swept.

        Removing .update_check lets the next banner fire a network update check
        that preflight forbids; terminal-sessions/ is owned by whichever live
        terminals exist, so sweeping it is the concurrent-session mistake the
        restart gate is meant to catch.
        """
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text(".update_check\nterminal-sessions/\n")
            (root / ".update_check").write_text('{"ts": 1787210948.5, "behind": 274, "ver": "0.20.4"}')
            (root / "terminal-sessions").mkdir()
            (root / "terminal-sessions" / "tty-dev-ttys003").write_text(
                '{"session_id": "20260820_152908_3b11c3", "cwd": "/x", "ts": 1787210948.7}'
            )
            policy_path = write_policy(
                root,
                ignored_keep={
                    ".update_check": "update-check throttle cache",
                    "terminal-sessions/": "per-TTY session pointers",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual({entry.classification for entry in audit}, {"keep"})
            self.assertEqual(
                {entry.path for entry in audit},
                {".update_check", "terminal-sessions/"},
            )

    def test_repository_policy_keeps_wiki_state_without_preserving_finder_metadata(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        policy = cleanup.load_policy(repository_root / "scripts/cleanup_policy.json")
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text(
                "\n".join(
                    (
                        ".DS_Store",
                        "wiki/.obsidian/workspace.json",
                        "wiki/.obsidian/graph.json",
                        "wiki/.obsidian/plugins/obsidian-git/obsidian_askpass.sh",
                    )
                )
                + "\n"
            )
            raw = root / "wiki" / "raw"
            raw.mkdir(parents=True)
            tracked_wiki_file = root / "wiki" / "tracked.md"
            tracked_wiki_file.write_text("tracked\n")
            subprocess.run(["git", "-C", str(root), "add", "wiki/tracked.md"], check=True)
            (raw / ".DS_Store").write_bytes(b"finder")
            obsidian = root / "wiki" / ".obsidian"
            obsidian.mkdir(parents=True)
            tracked_obsidian_file = obsidian / "app.json"
            tracked_obsidian_file.write_text("{}")
            subprocess.run(["git", "-C", str(root), "add", "wiki/.obsidian/app.json"], check=True)
            (obsidian / ".DS_Store").write_bytes(b"finder")
            (obsidian / "workspace.json").write_text("{}")
            (obsidian / "graph.json").write_text("{}")
            obsidian_git = obsidian / "plugins" / "obsidian-git"
            obsidian_git.mkdir(parents=True)
            tracked_plugin_file = obsidian_git / "manifest.json"
            tracked_plugin_file.write_text("{}")
            subprocess.run(
                ["git", "-C", str(root), "add", "wiki/.obsidian/plugins/obsidian-git/manifest.json"],
                check=True,
            )
            askpass = obsidian_git / "obsidian_askpass.sh"
            askpass.write_text("#!/bin/sh\n")

            audit, errors = cleanup.audit_ignored(root, policy)

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {
                    "wiki/.obsidian/.DS_Store": "remove",
                    "wiki/.obsidian/graph.json": "keep",
                    "wiki/.obsidian/plugins/obsidian-git/obsidian_askpass.sh": "keep",
                    "wiki/.obsidian/workspace.json": "keep",
                    "wiki/raw/": "keep",
                },
            )

    def test_runtime_bytecode_is_kept_while_test_bytecode_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("**/__pycache__/\n")
            for parent, dirname in (
                ("agent", "agent/__pycache__"),
                ("tests", "tests/__pycache__"),
                ("website/scripts", "website/scripts/__pycache__"),
            ):
                source = root / parent / "tracked.py"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("tracked")
                cache = root / dirname
                cache.mkdir(parents=True)
                (cache / "value.pyc").write_bytes(b"x")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "add",
                    "agent/tracked.py",
                    "tests/tracked.py",
                    "website/scripts/tracked.py",
                ],
                check=True,
            )
            policy_path = write_policy(
                root,
                ignored_keep={
                    "agent/__pycache__/": "runtime cache",
                    "agent/**/__pycache__/": "nested runtime cache",
                },
                ignored_remove={
                    "tests/__pycache__/": "test cache",
                    "tests/**/__pycache__/": "nested test cache",
                    "website/__pycache__/": "website cache",
                    "website/**/__pycache__/": "nested website cache",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {
                    "agent/__pycache__/": "keep",
                    "tests/__pycache__/": "remove",
                    "website/scripts/__pycache__/": "remove",
                },
            )


if __name__ == "__main__":
    unittest.main()
