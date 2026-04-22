#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

import jwt


DEFAULT_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
DEFAULT_HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
DEFAULT_ENV_PATH = DEFAULT_HERMES_HOME / ".env"


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _set_env_value(lines: list[str], key: str, value: str) -> list[str]:
    rendered = f"{key}={value}\n"
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = rendered
            return lines
    lines.append(rendered)
    return lines


def _write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
        delete=False,
    ) as handle:
        for line in lines:
            handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
        tmp_path = Path(handle.name)
    os.replace(tmp_path, path)


def _load_service_account(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "type",
        "project_id",
        "private_key",
        "client_email",
        "token_uri",
    }
    missing = sorted(key for key in required if not payload.get(key))
    if missing:
        raise ValueError(f"service-account JSON missing required fields: {', '.join(missing)}")
    if payload.get("type") != "service_account":
        raise ValueError("credential file is not a service-account JSON")
    return payload


def _mint_access_token(service_account: dict[str, str], scope: str) -> tuple[str, int]:
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": service_account["client_email"],
            "sub": service_account["client_email"],
            "aud": service_account["token_uri"],
            "iat": now,
            "exp": now + 3600,
            "scope": scope,
        },
        service_account["private_key"],
        algorithm="RS256",
    )
    if isinstance(assertion, bytes):
        assertion = assertion.decode("utf-8")

    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        service_account["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"token endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"token request failed: {exc}") from exc

    token = str(payload.get("access_token") or "").strip()
    expires_in = int(payload.get("expires_in") or 3600)
    if not token:
        raise RuntimeError("token endpoint returned no access_token")
    return token, expires_in


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mint a short-lived Vertex AI access token from a service-account JSON and write it into ~/.hermes/.env.",
    )
    parser.add_argument(
        "--credentials",
        default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
        help="Path to the service-account JSON. Defaults to GOOGLE_APPLICATION_CREDENTIALS.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Path to the Hermes .env file to update.",
    )
    parser.add_argument(
        "--scope",
        default=DEFAULT_SCOPE,
        help="OAuth scope for the access token.",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("VERTEX_LOCATION", "global") or "global",
        help="Vertex location to persist into the env file when absent.",
    )
    args = parser.parse_args()

    credentials_path = Path(args.credentials).expanduser().resolve() if args.credentials else None
    if credentials_path is None:
        print("GOOGLE_APPLICATION_CREDENTIALS is not set and --credentials was not provided.", file=sys.stderr)
        return 2
    if not credentials_path.exists():
        print(f"Credential file not found: {credentials_path}", file=sys.stderr)
        return 2

    env_path = Path(args.env_file).expanduser().resolve()
    service_account = _load_service_account(credentials_path)
    token, expires_in = _mint_access_token(service_account, args.scope)
    expires_at = int(time.time()) + expires_in
    vertex_openai_base_url = (
        "https://aiplatform.googleapis.com/v1/"
        f"projects/{service_account['project_id']}/locations/{args.location}/endpoints/openapi"
    )

    lines = _read_lines(env_path)
    _set_env_value(lines, "GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))
    _set_env_value(lines, "VERTEX_PROJECT_ID", str(service_account["project_id"]))
    _set_env_value(lines, "VERTEX_LOCATION", args.location)
    _set_env_value(lines, "VERTEX_OPENAI_BASE_URL", vertex_openai_base_url)
    _set_env_value(lines, "VERTEX_ACCESS_TOKEN", token)
    _set_env_value(lines, "VERTEX_ACCESS_TOKEN_EXPIRES_AT", str(expires_at))
    _write_lines(env_path, lines)

    print(f"Wrote VERTEX_ACCESS_TOKEN to {env_path}")
    print(f"Project: {service_account['project_id']}")
    print(f"Location: {args.location}")
    print(f"Base URL: {vertex_openai_base_url}")
    print(f"Expires at: {time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(expires_at))}")
    print("Run /reload in an active Hermes CLI session, or restart gateway/background processes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
