#!/usr/bin/env bash
# Verify the user-level Claude SC provider against the installed Hermes runtime.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_AGENT="${HERMES_HOME}/hermes-agent"
VENV_PYTHON="${HERMES_AGENT}/venv/bin/python"
PLUGIN_DIR="${HERMES_HOME}/plugins/model-providers/claude-sc"

if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "FAIL Hermes virtualenv Python is unavailable: ${VENV_PYTHON}"
    exit 1
fi
if [[ ! -x "${HOME}/bin/claude-sc" ]]; then
    echo "FAIL claude-sc wrapper is unavailable: ${HOME}/bin/claude-sc"
    exit 1
fi

PYTHONPATH="${HERMES_AGENT}" HERMES_HOME="${HERMES_HOME}" "${VENV_PYTHON}" - \
    "${HERMES_HOME}/config.yaml" "${HERMES_HOME}/.env" \
    "${PLUGIN_DIR}/plugin.yaml" "${PLUGIN_DIR}/__init__.py" "${PLUGIN_DIR}/verify.sh" <<'PY'
import json
import os
import sys
from pathlib import Path

import anthropic  # Import before monkeypatching httpx.Client; the SDK subclasses it at import time.
import httpx
import yaml

config_path, env_path, manifest_path, plugin_path, verifier_path = map(Path, sys.argv[1:])
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

fallbacks = config.get("fallback_providers") or []
assert len(fallbacks) >= 2
assert fallbacks[0] == {"provider": "claude-sc", "model": "claude-fable-5-1"}
assert fallbacks[1].get("provider") == "vertex"
assert fallbacks[1].get("model") == "google/gemini-3.7-flash"
assert (
    config.get("providers", {})
    .get("claude-sc", {})
    .get("models", {})
    .get("claude-fable-5-1", {})
    .get("supports_vision")
    is True
)
assert manifest.get("kind") == "model-provider"
assert manifest.get("name") == "claude-sc"
assert env_path.stat().st_mode & 0o777 == 0o600

from hermes_cli.config import load_config

load_config()
from agent.image_routing import decide_image_input_mode
from hermes_cli.runtime_provider import resolve_runtime_provider
from providers import get_provider_profile

profile = get_provider_profile("claude-sc")
assert profile is not None
assert profile.auth_type == "external_process"
assert profile.api_mode == "chat_completions"
assert profile.fetch_models() == ["claude-fable-5-1"]
assert Path(profile.process_command).samefile(Path.home() / "bin" / "claude-sc")

runtime = resolve_runtime_provider(requested="claude-sc", target_model="claude-fable-5-1")
assert runtime.get("provider") == "claude-sc"
assert runtime.get("api_mode") == "chat_completions"
assert Path(str(runtime.get("command"))).samefile(Path.home() / "bin" / "claude-sc")
assert decide_image_input_mode(
    "claude-sc", "claude-fable-5-1", config, requested_provider="claude-sc"
) == "native"

prepared = profile.prepare_messages([
    {"role": "system", "content": "stable system"},
    {"role": "user", "content": "call the probe tool"},
])
reasoning_extra, reasoning_top = profile.build_api_kwargs_extras(
    reasoning_config={"enabled": True, "effort": "high"}
)
assert reasoning_extra == {}
assert reasoning_top == {"_reasoning_config": {"enabled": True, "effort": "high"}}

captured = {}
real_httpx_client_init = httpx.Client.__init__

def handler(request: httpx.Request) -> httpx.Response:
    captured["path"] = request.url.path
    captured["headers"] = {key.lower(): value for key, value in request.headers.items()}
    captured["body"] = json.loads(request.content)
    return httpx.Response(
        418,
        request=request,
        json={"type": "error", "error": {"type": "api_error", "message": "offline verifier"}},
    )

def mock_client_init(self, *args, **kwargs):
    kwargs["transport"] = httpx.MockTransport(handler)
    return real_httpx_client_init(self, *args, **kwargs)

httpx.Client.__init__ = mock_client_init
try:
    client = profile.create_client(timeout=5)
    try:
        client.chat.completions.create(
            model="claude-fable-5-1",
            max_tokens=64,
            messages=prepared,
            tools=[{
                "type": "function",
                "function": {
                    "name": "probe",
                    "description": "offline verifier",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
            _reasoning_config=reasoning_top["_reasoning_config"],
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 418
    finally:
        client.close()
finally:
    httpx.Client.__init__ = real_httpx_client_init

headers = captured["headers"]
body = captured["body"]
assert captured["path"] == "/v1/messages"
assert headers.get("authorization", "").startswith("Bearer ")
assert "x-api-key" not in headers
assert headers.get("user-agent", "").startswith("claude-cli/")
assert headers.get("x-app") == "cli"
assert headers.get("x-stainless-lang") == "js"
assert body.get("model") == "claude-fable-5-1"
assert body.get("thinking", {}).get("type") == "adaptive"
assert body.get("output_config", {}).get("effort") == "high"
assert (body.get("system") or [])[0].get("text", "").startswith("You are Claude Code")
assert (body.get("tools") or [])[0].get("name") == "mcp__probe"
assert any(
    isinstance(block, dict) and block.get("cache_control")
    for message in [*(body.get("system") or []), *(body.get("messages") or [])]
    for block in (
        message.get("content")
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        else [message]
    )
)

from gateway.status import get_running_pid
import psutil

gateway_pid = get_running_pid()
assert isinstance(gateway_pid, int) and gateway_pid > 0
gateway_started = psutil.Process(gateway_pid).create_time()
latest_runtime_input = max(config_path.stat().st_mtime, plugin_path.stat().st_mtime, verifier_path.stat().st_mtime)
assert gateway_started + 1 >= latest_runtime_input, (
    f"gateway pid {gateway_pid} predates the claude-sc provider/config; restart required"
)

print("PATCH_VERIFY_RESULT claude-sc passed=13 skipped=0 failed=0 errors=0")
PY
