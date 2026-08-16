from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch

from scripts import nightly_greeting as nightly


@contextlib.contextmanager
def acquired_lock():
    yield True


def make_args(**overrides) -> argparse.Namespace:
    values = {
        "date": "2026-08-17",
        "dry_run": False,
        "force_dry_run": False,
        "skip_org_sync": False,
        "skip_report": False,
        "skip_greeting": False,
        "force_report": False,
        "force_greeting": False,
        "ignore_holiday": False,
        "mode": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class NightlyArgumentParsingTests(unittest.TestCase):
    def test_no_options_uses_normal_mode_defaults(self) -> None:
        args = nightly.parse_args([])

        self.assertIsNone(args.date)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.force_dry_run)
        self.assertFalse(args.skip_org_sync)
        self.assertFalse(args.skip_report)
        self.assertFalse(args.skip_greeting)
        self.assertFalse(args.force_report)
        self.assertFalse(args.force_greeting)
        self.assertFalse(args.ignore_holiday)

    def test_all_dry_run_entry_points_enable_preview_mode(self) -> None:
        cases = (
            (["dryrun"], False),
            (["dry-run"], False),
            (["--dry-run"], False),
            (["--dryrun"], False),
            (["--force-dry-run"], True),
            (["--force-dryrun"], True),
        )
        for argv, forced in cases:
            with self.subTest(argv=argv):
                args = nightly.parse_args(argv)
                self.assertTrue(args.dry_run)
                self.assertEqual(args.force_dry_run, forced)

    def test_named_options_parse_with_expected_values(self) -> None:
        args = nightly.parse_args(
            [
                "--date",
                "2026-08-17",
                "--skip-org-sync",
                "--skip-report",
                "--skip-greeting",
                "--force-report",
                "--force-greeting",
                "--ignore-holiday",
            ]
        )

        self.assertEqual(args.date, "2026-08-17")
        self.assertTrue(args.skip_org_sync)
        self.assertTrue(args.skip_report)
        self.assertTrue(args.skip_greeting)
        self.assertTrue(args.force_report)
        self.assertTrue(args.force_greeting)
        self.assertTrue(args.ignore_holiday)
        self.assertFalse(args.dry_run)

    def test_invalid_date_is_rejected_by_argparse(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaisesRegex(SystemExit, "2"):
            nightly.parse_args(["--date", "2026-99-99"])

        self.assertIn("expected YYYY-MM-DD", stderr.getvalue())


class NightlyRunOptionAuditTests(unittest.TestCase):
    def run_flow(
        self,
        args: argparse.Namespace,
        *,
        state: dict | None = None,
        workday: bool = True,
    ) -> tuple[dict, dict]:
        if state is None:
            state = {"org_syncs": {}, "reports": {}, "greetings": {}, "dry_runs": {}}
        sync_result = {
            "completed_at": "2026-08-17T22:00:00+08:00",
            "mode": "preview" if args.dry_run else "apply",
            "log": "sync.log",
            "added": [],
            "removed": [],
        }
        draft = {"today": "1. 完成", "plan": "1. 计划", "goodnight": nightly.default_goodnight()}

        with (
            patch.object(nightly, "nightly_lock", acquired_lock),
            patch.object(nightly, "is_chinese_workday", return_value=workday) as calendar,
            patch.object(nightly, "load_state", return_value=state) as load_state,
            patch.object(nightly, "save_state") as save_state,
            patch.object(nightly, "sync_feishu_organization", return_value=sync_result) as sync_org,
            patch.object(nightly, "notify_owner_org_sync") as notify_owner,
            patch.object(nightly, "read_daily_sessions", return_value="SESSION") as read_sessions,
            patch.object(nightly, "run_hermes_generation", return_value=draft) as generate,
            patch.object(nightly, "write_artifacts") as write_artifacts,
            patch.object(nightly, "submit_report", return_value="report.log") as submit_report,
            patch.object(
                nightly,
                "send_greetings",
                return_value=[{"group_id": "oc_group"}],
            ) as send_greetings,
            patch.object(nightly, "send_dry_run_preview") as send_preview,
        ):
            result = nightly.run(args)

        calls = {
            "calendar": calendar,
            "load_state": load_state,
            "save_state": save_state,
            "sync_org": sync_org,
            "notify_owner": notify_owner,
            "read_sessions": read_sessions,
            "generate": generate,
            "write_artifacts": write_artifacts,
            "submit_report": submit_report,
            "send_greetings": send_greetings,
            "send_preview": send_preview,
        }
        self.assertIsNone(result)
        return calls, state

    def test_default_run_uses_selected_date_and_all_delivery_stages(self) -> None:
        calls, _state = self.run_flow(make_args(date="2026-08-18"))
        day = dt.date(2026, 8, 18)

        calls["calendar"].assert_called_once_with(day)
        calls["sync_org"].assert_called_once_with(day, apply=True)
        calls["read_sessions"].assert_called_once_with(day)
        calls["submit_report"].assert_called_once()
        calls["send_greetings"].assert_called_once()
        calls["send_preview"].assert_not_called()

    def test_skip_options_suppress_only_the_requested_stages(self) -> None:
        cases = (
            ({"skip_org_sync": True}, (False, True, True, True)),
            ({"skip_report": True}, (True, False, True, True)),
            ({"skip_greeting": True}, (True, True, False, True)),
            ({"skip_report": True, "skip_greeting": True}, (True, False, False, False)),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                calls, _state = self.run_flow(make_args(**overrides))
                sync, report, greeting, generation = expected
                self.assertEqual(calls["sync_org"].called, sync)
                self.assertEqual(calls["notify_owner"].called, sync)
                self.assertEqual(calls["submit_report"].called, report)
                self.assertEqual(calls["send_greetings"].called, greeting)
                self.assertEqual(calls["generate"].called, generation)

    def test_force_options_bypass_only_the_matching_success_marker(self) -> None:
        day_key = "2026-08-17"
        cases = (
            ({"force_report": True}, (True, False)),
            ({"force_greeting": True}, (False, True)),
        )
        for overrides, expected in cases:
            with self.subTest(overrides=overrides):
                state = {
                    "org_syncs": {},
                    "reports": {day_key: {"submitted_at": "earlier"}},
                    "greetings": {day_key: {"sent_at": "earlier"}},
                    "dry_runs": {},
                }
                calls, _state = self.run_flow(make_args(**overrides), state=state)
                report, greeting = expected
                self.assertEqual(calls["submit_report"].called, report)
                self.assertEqual(calls["send_greetings"].called, greeting)

    def test_success_markers_limit_delivery_to_pending_stages(self) -> None:
        day_key = "2026-08-17"
        cases = (
            ({"reports": {day_key: {"submitted_at": "earlier"}}}, (False, True, True)),
            ({"greetings": {day_key: {"sent_at": "earlier"}}}, (True, False, True)),
            (
                {
                    "reports": {day_key: {"submitted_at": "earlier"}},
                    "greetings": {day_key: {"sent_at": "earlier"}},
                },
                (False, False, False),
            ),
        )
        for completed, expected in cases:
            with self.subTest(completed=completed):
                state = {"org_syncs": {}, "reports": {}, "greetings": {}, "dry_runs": {}}
                state.update(completed)
                calls, _state = self.run_flow(make_args(), state=state)
                report, greeting, generation = expected
                self.assertEqual(calls["submit_report"].called, report)
                self.assertEqual(calls["send_greetings"].called, greeting)
                self.assertEqual(calls["generate"].called, generation)

    def test_skip_takes_precedence_over_force_without_generation(self) -> None:
        calls, _state = self.run_flow(
            make_args(
                skip_report=True,
                skip_greeting=True,
                force_report=True,
                force_greeting=True,
            )
        )

        calls["sync_org"].assert_called_once()
        calls["generate"].assert_not_called()
        calls["submit_report"].assert_not_called()
        calls["send_greetings"].assert_not_called()

    def test_dry_run_previews_without_apply_report_or_group_send(self) -> None:
        args = make_args(dry_run=True)
        calls, state = self.run_flow(args)

        calls["sync_org"].assert_called_once_with(dt.date(2026, 8, 17), apply=False)
        calls["send_preview"].assert_called_once_with(dt.date(2026, 8, 17), ANY, state)
        calls["submit_report"].assert_not_called()
        calls["send_greetings"].assert_not_called()

    def test_dry_run_honors_skip_org_sync(self) -> None:
        calls, _state = self.run_flow(make_args(dry_run=True, skip_org_sync=True))

        calls["sync_org"].assert_not_called()
        calls["notify_owner"].assert_not_called()
        calls["generate"].assert_called_once()
        calls["send_preview"].assert_called_once()

    def test_force_dry_run_repeats_an_existing_preview(self) -> None:
        state = {
            "org_syncs": {},
            "reports": {},
            "greetings": {},
            "dry_runs": {"2026-08-17": {"sent_at": "earlier"}},
        }
        calls, _state = self.run_flow(make_args(dry_run=True, force_dry_run=True), state=state)

        calls["generate"].assert_called_once()
        calls["send_preview"].assert_called_once()

    def test_existing_dry_run_without_force_stops_before_generation(self) -> None:
        state = {
            "org_syncs": {},
            "reports": {},
            "greetings": {},
            "dry_runs": {"2026-08-17": {"sent_at": "earlier"}},
        }
        calls, _state = self.run_flow(make_args(dry_run=True), state=state)

        calls["sync_org"].assert_called_once_with(dt.date(2026, 8, 17), apply=False)
        calls["generate"].assert_not_called()
        calls["send_preview"].assert_not_called()

    def test_rest_day_blocks_dry_run_and_force_modes(self) -> None:
        cases = (
            {},
            {"dry_run": True},
            {"force_report": True},
            {"force_greeting": True},
            {"dry_run": True, "force_dry_run": True},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                calls, _state = self.run_flow(make_args(**overrides), workday=False)
                calls["load_state"].assert_not_called()
                calls["sync_org"].assert_not_called()
                calls["generate"].assert_not_called()
                calls["send_preview"].assert_not_called()
                calls["submit_report"].assert_not_called()
                calls["send_greetings"].assert_not_called()

    def test_ignore_holiday_is_the_only_rest_day_override(self) -> None:
        calls, _state = self.run_flow(make_args(ignore_holiday=True), workday=False)

        calls["calendar"].assert_not_called()
        calls["sync_org"].assert_called_once()
        calls["submit_report"].assert_called_once()
        calls["send_greetings"].assert_called_once()


class NightlyOrganizationStageTests(unittest.TestCase):
    def test_rest_day_skips_entire_task_before_state_and_org_sync(self) -> None:
        args = argparse.Namespace(
            date="2026-08-16",
            dry_run=False,
            force_dry_run=False,
            skip_org_sync=False,
            skip_report=False,
            skip_greeting=False,
            force_report=False,
            force_greeting=False,
            ignore_holiday=False,
            mode=None,
        )

        with (
            patch.object(nightly, "nightly_lock", acquired_lock),
            patch.object(nightly, "is_chinese_workday", return_value=False) as is_workday,
            patch.object(nightly, "load_state") as load_state,
            patch.object(nightly, "sync_feishu_organization") as sync_org,
            patch.object(nightly, "notify_owner_org_sync") as notify_owner,
            patch.object(nightly, "read_daily_sessions") as read_sessions,
            patch.object(nightly, "run_hermes_generation") as generate,
        ):
            result = nightly.run(args)

        self.assertIsNone(result)
        is_workday.assert_called_once_with(dt.date(2026, 8, 16))
        load_state.assert_not_called()
        sync_org.assert_not_called()
        notify_owner.assert_not_called()
        read_sessions.assert_not_called()
        generate.assert_not_called()

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

    def test_preview_notification_is_explicitly_non_applying(self) -> None:
        sent: list[str] = []
        with (
            patch.object(nightly, "load_owner_chat_ids", return_value=["oc_owner"]),
            patch.object(nightly.feishu_common, "get_tenant_token", return_value="token"),
            patch.object(
                nightly,
                "send_message",
                side_effect=lambda _token, _chat_id, text: sent.append(text) or {},
            ),
        ):
            nightly.notify_owner_org_sync(
                dt.date(2026, 8, 17),
                summary={"mode": "preview", "added": [], "removed": []},
            )

        self.assertIn("同步预览完成", sent[0])
        self.assertIn("未写入 people.yaml", sent[0])
        self.assertNotIn("✅", sent[0])

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
