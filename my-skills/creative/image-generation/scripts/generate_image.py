#!/usr/bin/env python3
"""Generate or edit one image through the configured async media API.

The script is intentionally a narrow stdin/stdout helper for the Hermes
Feishu-group sandbox plugin. It accepts JSON on stdin, writes only below
``HERMES_GROUP_WORKSPACE``, and emits one JSON object on stdout. Credentials
are read from the environment and are never included in results or errors.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

CATALOG_PATH = "/media/catalog"
IMAGE_GENERATION_PATH = "/media/image/generations"
FALLBACK_MODELS = (
    "gpt-image-2",
    "nano-banana-pro",
    "nano-banana-2",
    "grok-imagine-image",
)
MODEL_ALIASES = {
    "gpt": "gpt-image-2",
    "nano-banana": "nano-banana-pro",
    "grok-image": "grok-imagine-image",
}
UPLOAD_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_JSON_BYTES = 2 * 1024 * 1024
PROMPT_MAX_CHARS = 4000
POLL_INTERVAL_SECONDS = 5.0


class MediaError(RuntimeError):
    """A bounded, user-safe media API failure."""


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, default))))
    except (TypeError, ValueError):
        return default


def _credentials() -> tuple[str, str]:
    key = os.environ.get("IMAGE_GENERATION_API_KEY", "").strip()
    if not key:
        raise MediaError("image generation credential is not configured for the Hermes gateway")
    base = os.environ.get("IMAGE_GENERATION_API_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise MediaError("image generation endpoint is not configured for the Hermes gateway")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MediaError("image generation API base URL must be an HTTPS origin without embedded credentials")
    if parsed.query or parsed.fragment:
        raise MediaError("image generation API base URL must not contain a query string or fragment")
    return key, base


def _scrub(value: object, key: str) -> str:
    text = str(value)
    if key:
        text = text.replace(key, "[REDACTED]")
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@", r"\1[REDACTED]@", text)
    return text


def _read_limited(response: Any, max_bytes: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared:
        try:
            if int(declared) > max_bytes:
                raise MediaError(f"response exceeds {max_bytes} byte limit")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_bytes - total + 1))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise MediaError(f"response exceeds {max_bytes} byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _request_bytes(
    method: str,
    url: str,
    *,
    key: str,
    body: bytes | None = None,
    content_type: str | None = None,
    authenticated: bool = True,
    timeout: float = 60.0,
    max_bytes: int = MAX_JSON_BYTES,
) -> tuple[bytes, str]:
    headers = {"User-Agent": "hermes-group-image/1.0"}
    if authenticated:
        headers["Authorization"] = f"Bearer {key}"
    if content_type:
        headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            data = _read_limited(response, max_bytes)
            response_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            return data, response_type
    except HTTPError as exc:
        try:
            detail = exc.read(4096).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - HTTPError bodies are best-effort diagnostics
            detail = ""
        safe_detail = _scrub(detail, key)[:600]
        suffix = f": {safe_detail}" if safe_detail else ""
        raise MediaError(f"HTTP {exc.code}{suffix}") from None
    except MediaError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize all transport failures
        raise MediaError(_scrub(exc, key)[:600]) from None


def _request_json(
    method: str,
    url: str,
    *,
    key: str,
    payload: dict[str, Any] | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    raw, _ = _request_bytes(
        method,
        url,
        key=key,
        body=body,
        content_type=content_type,
        timeout=timeout,
    )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MediaError(f"invalid JSON response: {exc}") from None
    if not isinstance(parsed, dict):
        raise MediaError("API response must be a JSON object")
    return parsed


def _with_retry(label: str, operation: Callable[[], Any], attempts: int = 6) -> Any:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - retry wrapper preserves final cause
            last = exc
            if attempt == attempts - 1:
                break
            time.sleep(min(2 ** (attempt + 1), 10))
    raise MediaError(f"{label} failed after {attempts} attempts: {last}")


def _workspace() -> Path:
    raw = os.environ.get("HERMES_GROUP_WORKSPACE", "").strip()
    if not raw:
        raise MediaError("HERMES_GROUP_WORKSPACE is not set")
    workspace = Path(raw).resolve(strict=True)
    if not workspace.is_dir() or workspace.is_symlink():
        raise MediaError("group workspace is unavailable")
    return workspace


def _workspace_input(workspace: Path, relative: object) -> Path:
    text = str(relative or "").strip()
    raw = Path(text)
    if not text or raw.is_absolute() or text.startswith("~") or ".." in raw.parts:
        raise MediaError("input image path must be relative to the group workspace")
    lexical = workspace / raw
    if lexical.is_symlink():
        raise MediaError("symbolic-link image inputs are not allowed")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_relative_to(workspace) or not resolved.is_file():
        raise MediaError("input image is outside the group workspace")
    if resolved.suffix.lower() not in UPLOAD_MIME:
        raise MediaError("input image must be PNG, JPEG, or WebP")
    return resolved


def _catalog(key: str, base: str) -> list[dict[str, Any]]:
    body = _with_retry(
        "catalog",
        lambda: _request_json("GET", base + CATALOG_PATH, key=key),
    )
    models = ((body.get("data") or {}).get("models") or []) if isinstance(body.get("data"), dict) else []
    return [item for item in models if isinstance(item, dict) and item.get("kind") == "image"]


def _resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


def _scope_for_mode(model: dict[str, Any], mode: str) -> dict[str, Any]:
    modes = model.get("modes")
    if isinstance(modes, dict) and isinstance(modes.get(mode), dict):
        return modes[mode]
    return model


def _pick_mode(model: dict[str, Any], requested: object) -> str:
    allowed = (model.get("allowed") or {}).get("mode") if isinstance(model.get("allowed"), dict) else None
    modes = [str(value) for value in allowed] if isinstance(allowed, list) else []
    wanted = str(requested or "").strip()
    default = str(model.get("default_mode") or "").strip()
    if wanted and wanted in modes:
        return wanted
    if default and (not modes or default in modes):
        return default
    return modes[0] if modes else "standard"


def _snap(model: dict[str, Any], mode: str, field: str, requested: object) -> object | None:
    scope = _scope_for_mode(model, mode)
    scope_allowed = scope.get("allowed") if isinstance(scope.get("allowed"), dict) else {}
    model_allowed = model.get("allowed") if isinstance(model.get("allowed"), dict) else {}
    scope_defaults = scope.get("defaults") if isinstance(scope.get("defaults"), dict) else {}
    model_defaults = model.get("defaults") if isinstance(model.get("defaults"), dict) else {}
    allowed = scope_allowed.get(field, model_allowed.get(field))
    default = scope_defaults.get(field, model_defaults.get(field))
    if not isinstance(allowed, list) or not allowed:
        return default
    if requested in allowed:
        return requested
    return default if default is not None else allowed[0]


def _can_run(model: dict[str, Any], has_images: bool) -> bool:
    constraints = model.get("constraints") if isinstance(model.get("constraints"), dict) else {}
    image_count = constraints.get("image_input_count") if isinstance(constraints, dict) else {}
    minimum = image_count.get("min", 0) if isinstance(image_count, dict) else 0
    try:
        return has_images or int(minimum or 0) <= 0
    except (TypeError, ValueError):
        return has_images


def _generation_type(model: dict[str, Any], has_images: bool) -> str:
    allowed = (model.get("allowed") or {}).get("generation_type") if isinstance(model.get("allowed"), dict) else None
    preferred = ["image_to_image", "text_to_image"] if has_images else ["text_to_image"]
    if isinstance(allowed, list) and allowed:
        return next((item for item in preferred if item in allowed), str(allowed[0]))
    return "image_to_image" if has_images else "text_to_image"


def _multipart_file(path: Path) -> tuple[bytes, str]:
    boundary = f"----HermesMedia{uuid.uuid4().hex}"
    mime = UPLOAD_MIME[path.suffix.lower()]
    name = path.name.replace('"', "")
    body = bytearray()
    for field, value in (("display_name", name),):
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{field}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode())
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _upload_asset(path: Path, key: str, base: str) -> dict[str, str]:
    max_input = _bounded_int("HERMES_GROUP_IMAGE_MAX_INPUT_BYTES", 25_000_000, 1_000_000, 100_000_000)
    if path.stat().st_size > max_input:
        raise MediaError(f"input image exceeds {max_input} byte limit")
    body, content_type = _multipart_file(path)
    response = _with_retry(
        f"upload {path.name}",
        lambda: _request_json(
            "POST",
            base + "/media/files",
            key=key,
            body=body,
            content_type=content_type,
        ),
    )
    file_info = ((response.get("data") or {}).get("file") or {}) if isinstance(response.get("data"), dict) else {}
    uri = str(file_info.get("uri") or "").strip() if isinstance(file_info, dict) else ""
    name = str(file_info.get("name") or "").strip() if isinstance(file_info, dict) else ""
    if not uri or not name:
        raise MediaError("upload response had no file uri")
    return {"uri": uri, "name": name}


def _delete_asset(uploaded: dict[str, str], key: str, base: str) -> None:
    asset_id = uploaded.get("name", "").rsplit("/", 1)[-1]
    if not asset_id:
        return
    try:
        _request_bytes(
            "DELETE",
            f"{base}/media/files/{quote(asset_id, safe='')}",
            key=key,
            max_bytes=64 * 1024,
        )
    except Exception:  # noqa: BLE001,S110 - remote cleanup is best effort
        pass


def _submit_job(payload: dict[str, Any], key: str, base: str) -> str:
    response = _with_retry(
        "submit",
        lambda: _request_json("POST", base + IMAGE_GENERATION_PATH, key=key, payload=payload),
        attempts=3,
    )
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    generation_id = str(data.get("id") or "").strip()
    if not generation_id:
        raise MediaError("Media API returned no generation id")
    return generation_id


def _cancel_job(generation_id: str, key: str, base: str) -> None:
    try:
        _request_bytes(
            "POST",
            f"{base}{IMAGE_GENERATION_PATH}/{quote(generation_id, safe='')}/cancel",
            key=key,
            max_bytes=64 * 1024,
        )
    except Exception:  # noqa: BLE001,S110 - remote cancellation is best effort
        pass


def _poll_job(generation_id: str, key: str, base: str) -> tuple[str, str]:
    timeout_seconds = _bounded_int("HERMES_GROUP_IMAGE_JOB_TIMEOUT", 900, 30, 1200)
    deadline = time.monotonic() + timeout_seconds
    url = f"{base}{IMAGE_GENERATION_PATH}/{quote(generation_id, safe='')}"
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        response = _with_retry("poll", lambda: _request_json("GET", url, key=key))
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        status = str(data.get("status") or "").strip().lower()
        if status == "completed":
            result = data.get("result") if isinstance(data.get("result"), dict) else {}
            outputs = result.get("outputs") if isinstance(result, dict) else []
            for entry in outputs if isinstance(outputs, list) else []:
                if isinstance(entry, str) and entry:
                    return entry, status
                if isinstance(entry, dict):
                    value = entry.get("url") or entry.get("uri")
                    if isinstance(value, str) and value:
                        return value, status
            raise MediaError("job completed but returned no output URL")
        if status in {"failed", "cancelled"}:
            code = str(data.get("error_code") or status)
            detail = str(data.get("error_message") or "no detail")[:600]
            raise MediaError(f"generation {code}: {detail}")
    _cancel_job(generation_id, key, base)
    raise MediaError(f"generation timed out after {timeout_seconds} seconds")


def _validate_output_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MediaError("generation output must be an HTTPS URL without embedded credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        raise MediaError("generation output host is not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return url
    if not address.is_global:
        raise MediaError("generation output address is not public")
    return url


def _image_extension(data: bytes, content_type: str) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    raise MediaError(f"generation output is not a supported image ({content_type or 'unknown content type'})")


def _download_output(url: str, key: str) -> tuple[bytes, str, str]:
    max_output = _bounded_int("HERMES_GROUP_IMAGE_MAX_OUTPUT_BYTES", 10_000_000, 1_000_000, 20_000_000)
    raw, content_type = _with_retry(
        "download",
        lambda: _request_bytes(
            "GET",
            _validate_output_url(url),
            key=key,
            authenticated=False,
            timeout=120,
            max_bytes=max_output,
        ),
    )
    extension, mime = _image_extension(raw, content_type)
    return raw, extension, mime


def _write_output(workspace: Path, data: bytes, extension: str) -> Path:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    output_dir = (workspace / "generated-images" / day).resolve(strict=False)
    if not output_dir.is_relative_to(workspace):
        raise MediaError("invalid generated-image output directory")
    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = output_dir / f"image-{stamp}-{uuid.uuid4().hex[:8]}.{extension}"
    with tempfile.NamedTemporaryFile("wb", dir=output_dir, prefix=".image-", delete=False) as handle:
        handle.write(data)
        staged = Path(handle.name)
    try:
        os.chmod(staged, 0o600)
        os.replace(staged, target)
    finally:
        if staged.exists():
            staged.unlink()
    return target


def generate(request_data: dict[str, Any]) -> dict[str, Any]:
    workspace = _workspace()
    key, base = _credentials()
    prompt = str(request_data.get("prompt") or "").strip()
    if not prompt:
        raise MediaError("prompt is required")
    if len(prompt) > PROMPT_MAX_CHARS:
        raise MediaError(f"prompt exceeds {PROMPT_MAX_CHARS} characters")

    raw_paths = request_data.get("image_paths") or []
    if not isinstance(raw_paths, list):
        raise MediaError("image_paths must be a list")
    max_inputs = _bounded_int("HERMES_GROUP_IMAGE_MAX_INPUTS", 4, 1, 8)
    if len(raw_paths) > max_inputs:
        raise MediaError(f"at most {max_inputs} input images are allowed")
    input_paths = [_workspace_input(workspace, item) for item in raw_paths]

    models = _catalog(key, base)
    by_id = {str(item.get("public_model")): item for item in models if item.get("public_model")}
    requested_model = str(request_data.get("model") or "").strip()
    chain = (
        [_resolve_model(requested_model)]
        if requested_model
        else [
            model_id
            for model_id in FALLBACK_MODELS
            if model_id in by_id and _can_run(by_id[model_id], bool(input_paths))
        ]
    )
    if not chain:
        raise MediaError(f"no usable image model; available: {', '.join(sorted(by_id))}")

    uploaded: list[dict[str, str]] = []
    failures: list[str] = []
    try:
        uploaded = [_upload_asset(path, key, base) for path in input_paths]
        image_urls = [item["uri"] for item in uploaded]
        for model_id in chain:
            model = by_id.get(model_id)
            if model is None:
                failures.append(f"{model_id}: not in catalog")
                continue
            mode = _pick_mode(model, request_data.get("mode"))
            payload: dict[str, Any] = {
                "model": model_id,
                "mode": mode,
                "client_request_id": f"hermes-group-{uuid.uuid4()}",
                "prompt": prompt,
                "generation_type": _generation_type(model, bool(image_urls)),
            }
            resolution = _snap(model, mode, "resolution", request_data.get("resolution"))
            aspect = _snap(model, mode, "aspect_ratio", request_data.get("aspect_ratio"))
            if resolution is not None:
                payload["resolution"] = resolution
            if aspect is not None:
                payload["aspect_ratio"] = aspect
            if image_urls:
                payload["image_urls"] = image_urls
            try:
                generation_id = _submit_job(payload, key, base)
                output_url, _ = _poll_job(generation_id, key, base)
                image_bytes, extension, mime = _download_output(output_url, key)
                output = _write_output(workspace, image_bytes, extension)
                return {
                    "success": True,
                    "image": str(output.relative_to(workspace)),
                    "mime_type": mime,
                    "size_bytes": len(image_bytes),
                    "model": model_id,
                    "mode": mode,
                    "generation_id": generation_id,
                    "fallback_failures": failures,
                }
            except Exception as exc:  # noqa: BLE001 - advance to the next configured fallback
                failures.append(f"{model_id}: {_scrub(exc, key)[:600]}")
        raise MediaError("all image models failed: " + "; ".join(failures))
    finally:
        for asset in uploaded:
            _delete_asset(asset, key, base)


def main() -> int:
    key = os.environ.get("IMAGE_GENERATION_API_KEY", "")
    try:
        raw = os.read(0, 64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise MediaError("request exceeds 64 KiB")
        request_data = json.loads(raw.decode("utf-8"))
        if not isinstance(request_data, dict):
            raise MediaError("request must be a JSON object")
        result = generate(request_data)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns one sanitized JSON error
        print(
            json.dumps(
                {
                    "success": False,
                    "error": _scrub(exc, key)[:1000],
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
