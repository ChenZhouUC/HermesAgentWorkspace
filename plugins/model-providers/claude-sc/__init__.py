"""Claude SC provider using the same endpoint and token as ``~/bin/claude-sc``.

The SC gateway expects Anthropic Messages requests with Bearer auth and the
Claude Code client identity.  A user-level provider plugin keeps that routing
policy outside the upstream Hermes checkout while preserving Hermes' own agent
loop, tools, fallback handling, and session state.
"""

from __future__ import annotations

import platform
import subprocess
import uuid
from pathlib import Path
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


_DEFAULT_BASE_URL = "https://socheap.ai"
_DEFAULT_MODEL = "claude-fable-5-1"
_ANTHROPIC_SDK_VERSION = "0.112.1"


def _secret(name: str) -> str:
    from agent.secret_scope import get_secret

    return str(get_secret(name) or "").strip()


def _node_version() -> str:
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=2, check=False)
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            return value
    except Exception:
        pass
    return "v22.0.0"


def _stainless_os() -> str:
    return {
        "Darwin": "MacOS",
        "Linux": "Linux",
        "Windows": "Windows",
    }.get(platform.system(), "Unknown")


def _stainless_arch() -> str:
    machine = platform.machine().lower()
    return {
        "aarch64": "arm64",
        "arm64": "arm64",
        "amd64": "x64",
        "x86_64": "x64",
        "i386": "x32",
        "i686": "x32",
    }.get(machine, f"other:{machine}" if machine else "unknown")


class ClaudeSCProfile(ProviderProfile):
    """SC's Claude Code-compatible Anthropic Messages endpoint."""

    def prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep Anthropic prompt-cache markers on the SC route."""
        from agent.prompt_caching import apply_anthropic_cache_control

        return apply_anthropic_cache_control(messages, cache_ttl="5m", native_anthropic=True)

    def build_api_kwargs_extras(
        self, *, reasoning_config: dict[str, Any] | None = None, **_: Any
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Pass Hermes reasoning settings to the Anthropic compatibility adapter."""
        top_level = {"_reasoning_config": reasoning_config} if reasoning_config else {}
        return {}, top_level

    def create_client(self, **client_kwargs: Any) -> Any:
        import anthropic
        import httpx

        from agent.anthropic_adapter import (
            _COMMON_BETAS,
            _OAUTH_ONLY_BETAS,
            _beta_header,
            _client_timeout,
            _get_claude_code_version,
        )
        from agent.auxiliary_client import AnthropicAuxiliaryClient
        from utils import normalize_proxy_env_vars

        token = _secret("CLAUDE_SC_AUTH_TOKEN") or _secret("ANTHROPIC_AUTH_TOKEN")
        base_url = (
            _secret("CLAUDE_SC_BASE_URL") or str(client_kwargs.get("base_url") or "").strip() or _DEFAULT_BASE_URL
        ).rstrip("/")
        if not token:
            raise RuntimeError("CLAUDE_SC_AUTH_TOKEN is required in ~/.hermes/.env for the claude-sc provider")

        session_id = str(uuid.uuid4())
        claude_version = _get_claude_code_version()
        node_version = _node_version()

        def apply_claude_code_headers(request: httpx.Request) -> None:
            # The Python SDK adds its own x-stainless identity.  SC intentionally
            # admits Claude Code clients only, so replace that identity with the
            # headers emitted by the installed Claude Code CLI and force Bearer
            # auth exactly as ~/bin/claude-sc does.
            for name in tuple(request.headers):
                lowered = name.lower()
                if lowered in {
                    "authorization",
                    "x-api-key",
                    "user-agent",
                    "x-app",
                    "x-claude-code-session-id",
                } or lowered.startswith("x-stainless-"):
                    request.headers.pop(name, None)
            request.headers["Authorization"] = f"Bearer {token}"
            request.headers["User-Agent"] = f"claude-cli/{claude_version} (external, cli)"
            request.headers["x-app"] = "cli"
            request.headers["x-claude-code-session-id"] = session_id
            request.headers["x-stainless-lang"] = "js"
            request.headers["x-stainless-package-version"] = _ANTHROPIC_SDK_VERSION
            request.headers["x-stainless-os"] = _stainless_os()
            request.headers["x-stainless-arch"] = _stainless_arch()
            request.headers["x-stainless-runtime"] = "node"
            request.headers["x-stainless-runtime-version"] = node_version
            request.headers["x-stainless-retry-count"] = "0"
            request.headers["x-stainless-timeout"] = "600"

        normalize_proxy_env_vars()
        timeout = _client_timeout(client_kwargs.get("timeout"))
        http_client = httpx.Client(timeout=timeout, event_hooks={"request": [apply_claude_code_headers]})
        headers = _beta_header([*_COMMON_BETAS, *_OAUTH_ONLY_BETAS])
        real_client = anthropic.Anthropic(
            auth_token="claude-sc-bearer-via-http-hook",
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
            default_headers=headers,
            http_client=http_client,
        )
        client = AnthropicAuxiliaryClient(
            real_client,
            _DEFAULT_MODEL,
            token,
            base_url,
            is_oauth=True,
        )
        client.HERMES_SKIP_TRANSPORT_WRAP = True
        client.HERMES_SKIP_ASYNC_WRAP = True
        return client

    def fetch_models(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ) -> list[str] | None:
        return [_DEFAULT_MODEL]


register_provider(
    ClaudeSCProfile(
        name="claude-sc",
        aliases=("sc-claude",),
        api_mode="chat_completions",
        display_name="SC Anthropic",
        description="Claude Code-compatible SC endpoint",
        env_vars=("CLAUDE_SC_AUTH_TOKEN", "CLAUDE_SC_BASE_URL"),
        base_url=_DEFAULT_BASE_URL,
        auth_type="external_process",
        supports_health_check=False,
        supports_vision=True,
        process_command=str(Path.home() / "bin" / "claude-sc"),
        fallback_models=(_DEFAULT_MODEL,),
        default_aux_model=_DEFAULT_MODEL,
    )
)
