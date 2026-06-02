---
name: qwen-code
description: "Delegate coding to Qwen Code CLI (Alibaba's official agentic coding CLI for Qwen3-Coder/Qwen3.7-Max)."
category: autonomous-ai-agents
---

# Qwen Code CLI

Use `qwen-code` as an autonomous coding worker. It is Alibaba's official open-source agentic coding CLI (forked and heavily optimized from Gemini CLI), designed specifically for Qwen3-Coder and Qwen 3.7 Max, capable of multi-file codebase comprehension, editing, and automation.

## Installation

The user explicitly prefers official/manufacturer-provided tools and prefers Homebrew over npm when available.

- **Homebrew** (macOS/Linux): `brew install qwen-code`
- **npm** (Cross-platform): `npm install -g @qwen-code/qwen-code@latest`

## Configuration & Authentication

It works seamlessly with DashScope (Alibaba Cloud) or OpenAI-compatible APIs. Unlike other CLIs, it also supports OAuth login natively.

To use via DashScope compatibility mode (using an API key):

```bash
export OPENAI_API_KEY="<your_dashscope_key>"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export QWEN_MODEL="qwen3.7-max"
```

## Usage

To start the interactive CLI in the terminal:

```bash
terminal(command="qwen-code", workdir="~/project", pty=true)
```

_(Requires `pty=true` for interactive terminal UI)_

## VS Code Integration

For IDE integration, the user prefers the official manufacturer-tuned extension:

- **通义灵码 (TONGYI Lingma)**: The official VS Code extension by Alibaba (v2.5.0+). It natively supports Qwen3-Coder Agentic Coding, MCP (Model Context Protocol), and long-context workspaces without needing manual API key management (relies on Aliyun account login).
