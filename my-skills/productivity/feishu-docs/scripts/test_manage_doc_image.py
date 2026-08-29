#!/usr/bin/env python3
"""Offline regression tests for Feishu document image and cover writes."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("manage_doc_image.py")
SPEC = importlib.util.spec_from_file_location("testable_manage_doc_image", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


def _png(tmp_path: Path, name: str = "image.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    return path


def test_upload_uses_document_scoped_media_contract(tmp_path, monkeypatch):
    image = _png(tmp_path)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"code": 0, "data": {"file_token": "box_token"}}).encode(), b""
        )

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    token = media.upload_doc_image("secret-token", str(image), parent_node="image-block", doc_token="doc-token")

    assert token == "box_token"
    command = captured["command"]
    assert "parent_type=docx_image" in command
    assert "parent_node=image-block" in command
    assert 'extra={"drive_route_token":"doc-token"}' in command
    assert f"file=@{image.resolve()}" in command
    assert captured["capture_output"] is True
    assert captured["check"] is False


def test_upload_retries_retryable_feishu_response(tmp_path, monkeypatch):
    image = _png(tmp_path)
    responses = [
        subprocess.CompletedProcess([], 0, json.dumps({"code": 1061045, "msg": "retry"}).encode(), b""),
        subprocess.CompletedProcess([], 0, json.dumps({"code": 0, "data": {"file_token": "box-ok"}}).encode(), b""),
    ]
    backoffs = []
    monkeypatch.setattr(media.subprocess, "run", lambda *_args, **_kwargs: responses.pop(0))
    monkeypatch.setattr(media.fc, "_backoff", lambda attempt: backoffs.append(attempt))

    assert media.upload_doc_image("token", str(image), parent_node="image-block", doc_token="doc-token") == "box-ok"
    assert backoffs == [0]


def test_image_validation_rejects_unknown_type_and_oversize(tmp_path, monkeypatch):
    unknown = tmp_path / "unknown.bin"
    unknown.write_bytes(b"not-an-image")
    with pytest.raises(ValueError, match="must be PNG"):
        media.validate_image_path(str(unknown))

    image = _png(tmp_path, "large.png")
    monkeypatch.setenv("HERMES_FEISHU_IMAGE_MAX_BYTES", "1000000")
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 1_000_000)
    with pytest.raises(ValueError, match="upload limit"):
        media.validate_image_path(str(image))


def test_insert_image_targets_anchor_and_updates_version(tmp_path, monkeypatch):
    image = _png(tmp_path)
    root = {"children": ["version", "heading", "body"]}
    block_map = {
        "version": {"block_type": 31},
        "heading": {
            "block_type": 4,
            "heading2": {"elements": [{"text_run": {"content": "Architecture"}}]},
        },
        "body": {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Body"}}]}},
    }
    calls = []
    monkeypatch.setattr(media.fc, "read_version_tables", lambda *_args: ([[[]]], 1, block_map, root))
    monkeypatch.setattr(
        media,
        "upload_doc_image",
        lambda token, image_path, *, parent_node, doc_token: (
            calls.append(("upload", token, image_path, parent_node, doc_token)) or "box-image"
        ),
    )
    monkeypatch.setattr(media.fc, "append_version_row", lambda *_args: "20260829.01ed")

    def fake_do_req(_token, url, method="GET", payload=None, **_kwargs):
        calls.append((method, url, payload))
        if method == "POST" and url.endswith("/children"):
            return {"code": 0, "data": {"children": [{"block_id": "image-block"}]}}
        if method == "PATCH" and url.endswith("/blocks/image-block"):
            return {"code": 0, "data": {}}
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(media.fc, "do_req", fake_do_req)
    result = media.insert_image(
        "token",
        "doc-token",
        str(image),
        position="after",
        anchor_text="Architecture",
        align="right",
        caption="System diagram",
        width=900,
        height=500,
    )

    create = next(call for call in calls if call[0] == "POST")
    assert create[2] == {"children": [{"block_type": 27, "image": {}}], "index": 2}
    upload = next(call for call in calls if call[0] == "upload")
    assert upload[3:] == ("image-block", "doc-token")
    patch = next(call for call in calls if call[0] == "PATCH")
    assert patch[2] == {
        "replace_image": {
            "token": "box-image",
            "align": 3,
            "caption": {"content": "System diagram"},
            "width": 900,
            "height": 500,
        }
    }
    assert result["version"] == "20260829.01ed"
    assert result["block_id"] == "image-block"


def test_insert_image_removes_created_block_when_upload_fails(tmp_path, monkeypatch):
    image = _png(tmp_path)
    root = {"children": ["body"]}
    block_map = {"body": {"block_type": 2, "text": {"elements": []}}}
    children = ["body"]
    deletes = []
    monkeypatch.setattr(media.fc, "read_version_tables", lambda *_args: (None, 0, block_map, root))
    monkeypatch.setattr(
        media,
        "upload_doc_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("upload failed")),
    )

    def fake_do_req(_token, url, method="GET", payload=None, **_kwargs):
        if method == "POST" and url.endswith("/children"):
            children.append("image-block")
            return {"code": 0, "data": {"children": [{"block_id": "image-block"}]}}
        if method == "GET" and url.endswith("/blocks/doc-token"):
            return {"data": {"block": {"children": list(children)}}}
        if method == "DELETE" and url.endswith("/children/batch_delete"):
            deletes.append(payload)
            del children[payload["start_index"] : payload["end_index"]]
            return {"code": 0, "data": {}}
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(media.fc, "do_req", fake_do_req)
    with pytest.raises(RuntimeError, match="upload failed"):
        media.insert_image("token", "doc-token", str(image))
    assert deletes == [{"start_index": 1, "end_index": 2}]
    assert children == ["body"]


def test_set_cover_uploads_against_document_and_patches_cover(tmp_path, monkeypatch):
    image = _png(tmp_path)
    root = {"children": ["body"]}
    block_map = {"body": {"block_type": 2, "text": {"elements": []}}}
    calls = []
    monkeypatch.setattr(media.fc, "read_version_tables", lambda *_args: (None, 0, block_map, root))
    monkeypatch.setattr(media.fc, "append_version_row", lambda *_args: "20260829.02ed")
    monkeypatch.setattr(
        media,
        "upload_doc_image",
        lambda token, image_path, *, parent_node, doc_token: (
            calls.append(("upload", parent_node, doc_token)) or "new-cover"
        ),
    )

    def fake_do_req(_token, url, method="GET", payload=None, **_kwargs):
        calls.append((method, url, payload))
        if method == "GET":
            return {"code": 0, "data": {"document": {"cover": {"token": "old-cover"}}}}
        if method == "PATCH":
            return {"code": 0, "data": {}}
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(media.fc, "do_req", fake_do_req)
    result = media.set_cover(
        "token",
        "doc-token",
        str(image),
        offset_ratio_x=0.2,
        offset_ratio_y=-0.1,
    )

    assert ("upload", "doc-token", "doc-token") in calls
    patch = next(call for call in calls if call[0] == "PATCH")
    assert patch[2] == {
        "update_cover": {"cover": {"token": "new-cover", "offset_ratio_x": 0.2, "offset_ratio_y": -0.1}}
    }
    assert result["version"] == "20260829.02ed"


def test_set_cover_restores_previous_cover_when_version_update_fails(tmp_path, monkeypatch):
    image = _png(tmp_path)
    root = {"children": ["body"]}
    block_map = {"body": {"block_type": 2, "text": {"elements": []}}}
    patches = []
    monkeypatch.setattr(media.fc, "read_version_tables", lambda *_args: (None, 0, block_map, root))
    monkeypatch.setattr(media, "upload_doc_image", lambda *_args, **_kwargs: "new-cover")
    monkeypatch.setattr(
        media.fc,
        "append_version_row",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("version failed")),
    )
    monkeypatch.setattr(media, "_restore_version_rows", lambda *_args, **_kwargs: None)

    def fake_do_req(_token, url, method="GET", payload=None, **_kwargs):
        if method == "GET":
            return {
                "code": 0,
                "data": {"document": {"cover": {"token": "old-cover", "offset_ratio_x": 0.1, "offset_ratio_y": 0.3}}},
            }
        if method == "PATCH":
            patches.append(payload)
            return {"code": 0, "data": {}}
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(media.fc, "do_req", fake_do_req)
    with pytest.raises(RuntimeError, match="version failed"):
        media.set_cover("token", "doc-token", str(image))

    assert patches == [
        {"update_cover": {"cover": {"token": "new-cover"}}},
        {"update_cover": {"cover": {"token": "old-cover", "offset_ratio_x": 0.1, "offset_ratio_y": 0.3}}},
    ]


def test_anchor_and_version_table_boundaries_are_enforced():
    root = {"children": ["version", "a", "b"]}
    block_map = {
        "version": {"block_type": 31},
        "a": {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "Overview"}}]}},
        "b": {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Overview details"}}]}},
    }
    assert (
        media.resolve_insert_index(
            root,
            block_map,
            version_table_count=1,
            insert_index=None,
            position="before",
            anchor_text="Overview",
        )
        == 1
    )
    with pytest.raises(ValueError, match="version table"):
        media.resolve_insert_index(
            root,
            block_map,
            version_table_count=1,
            insert_index=0,
            position="end",
            anchor_text=None,
        )
    with pytest.raises(ValueError, match="multiple"):
        media.resolve_insert_index(
            root,
            {
                **block_map,
                "b": {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Overview"}}]}},
            },
            version_table_count=1,
            insert_index=None,
            position="after",
            anchor_text="Overview",
        )
