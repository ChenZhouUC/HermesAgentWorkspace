---
name: github-copilot-cli
description: "Use when operating or debugging GitHub Copilot CLI (gh copilot), including commands, geo/data-residency config, compaction, and model/context quirks."
---

# GitHub Copilot CLI (gh copilot)

This skill covers non-obvious operational realities, environmental configurations, and model limitations of the GitHub Copilot CLI.

## 1. Context Window & Compaction

- **Interactive Session (`/compact`)**: Manually summarizes the conversation history to free up context window tokens. You can provide focus instructions (e.g., `/compact focus on database schema, ignore UI`).
  _Note: There is no global setting to auto-trigger compaction based on a threshold; it must be invoked manually when the status line warns of high usage._
- **Paste Compaction (`compactPaste`)**: To visually compress large pasted text blocks into a single line like `[Paste #N - X lines]`, ensure `"compactPaste": true` in `~/.copilot/config.json` (enabled by default). This only affects display, not underlying token usage.

## 2. Model Quirks: GPT-5.5 Context Limitations

- **The 258k Input Limit**: While GPT-5.5 natively supports a 1M token context, Copilot CLI currently caps the total window at 400k for subscription users. This is hard-split into ~272k for input and 128k for output. Due to safety margins, the CLI typically reports a **258,400 (258k)** maximum input context.
- **Rapid Token Consumption**: Next-generation models (like GPT-5.5) generate hidden reasoning (CoT) tokens during their planning phases. These rapidly consume the 258k input window, often leading to unexpected context exhaustion during long sessions.
- **Threshold Overrides (BYOK only)**: Token thresholds cannot be changed for standard catalog models. In Bring-Your-Own-Key mode, use `COPILOT_PROVIDER_MAX_PROMPT_TOKENS` and `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS` environment variables to override defaults.

## 3. Experimental Features

- **Rubber Duck Agent (Cross-Model Review)**: An experimental feature where Copilot dispatches a critic agent from a _different_ AI family to review the primary model's output (e.g., Claude evaluates GPT, or GPT-5.5 evaluates Claude). This mitigates single-model blind spots.
- **Usage**: Requires interactive mode (`gh copilot`) with `/experimental on` toggled.

## 4. Geo & Data Residency Environment Variables

- **Geo Configuration**: Refers to enterprise data residency constraints (e.g., EU Geo). It dictates where telemetry and prompts are processed to ensure compliance.
- **Implementation**: Controlled via environment variables `GH_HOST` or `COPILOT_GH_HOST` (e.g., pointing to an internal `mycompany.ghe.com` instead of the public `github.com`).

## 5. Key References

- **Help Commands**:
  - `gh copilot help config` (JSON settings like `mouse`, `theme`, `compactPaste`)
  - `gh copilot help commands` (Interactive slash commands)
  - `gh copilot help environment` (Env variables like `COPILOT_ALLOW_ALL`, `COPILOT_OFFLINE`)
