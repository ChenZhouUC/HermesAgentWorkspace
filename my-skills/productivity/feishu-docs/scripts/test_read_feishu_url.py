#!/usr/bin/env python3
"""Offline tests for Feishu document image-import verification."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("read_feishu_url.py")
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("testable_read_feishu_url", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)


def test_detect_import_error_images_matches_only_known_placeholder(monkeypatch):
    placeholder = b"known-placeholder"
    monkeypatch.setattr(reader, "_IMPORT_ERROR_IMAGE_SHA256", hashlib.sha256(placeholder).hexdigest())
    monkeypatch.setattr(
        reader,
        "_download_doc_image",
        lambda _token, media_token: placeholder if media_token == "bad-media" else b"real-image",
    )
    blocks = [
        {
            "block_id": "bad-block",
            "block_type": 27,
            "image": {"token": "bad-media", "width": 1460, "height": 220},
        },
        {
            "block_id": "real-block",
            "block_type": 27,
            "image": {"token": "real-media", "width": 1460, "height": 220},
        },
        {
            "block_id": "different-shape",
            "block_type": 27,
            "image": {"token": "bad-media", "width": 1200, "height": 600},
        },
    ]

    assert reader.detect_import_error_images("token", blocks) == ["bad-block"]
