---
name: ai-coding-cli-internals
description: Use when diagnosing OpenAI Codex or Claude Code CLI behavior, including token economics, context limits, and known operational quirks.
---

# AI Coding CLI Internals & Diagnostics

Operational quirks and token-economics gotchas for OpenAI Codex and Claude Code.

## OpenAI Codex (GPT-5.5) Quirks

- **Context Window Split**: While GPT-5.5 has a 1M+ physical window, Codex caps it at 400K, forcibly split into ~272K input and ~128K output. The UI will show max available input as `258K` (with safety margins).
- **Rapid Token Consumption**: Hidden reasoning/CoT tokens consume input context rapidly.
- **Auto-Compaction Threshold**: Configured via `model_auto_compact_token_limit` in `~/.config/openai/codex/config.toml` (can be scoped under `[profiles.name]`), not within tool-specific CLI config.

## Claude Code Quirks

- **Token Drop/Cache Eviction**: If the token usage suddenly drops massively without a `/compact` command, it is due to Anthropic's 1-hour idle eviction strategy. It clears historical "Thinking" tokens to save cache-miss restoration costs.
- **UI Rendering**: `⏺ ...` is the Terminal Rendering System's indicator for streaming tool execution or hidden background reasoning. It is normal behavior, not a hang.
