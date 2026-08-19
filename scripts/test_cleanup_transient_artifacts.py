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
        with tempfile.TemporaryDirectory() as root_raw, tempfile.TemporaryDirectory() as trash_raw:
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
        with tempfile.TemporaryDirectory() as root_raw, tempfile.TemporaryDirectory() as trash_raw:
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

    def test_transaction_lock_is_explicitly_keep_classified(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("*.lock\n")
            lock_dir = root / ".hermes-update-transaction.lock"
            lock_dir.mkdir()
            (lock_dir / "owner").write_text("test")
            policy_path = write_policy(
                root,
                ignored_keep={
                    ".hermes-update-transaction.lock/": "transaction lock",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0].classification, "keep")

    def test_runtime_bytecode_is_kept_while_test_bytecode_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as root_raw:
            root = Path(root_raw)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("**/__pycache__/\n")
            for parent, dirname in (("agent", "agent/__pycache__"), ("tests", "tests/__pycache__")):
                source = root / parent / "tracked.py"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text("tracked")
                cache = root / dirname
                cache.mkdir(parents=True)
                (cache / "value.pyc").write_bytes(b"x")
            subprocess.run(["git", "-C", str(root), "add", "agent/tracked.py", "tests/tracked.py"], check=True)
            policy_path = write_policy(
                root,
                ignored_keep={
                    "agent/__pycache__/": "runtime cache",
                    "agent/**/__pycache__/": "nested runtime cache",
                },
                ignored_remove={
                    "tests/__pycache__/": "test cache",
                    "tests/**/__pycache__/": "nested test cache",
                },
            )

            audit, errors = cleanup.audit_ignored(root, cleanup.load_policy(policy_path))

            self.assertEqual(errors, [])
            self.assertEqual(
                {item.path: item.classification for item in audit},
                {"agent/__pycache__/": "keep", "tests/__pycache__/": "remove"},
            )


if __name__ == "__main__":
    unittest.main()
