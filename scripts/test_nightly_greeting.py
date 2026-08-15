from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import nightly_greeting as nightly


@contextlib.contextmanager
def acquired_lock():
    yield True


class NightlyOrganizationStageTests(unittest.TestCase):
    def test_sync_subprocess_summary_is_parsed_without_official_updates(self) -> None:
        output = (
            "merged: 218 updated, 1 new, 2 departed removed\n"
            'summary-json: {"added":[{"open_id":"ou_new","name":"新同事"}],'
            '"removed":[{"open_id":"ou_old","name":"离职同事"}]}\n'
        )
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(nightly, "WORK_DIR", Path(tmp)),
            patch.object(
                nightly.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout=output),
            ),
        ):
            result = nightly.sync_feishu_organization(dt.date(2026, 8, 15), apply=False)

        self.assertEqual([item["name"] for item in result["added"]], ["新同事"])
        self.assertEqual([item["name"] for item in result["removed"]], ["离职同事"])

    def test_success_notice_happens_before_session_material(self) -> None:
        calls: list[str] = []
        state = {"org_syncs": {}, "reports": {}, "greetings": {}, "dry_runs": {}}
        args = argparse.Namespace(
            date="2026-08-14",
            dry_run=False,
            force_dry_run=False,
            skip_org_sync=False,
            skip_report=False,
            skip_greeting=False,
            force_report=False,
            force_greeting=False,
            ignore_holiday=True,
            mode=None,
        )
        sync_result = {
            "completed_at": "2026-08-14T22:00:00+08:00",
            "mode": "apply",
            "log": "sync.log",
            "added": [],
            "removed": [],
        }

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(nightly, "WORK_DIR", Path(tmp)),
            patch.object(nightly, "STATE_PATH", Path(tmp) / "state.json"),
            patch.object(nightly, "LOCK_PATH", Path(tmp) / "lock"),
            patch.object(nightly, "nightly_lock", acquired_lock),
            patch.object(nightly, "load_state", return_value=state),
            patch.object(nightly, "save_state"),
            patch.object(
                nightly,
                "sync_feishu_organization",
                side_effect=lambda _day, apply: calls.append(f"sync:{apply}") or sync_result,
            ),
            patch.object(
                nightly,
                "notify_owner_org_sync",
                side_effect=lambda _day, **_kwargs: calls.append("notify-owner"),
            ),
            patch.object(
                nightly,
                "read_daily_sessions",
                side_effect=lambda _day: calls.append("sessions") or "SESSION_ONLY_MATERIAL",
            ),
            patch.object(
                nightly,
                "run_hermes_generation",
                return_value={"today": "1. 完成", "plan": "1. 计划", "goodnight": nightly.default_goodnight()},
            ),
            patch.object(nightly, "write_artifacts"),
            patch.object(nightly, "submit_report", return_value="report.log"),
            patch.object(nightly, "send_greetings", return_value=[{"group_id": "oc_group"}]),
        ):
            nightly.run(args)

        self.assertEqual(calls[:3], ["sync:True", "notify-owner", "sessions"])

    def test_sync_failure_is_private_non_blocking_and_prompt_isolated(self) -> None:
        calls: list[str] = []
        state = {"org_syncs": {}, "reports": {}, "greetings": {}, "dry_runs": {}}
        args = argparse.Namespace(
            date="2026-08-14",
            dry_run=False,
            force_dry_run=False,
            skip_org_sync=False,
            skip_report=False,
            skip_greeting=False,
            force_report=False,
            force_greeting=False,
            ignore_holiday=True,
            mode=None,
        )

        def fail_sync(_day: dt.date, *, apply: bool):
            calls.append(f"sync:{apply}")
            raise RuntimeError("organization unavailable")

        def read_sessions(_day: dt.date) -> str:
            calls.append("sessions")
            self.assertEqual(calls[0], "sync:True")
            return "SESSION_ONLY_MATERIAL"

        def generate(prompt: str) -> dict[str, str]:
            calls.append("generate")
            self.assertIn("SESSION_ONLY_MATERIAL", prompt)
            self.assertNotIn("organization unavailable", prompt)
            return {"today": "1. 今日完成", "plan": "1. 明日计划", "goodnight": nightly.default_goodnight()}

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(nightly, "WORK_DIR", Path(tmp)),
            patch.object(nightly, "STATE_PATH", Path(tmp) / "state.json"),
            patch.object(nightly, "LOCK_PATH", Path(tmp) / "lock"),
            patch.object(nightly, "nightly_lock", acquired_lock),
            patch.object(nightly, "load_state", return_value=state),
            patch.object(nightly, "save_state"),
            patch.object(nightly, "sync_feishu_organization", side_effect=fail_sync),
            patch.object(
                nightly, "notify_owner_org_sync", side_effect=lambda _day, **_kwargs: calls.append("notify-owner")
            ),
            patch.object(nightly, "read_daily_sessions", side_effect=read_sessions),
            patch.object(nightly, "run_hermes_generation", side_effect=generate),
            patch.object(nightly, "write_artifacts"),
            patch.object(
                nightly, "submit_report", side_effect=lambda _day, _draft: calls.append("report") or "report.log"
            ),
            patch.object(
                nightly,
                "send_greetings",
                side_effect=lambda _day, _text: calls.append("greeting") or [{"group_id": "oc_group"}],
            ),
        ):
            nightly.run(args)

        self.assertIn("notify-owner", calls)
        self.assertLess(calls.index("sync:True"), calls.index("sessions"))
        self.assertLess(calls.index("sessions"), calls.index("report"))
        self.assertLess(calls.index("report"), calls.index("greeting"))
        self.assertEqual(state["org_syncs"]["2026-08-14"]["status"], "failed")

    def test_success_notification_shows_only_added_removed_and_uses_owner_chat(self) -> None:
        sent: list[tuple[str, str]] = []
        with (
            patch.object(nightly, "load_owner_chat_ids", return_value=["oc_owner"]),
            patch.object(nightly.feishu_common, "get_tenant_token", return_value="token"),
            patch.object(
                nightly,
                "send_message",
                side_effect=lambda _token, chat_id, text: sent.append((chat_id, text)) or {},
            ),
            patch.object(nightly, "load_group_ids", side_effect=AssertionError("group roster must not be read")),
        ):
            nightly.notify_owner_org_sync(
                dt.date(2026, 8, 15),
                summary={
                    "added": [{"open_id": "ou_new", "name": "新同事"}],
                    "removed": [{"open_id": "ou_old", "name": "离职同事"}],
                    "updated": [{"name": "不应展示"}],
                },
            )

        self.assertEqual([chat_id for chat_id, _text in sent], ["oc_owner"])
        self.assertIn("新增人员：新同事", sent[0][1])
        self.assertIn("移除人员：离职同事", sent[0][1])
        self.assertNotIn("不应展示", sent[0][1])

    def test_failure_notification_includes_reason_and_never_reads_groups(self) -> None:
        sent: list[tuple[str, str]] = []
        with (
            patch.object(nightly, "load_owner_chat_ids", return_value=["oc_owner"]),
            patch.object(nightly.feishu_common, "get_tenant_token", return_value="token"),
            patch.object(
                nightly,
                "send_message",
                side_effect=lambda _token, chat_id, text: sent.append((chat_id, text)) or {},
            ),
            patch.object(nightly, "load_group_ids", side_effect=AssertionError("group roster must not be read")),
        ):
            nightly.notify_owner_org_sync(
                dt.date(2026, 8, 15),
                error=RuntimeError("contact scope unavailable"),
            )

        self.assertEqual([chat_id for chat_id, _text in sent], ["oc_owner"])
        self.assertIn("组织同步失败", sent[0][1])
        self.assertIn("contact scope unavailable", sent[0][1])


if __name__ == "__main__":
    unittest.main()
