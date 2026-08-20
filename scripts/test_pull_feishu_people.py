from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import pull_feishu_people as sync


class PeopleMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.people = self.root / "people.yaml"
        self.draft = self.root / "people.draft.yaml"
        self.merged = self.root / "people.merged.yaml"
        self.globals = patch.multiple(
            sync,
            PEOPLE_FILE=self.people,
            DRAFT_FILE=self.draft,
            MERGED_FILE=self.merged,
        )
        self.globals.start()
        self.prettier = patch.object(sync, "prettier_format", side_effect=lambda text, _label: text)
        self.prettier.start()

    def tearDown(self) -> None:
        self.prettier.stop()
        self.globals.stop()
        self.tmp.cleanup()

    def test_merge_uses_latest_org_fields_and_preserves_custom_fields(self) -> None:
        self.people.write_text(
            """people:
  - open_id: ou_active
    user_id: old_user_id
    name: Old Name
    aliases: [自定义别名]
    role: 旧岗位
    department: 旧部门
    manager: 旧上级
    address: 老师
    background: 本地背景
    favorite_topic: 几何
  - open_id: ou_departed
    name: Departed Person
    address: 老同事
""",
            encoding="utf-8",
        )
        self.draft.write_text(
            """generated: 2026-08-15 22:00:00
people:
  - open_id: ou_active
    user_id: new_user_id
    name: New Name
    department: 新部门
    employee_no: WH0001
    direct_reports: 0
    total_reports: 0
  - open_id: ou_new
    user_id: new_employee_user_id
    name: New Employee
    role: 新岗位
    department: 新部门
    direct_reports: 0
    total_reports: 0
""",
            encoding="utf-8",
        )

        sync.cmd_merge(SimpleNamespace(apply=True, allow_large_removal=True))

        doc = sync.make_yaml().load(self.people)
        by_id = {item["open_id"]: item for item in doc["people"]}
        self.assertEqual(set(by_id), {"ou_active", "ou_new"})
        active = by_id["ou_active"]
        self.assertEqual(active["user_id"], "new_user_id")
        self.assertEqual(active["name"], "New Name")
        self.assertEqual(active["department"], "新部门")
        self.assertNotIn("role", active)
        self.assertNotIn("manager", active)
        self.assertEqual(list(active["aliases"]), ["自定义别名"])
        self.assertEqual(active["address"], "老师")
        self.assertEqual(active["background"], "本地背景")
        self.assertEqual(active["favorite_topic"], "几何")
        self.assertEqual(stat.S_IMODE(self.people.stat().st_mode), 0o600)

    def test_objective_entry_includes_tenant_user_id(self) -> None:
        entry = sync.objective_entry(
            "ou_active",
            {
                "user_id": "tenant_user_id",
                "name": "Active Person",
                "job_title": None,
                "employee_no": None,
                "join_time": None,
                "leader": None,
                "dept_ids": set(),
                "manager_name": None,
                "direct_reports": 0,
                "total_reports": 0,
            },
            {},
        )

        self.assertEqual(entry["open_id"], "ou_active")
        self.assertEqual(entry["user_id"], "tenant_user_id")

    def test_large_automatic_removal_fails_closed(self) -> None:
        current = "people:\n" + "".join(f"  - open_id: ou_{idx}\n    name: Person {idx}\n" for idx in range(5))
        self.people.write_text(current, encoding="utf-8")
        self.draft.write_text(
            """generated: 2026-08-15 22:00:00
people:
  - open_id: ou_0
    name: Person 0
""",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(RuntimeError, "automatic 20% safety limit"):
            sync.cmd_merge(SimpleNamespace(apply=True, allow_large_removal=False))

    def test_summary_only_preview_contains_only_added_and_removed(self) -> None:
        self.people.write_text(
            """people:
  - open_id: ou_active
    name: Active Person
    role: 旧岗位
  - open_id: ou_departed
    name: Departed Person
""",
            encoding="utf-8",
        )
        self.draft.write_text(
            """generated: 2026-08-15 22:00:00
people:
  - open_id: ou_active
    name: Active Person
    role: 新岗位
  - open_id: ou_new
    name: New Person
    role: 新岗位
""",
            encoding="utf-8",
        )

        sync.cmd_merge(
            SimpleNamespace(
                apply=False,
                allow_large_removal=False,
                summary_only=True,
            )
        )

        preview = self.merged.read_text(encoding="utf-8")
        self.assertIn("New Person", preview)
        self.assertIn("Departed Person", preview)
        self.assertNotIn("Active Person", preview)
        self.assertNotIn("新岗位", preview)
        self.assertNotIn("旧岗位", preview)

    def test_inactive_feishu_users_are_excluded(self) -> None:
        active = SimpleNamespace(
            status=SimpleNamespace(is_resigned=False, is_exited=False, is_unjoin=False, is_activated=True)
        )
        resigned = SimpleNamespace(
            status=SimpleNamespace(is_resigned=True, is_exited=False, is_unjoin=False, is_activated=False)
        )
        self.assertTrue(sync.is_active_employee(active))
        self.assertFalse(sync.is_active_employee(resigned))

    def test_identity_validation_rejects_missing_or_duplicate_user_ids(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "without tenant user_id"):
            sync.validate_identity_fields({"ou_missing": {"user_id": None}})

        with self.assertRaisesRegex(RuntimeError, "duplicate tenant user_id"):
            sync.validate_identity_fields(
                {
                    "ou_first": {"user_id": "same_user"},
                    "ou_second": {"user_id": "same_user"},
                }
            )

        sync.validate_identity_fields(
            {
                "ou_first": {"user_id": "first_user"},
                "ou_second": {"user_id": "second_user"},
            }
        )


if __name__ == "__main__":
    unittest.main()
