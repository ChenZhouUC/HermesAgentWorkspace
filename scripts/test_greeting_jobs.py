from __future__ import annotations

import contextlib
import copy
import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import greeting_jobs, morning_greeting, nightly_greeting


class GreetingDefinitionTests(unittest.TestCase):
    def test_definitions_use_the_same_fields_without_private_runtime_values(self):
        for name in greeting_jobs.JOB_NAMES:
            with self.subTest(name=name):
                definition = greeting_jobs.load_definition(name)
                self.assertEqual(set(definition), greeting_jobs.DEFINITION_FIELDS)
                self.assertNotRegex(json.dumps(definition), r"(?:oc_|ou_)[A-Za-z0-9]{20,}|/Users/|Bearer ")
                self.assertEqual(
                    [line.split("：", 1)[0] for line in definition["prompt"].splitlines()],
                    ["时间", "日历", "流程", "投递", "重跑", "预览"],
                )
        self.assertEqual(morning_greeting.REPORT_TIME, dt.time(9))

    def test_private_fields_and_unsafe_execution_modes_are_rejected(self):
        original = greeting_jobs.load_definition("morning_greeting")
        changes = (
            {"origin": {"chat_id": "oc_private"}},
            {"next_run_at": "2026-09-14T09:00:00+08:00"},
            {"script": "another.py"},
            {"no_agent": False},
            {"deliver": "feishu:oc_group"},
            {"enabled_toolsets": ["terminal"]},
            {"schedule": "0 9 * * 1-5"},
            {"schedule": "0 25 * * *"},
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for changeset in changes:
                (root / "morning_greeting.json").write_text(json.dumps({**original, **changeset}))
                with self.subTest(changes=changeset), patch.object(greeting_jobs, "DEFINITIONS_DIR", root):
                    with self.assertRaises(ValueError):
                        greeting_jobs.load_definition("morning_greeting")


class GreetingInstallTests(unittest.TestCase):
    def test_migration_preserves_ids_history_pending_runs_and_other_jobs(self):
        from cron import jobs

        with tempfile.TemporaryDirectory() as raw, jobs.use_cron_store(Path(raw)):
            home = Path(raw)
            for name, hour in (("morning_greeting", 9), ("nightly_greeting", 22)):
                job = jobs.create_job(
                    "old description",
                    f"0 {hour} * * *",
                    name="legacy " + name,
                    script=f"{name}.py",
                    no_agent=True,
                    workdir=str(home.parent),
                    enabled_toolsets=["terminal", "file"],
                )
                jobs.update_job(
                    job["id"],
                    {
                        "next_run_at": "2026-09-14T08:50:00+08:00",
                        "last_run_at": "2026-09-13T22:00:00+08:00",
                        "last_status": "ok",
                        "repeat": {"times": None, "completed": 12},
                    },
                )
            before = copy.deepcopy(jobs.list_jobs(include_disabled=True))
            for old in before:
                name = Path(old["script"]).stem
                other_id = next(job["id"] for job in before if job["id"] != old["id"])
                other = jobs.get_job(other_id)
                migrated = greeting_jobs.install_job(name, home, "oc_owner")
                self.assertEqual(migrated["name"], name)
                self.assertEqual(migrated["workdir"], str(home.resolve()))
                self.assertIsNone(migrated["enabled_toolsets"])
                self.assertEqual(migrated["origin"], {"platform": "feishu", "chat_id": "oc_owner"})
                for key in (
                    "id",
                    "created_at",
                    "last_run_at",
                    "last_status",
                    "repeat",
                    "next_run_at",
                    "enabled",
                    "state",
                ):
                    self.assertEqual(migrated[key], old[key], key)
                self.assertEqual(jobs.get_job(other["id"]), other)
                with patch.object(jobs, "update_job", side_effect=AssertionError("unchanged job was rewritten")):
                    self.assertEqual(greeting_jobs.install_job(name, home, "oc_owner"), migrated)
            self.assertEqual(len(jobs.list_jobs(include_disabled=True)), 2)

    def test_schedule_change_recomputes_next_run_and_preserves_pause(self):
        from cron import jobs

        now = dt.datetime.fromisoformat("2026-09-14T08:00:00+08:00")
        with tempfile.TemporaryDirectory() as raw, jobs.use_cron_store(Path(raw)):
            with patch.object(jobs, "_hermes_now", return_value=now):
                old = jobs.create_job(
                    "old", "0 10 * * *", name="morning_greeting", script="morning_greeting.py", no_agent=True
                )
                updated = greeting_jobs.install_job("morning_greeting", Path(raw), "oc_owner")
                self.assertEqual(updated["id"], old["id"])
                self.assertEqual(updated["next_run_at"], "2026-09-14T09:00:00+08:00")
                paused = jobs.pause_job(old["id"], reason="operator paused")
                jobs.update_job(old["id"], {"prompt": "stale description"})
                updated = greeting_jobs.install_job("morning_greeting", Path(raw), "oc_owner")
                for key in ("enabled", "state", "paused_at", "paused_reason", "next_run_at"):
                    self.assertEqual(updated[key], paused[key], key)

    def test_duplicate_script_matches_refuse_mutation(self):
        from cron import jobs

        with tempfile.TemporaryDirectory() as raw, jobs.use_cron_store(Path(raw)):
            for name in ("old nightly", "nightly_greeting"):
                jobs.create_job("old", "0 22 * * *", name=name, script="nightly_greeting.py", no_agent=True)
            before = copy.deepcopy(jobs.list_jobs(include_disabled=True))
            with self.assertRaisesRegex(RuntimeError, "Multiple nightly_greeting"):
                greeting_jobs.install_job("nightly_greeting", Path(raw), "oc_owner")
            self.assertEqual(jobs.list_jobs(include_disabled=True), before)

    def test_nightly_entry_point_installs_without_running_workflow(self):
        from cron import jobs

        with tempfile.TemporaryDirectory() as raw, jobs.use_cron_store(Path(raw)):
            with (
                patch.object(nightly_greeting, "HERMES_HOME", Path(raw)),
                patch.object(nightly_greeting, "load_owner_chat_ids", return_value=["oc_owner"]),
                patch.object(nightly_greeting, "run", side_effect=AssertionError("workflow ran during install")),
                patch.object(sys, "argv", ["nightly_greeting.py", "--install"]),
                patch("hermes_cli.env_loader.load_hermes_dotenv"),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(nightly_greeting.main(), 0)
                installed = json.loads(output.getvalue())
                first = jobs.get_job(installed["id"])
                second = nightly_greeting.install_job()
                self.assertEqual(first, second)
                self.assertEqual(first["name"], "nightly_greeting")
                self.assertEqual(first["schedule"]["expr"], "0 22 * * *")


if __name__ == "__main__":
    unittest.main()
