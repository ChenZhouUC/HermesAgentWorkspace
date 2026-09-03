#!/usr/bin/env python3
"""Offline tests for Feishu document image-import verification."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
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


def test_export_doc_images_writes_supported_images_and_returns_workspace_paths(monkeypatch, tmp_path):
    png = b"\x89PNG\r\n\x1a\nimage"
    jpeg = b"\xff\xd8\xffimage"
    payloads = {"png-token": png, "jpeg-token": jpeg}
    monkeypatch.setattr(reader, "_download_doc_image", lambda _token, media_token, max_bytes: payloads[media_token])
    blocks = [
        {
            "block_id": "png-block",
            "block_type": 27,
            "image": {"token": "png-token", "width": 1200, "height": 800},
        },
        {
            "block_id": "jpeg-block",
            "block_type": 27,
            "image": {"token": "jpeg-token", "width": 1600, "height": 900},
        },
    ]

    result = reader.export_doc_images("tenant-token", "doxcnSource", blocks, tmp_path, max_images=4, max_bytes=1024)

    assert result["errors"] == []
    assert result["truncated"] == 0
    assert [item["image_path"] for item in result["images"]] == [
        "feishu-doc-images/doxcnSource/01-png-block.png",
        "feishu-doc-images/doxcnSource/02-jpeg-block.jpg",
    ]
    assert [item["role"] for item in result["images"]] == ["body", "body"]
    assert (tmp_path / result["images"][0]["image_path"]).read_bytes() == png
    assert (tmp_path / result["images"][1]["image_path"]).read_bytes() == jpeg


def test_export_doc_images_excludes_import_placeholder(monkeypatch, tmp_path):
    placeholder = b"known-placeholder"
    monkeypatch.setattr(reader, "_IMPORT_ERROR_IMAGE_SHA256", hashlib.sha256(placeholder).hexdigest())
    monkeypatch.setattr(reader, "_download_doc_image", lambda _token, _media_token, max_bytes: placeholder)
    blocks = [
        {
            "block_id": "bad-block",
            "block_type": 27,
            "image": {"token": "bad-media", "width": 1460, "height": 220},
        }
    ]

    result = reader.export_doc_images("tenant-token", "doxcnSource", blocks, tmp_path, max_images=4, max_bytes=1024)

    assert result["images"] == []
    assert result["errors"] == [{"block_id": "bad-block", "error": "feishu_import_placeholder"}]
    assert not list((tmp_path / "feishu-doc-images" / "doxcnSource").iterdir())


def test_read_docx_include_images_appends_relative_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_GROUP_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(reader.fc, "get_tenant_token", lambda: "tenant-secret")

    def fake_request(_token, url):
        if url.endswith("/documents/doxcnSource"):
            return {"code": 0, "data": {"document": {"cover": {"token": "cover-token"}}}}
        return {
            "code": 0,
            "data": {
                "items": [{"block_id": "page", "block_type": 1, "page": {"elements": []}}],
                "has_more": False,
            },
        }

    monkeypatch.setattr(reader.fc, "do_req", fake_request)
    monkeypatch.setattr(reader.fc, "_check", lambda response, _label: response)
    captured = {}

    def fake_export(access_token, doc_token, blocks, workspace, **limits):
        captured.update(
            access_token=access_token,
            doc_token=doc_token,
            blocks=blocks,
            workspace=Path(workspace),
            limits=limits,
        )
        return {
            "images": [{"block_id": "image", "image_path": "feishu-doc-images/doxcnSource/01-image.png"}],
            "errors": [],
            "truncated": 0,
        }

    monkeypatch.setattr(reader, "export_doc_images", fake_export)

    output = reader.read_docx("doxcnSource", include_images=True)
    manifest = json.loads(output.split("[DOCUMENT_IMAGES]\n", 1)[1])

    assert captured["access_token"] == "tenant-secret"
    assert captured["doc_token"] == "doxcnSource"
    assert captured["workspace"] == tmp_path
    assert captured["blocks"][0]["asset_role"] == "cover"
    assert manifest["images"][0]["image_path"].startswith("feishu-doc-images/")
    assert "tenant-secret" not in output


def test_slides_url_returns_explicit_unsupported_failure():
    url = "https://whales.feishu.cn/slides/RFgisuPWylnGhodv48hcvmU3nm2"
    stdout = io.StringIO()

    with redirect_stdout(stdout):
        returncode = reader.main([url])

    payload = json.loads(stdout.getvalue())
    assert returncode != 0
    assert payload["success"] is False
    assert payload["status"] == "unsupported"
    assert payload["resource_type"] == "slides"
    assert url not in payload.get("content", "")
