#!/usr/bin/env python3
"""Offline tests for safe staging of public sourced images."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image


SCRIPT = Path(__file__).with_name("stage_remote_images.py")
SPEC = importlib.util.spec_from_file_location("testable_stage_remote_images", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def _png_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "source.png"
    Image.new("RGB", (640, 360), color=(20, 80, 140)).save(path, format="PNG")
    return path.read_bytes()


def test_stage_images_writes_only_relative_workspace_results(tmp_path, monkeypatch):
    data = _png_bytes(tmp_path)
    monkeypatch.setattr(stage, "_validate_url", lambda value: value)
    monkeypatch.setattr(stage, "_download", lambda _url, _limit: (data, "image/png"))

    result = stage.stage_images(["https://example.com/hero"], tmp_path)

    assert result["success"] is True
    assert result["total_bytes"] == len(data)
    assert len(result["images"]) == 1
    image = result["images"][0]
    assert image["workspace_path"].startswith("sourced-images/")
    assert not Path(image["workspace_path"]).is_absolute()
    assert (tmp_path / image["workspace_path"]).read_bytes() == data
    assert (image["mime_type"], image["width"], image["height"]) == ("image/png", 640, 360)


def test_stage_images_is_atomic_when_later_download_fails(tmp_path, monkeypatch):
    data = _png_bytes(tmp_path)
    monkeypatch.setattr(stage, "_validate_url", lambda value: value)
    attempts = iter([(data, "image/png"), ValueError("second failed")])

    def fake_download(_url, _limit):
        value = next(attempts)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(stage, "_download", fake_download)
    with pytest.raises(ValueError, match="second failed"):
        stage.stage_images(["https://example.com/one", "https://example.com/two"], tmp_path)
    assert not list((tmp_path / "sourced-images").rglob("source-*"))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/image.png",
        "https://user:password@example.com/image.png",
        "https://example.com/image.png?token=secret",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ],
)
def test_validate_url_rejects_non_https_or_credentials(url):
    with pytest.raises(ValueError):
        stage._validate_url(url)
