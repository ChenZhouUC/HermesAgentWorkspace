#!/usr/bin/env python3
"""Offline regression tests for batch_ingest_folder.py."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import batch_ingest_folder as batch


class BatchIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "wiki"
        (self.root / "_living" / "AI-Infrastructure").mkdir(parents=True)
        (self.root / "log.md").write_text(
            "---\ntitle: Wiki Log\n---\n\n# Wiki Log\n\n"
            "## [2026-08-21] daily | Wiki maintenance\n\n"
            "### existing | Earlier work\n\n- Verification: OK\n",
            encoding="utf-8",
        )
        self.env = patch.dict(os.environ, {"WIKI_PATH": str(self.root)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _mocks(self):
        listing = {
            "data": {
                "files": [
                    {"name": "Source One", "type": "docx", "token": "doc-1"},
                    {"name": "Source Two", "type": "docx", "token": "doc-2"},
                ]
            }
        }

        def extracted(command, **_kwargs):
            token = command[-1]
            return f"| Col 0 | Col 1 |\n| --- | --- |\n| v1 | {token} |\n\nBody {token}\n"

        return (
            patch.object(batch, "get_tenant_token", return_value="tenant-token"),
            patch.object(batch, "do_req", return_value=listing),
            patch.object(batch.subprocess, "check_output", side_effect=extracted),
        )

    def test_dry_run_has_no_writes(self) -> None:
        destination = self.root / "_living" / "AI-Infrastructure"
        original_log = (self.root / "log.md").read_text(encoding="utf-8")
        mocks = self._mocks()
        with mocks[0], mocks[1], mocks[2]:
            targets = batch.ingest_folder("folder", destination, dry_run=True)
        self.assertEqual(len(targets), 2)
        self.assertFalse((destination / "Source-One.md").exists())
        self.assertEqual((self.root / "log.md").read_text(encoding="utf-8"), original_log)

    def test_write_creates_living_sources_and_one_daily_subsection(self) -> None:
        destination = self.root / "_living" / "AI-Infrastructure"
        mocks = self._mocks()
        with mocks[0], mocks[1], mocks[2]:
            written = batch.ingest_folder("folder", destination, today="2026-08-21")
        self.assertEqual(len(written), 2)
        content = (destination / "Source-One.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("# Source One\n"))
        self.assertNotIn("type:", content)
        self.assertNotIn("tags:", content)
        self.assertNotIn("| Col 0", content)
        log = (self.root / "log.md").read_text(encoding="utf-8")
        self.assertEqual(log.count("## [2026-08-21] daily |"), 1)
        self.assertEqual(log.count("### ingest | Feishu folder source extraction"), 1)
        self.assertIn("`_living/AI-Infrastructure/Source-One.md`", log)

    def test_destination_must_stay_inside_living(self) -> None:
        with self.assertRaises(ValueError):
            batch._assert_living_destination(self.root / "concepts", self.root)

    def test_existing_source_blocks_entire_batch(self) -> None:
        destination = self.root / "_living" / "AI-Infrastructure"
        existing = destination / "Source-One.md"
        existing.write_text("keep", encoding="utf-8")
        mocks = self._mocks()
        with mocks[0], mocks[1], mocks[2], self.assertRaises(FileExistsError):
            batch.ingest_folder("folder", destination)
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
        self.assertFalse((destination / "Source-Two.md").exists())


if __name__ == "__main__":
    unittest.main()
