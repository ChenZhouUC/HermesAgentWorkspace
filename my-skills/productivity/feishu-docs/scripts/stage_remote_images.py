#!/usr/bin/env python3
"""Safely stage public raster images inside the current group workspace."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PIL import Image, UnidentifiedImageError


MAX_IMAGES = 8
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 5


def _bounded_env_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(1_000_000, min(maximum, value))


def _hermes_agent_root() -> Path:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    root = (home / "hermes-agent").resolve(strict=False)
    if not root.is_dir():
        raise RuntimeError("Hermes Agent runtime is unavailable")
    return root


def _validate_url(url: str) -> str:
    if not isinstance(url, str) or not url.strip() or len(url) > 4096:
        raise ValueError("each image URL must be a non-empty string of at most 4096 characters")
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("sourced images must use a public HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("image URLs must not contain embedded credentials")

    import sys

    agent_root = _hermes_agent_root()
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from tools.url_safety import has_sensitive_query_params, is_safe_url

    if has_sensitive_query_params(value):
        raise ValueError("image URLs must not contain credential-bearing query parameters")
    if not is_safe_url(value):
        raise ValueError("image URL was blocked by SSRF protection")
    return value


def _download(url: str, max_bytes: int) -> tuple[bytes, str]:
    import sys

    agent_root = _hermes_agent_root()
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from tools.url_safety import create_ssrf_safe_client

    current = _validate_url(url)
    with create_ssrf_safe_client(
        headers={"User-Agent": "Hermes-Feishu-Sourced-Image/1.0"},
        follow_redirects=False,
        timeout=30,
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("image redirect omitted the Location header")
                    current = _validate_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > max_bytes:
                            raise ValueError(f"image exceeds the {max_bytes}-byte download limit")
                    except ValueError as exc:
                        if "exceeds" in str(exc):
                            raise
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(f"image exceeds the {max_bytes}-byte download limit")
                    chunks.append(chunk)
                return b"".join(chunks), content_type
    raise ValueError("image URL exceeded the redirect limit")


def _image_info(data: bytes, content_type: str) -> tuple[str, str, int, int]:
    signatures = (
        (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
        (b"\xff\xd8\xff", "jpg", "image/jpeg"),
        (b"GIF87a", "gif", "image/gif"),
        (b"GIF89a", "gif", "image/gif"),
        (b"BM", "bmp", "image/bmp"),
        (b"II*\x00", "tiff", "image/tiff"),
        (b"MM\x00*", "tiff", "image/tiff"),
    )
    extension = mime = ""
    for prefix, candidate_extension, candidate_mime in signatures:
        if data.startswith(prefix):
            extension, mime = candidate_extension, candidate_mime
            break
    if not extension and len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        extension, mime = "webp", "image/webp"
    if not extension:
        raise ValueError(f"downloaded content is not a supported raster image ({content_type or 'unknown type'})")
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image.verify()
    except (OSError, UnidentifiedImageError):
        raise ValueError("downloaded image is corrupt or unreadable") from None
    if width <= 0 or height <= 0 or width > 20_000 or height > 20_000:
        raise ValueError("downloaded image dimensions are outside the supported range")
    return extension, mime, width, height


def stage_images(urls: list[str], workspace: Path) -> dict:
    if not 1 <= len(urls) <= MAX_IMAGES:
        raise ValueError(f"provide between 1 and {MAX_IMAGES} image URLs")
    workspace = workspace.expanduser().resolve(strict=True)
    per_image_limit = _bounded_env_int("HERMES_FEISHU_IMAGE_MAX_BYTES", MAX_IMAGE_BYTES, MAX_IMAGE_BYTES)
    total_limit = _bounded_env_int("HERMES_GROUP_MAX_DOWNLOAD_BYTES", MAX_TOTAL_BYTES, MAX_TOTAL_BYTES)
    output_dir = (workspace / "sourced-images" / time.strftime("%Y-%m-%d", time.gmtime())).resolve(strict=False)
    if not output_dir.is_relative_to(workspace):
        raise ValueError("invalid sourced-image output directory")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    created: list[Path] = []
    results = []
    total = 0
    try:
        for index, raw_url in enumerate(urls):
            url = _validate_url(raw_url)
            data, content_type = _download(url, per_image_limit)
            total += len(data)
            if total > total_limit:
                raise ValueError(f"staged images exceed the {total_limit}-byte per-call limit")
            extension, mime, width, height = _image_info(data, content_type)
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
            stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            target = output_dir / f"source-{stamp}-{index + 1}-{digest}-{uuid.uuid4().hex[:8]}.{extension}"
            with tempfile.NamedTemporaryFile("wb", dir=output_dir, prefix=".source-", delete=False) as handle:
                handle.write(data)
                staged = Path(handle.name)
            try:
                os.chmod(staged, 0o600)
                os.replace(staged, target)
            finally:
                staged.unlink(missing_ok=True)
            created.append(target)
            results.append(
                {
                    "index": index,
                    "workspace_path": str(target.relative_to(workspace)),
                    "mime_type": mime,
                    "size_bytes": len(data),
                    "width": width,
                    "height": height,
                }
            )
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {"success": True, "images": results, "total_bytes": total}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    args = parser.parse_args(argv)
    try:
        workspace_raw = os.environ.get("HERMES_GROUP_WORKSPACE", "").strip()
        if not workspace_raw:
            raise RuntimeError("HERMES_GROUP_WORKSPACE is required")
        result = stage_images(args.urls, Path(workspace_raw))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
