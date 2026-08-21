---
name: agent-reconnaissance
description: Authorized security assessment of AI agents and sandboxes.
---

# Agent Reconnaissance & Reverse Engineering

This skill covers methodologies for investigating the underlying architecture, frameworks, and tools of AI agents — your own, those you're under contract to red-team, or CTF / research targets.

## When to Use

Use only for an owned agent, a written assessment engagement, or an explicit
CTF/research target whose rules permit the requested reconnaissance.

## ⚠️ Authorization Scope (READ FIRST)

Only use this skill against:

1. Agents you yourself built or operate.
2. Third-party services where you hold a written red-team / pen-test engagement covering reconnaissance.
3. CTF / research targets explicitly intended for analysis.

Probing a public commercial agent without authorization — even with "polite, educational" wording — can violate the provider's TOS and, depending on jurisdiction, anti-circumvention or computer-misuse statutes. Reverse-engineering packaged binaries can violate EULAs. Confirm authorization before invoking §1, §3, or §4 below.

See also the companion templates in [`references/prompt_templates.md`](references/prompt_templates.md).

## 1. Prompt Probing (Architecture & Schema Extraction)

Use transparent, authorization-scoped inquiries to document architecture and exposed integration surfaces:

- **Architecture inquiry:** Ask what framework, orchestration layer, MCP servers, or gateway components the agent uses.
- **Tool schema review:** Ask for available tool names, JSON schemas, permissions, and approval boundaries when that disclosure is in scope.
- **Prompt and policy review:** Request the system/developer instruction set only for owned systems, contracted audits, or CTF targets that explicitly allow prompt extraction.

## 2. Sandbox Introspection (Terminal Access)

When you have remote shell access to the agent's worker sandbox, perform white-box auditing:

- **Process Tree:** `ps auxf` identifies main entry points (Node, Python, Go) and sidecars (e.g., MCP servers, headless browsers like Playwright). Look for process separations indicating an "API Brain vs. Sandbox Worker" architecture.
- **Environment Variables:** Never dump the complete environment: it commonly
  contains API keys, tokens, and credentials. Enumerate variable names first
  (`tr '\0' '\n' < /proc/<PID>/environ | sed 's/=.*//'`) and inspect only an
  explicitly authorized, non-secret allowlist. Redact values in notes and user
  output; proxy presence can be recorded without revealing credentials.
- **Dependencies:** `pip list` or `npm list` / `package.json`. The presence of heavy orchestrators (`langchain`, `crewai`) vs. raw HTTP/Validation libs (`aiohttp`, `pydantic`) distinguishes wrapper frameworks from custom-built routing engines.

## 3. Packaged Binary Analysis (PyInstaller / Node pkg)

Modern enterprise agents often package Node.js or Python apps into standalone ELF binaries to protect IP and ensure portable execution.

- **Identifying Node.js Binaries:** Running `strings <binary> | head -n 50` will show C++ mangled names containing `v8`, `N4node`, `nghttp2`, `llhttp`.
- **Identifying Python Binaries:** `strings` will reveal libraries like `aiohttp`, `asyncio`, and standard Python module paths.
- **Extracting Business Logic:** Standard `strings | grep api` is too noisy due to underlying engine bindings. Use highly specific filters to pierce the engine noise:
  ```bash
  strings <binary> | grep -iE 'tool_name|description|mcp_server' | grep -v 'v8\|nghttp2\|llhttp'
  ```

## 4. Common Enterprise Architectural Patterns

- **Dual-Stage MCP Routing:** Custom enterprise agents avoid injecting 100+ tools into the system prompt to save tokens. They use a "discover -> execute" pattern (e.g., `discover_mcp_tools` then `execute_mcp_tool`) to lazily load schemas. The execute tool typically takes a string `tool_name` and an untyped `args` object — distinguishes custom middleware from standard OpenAI tool-calling arrays.
- **External State Machines (Kanban):** To prevent hallucination loops, advanced agents use external task trackers (e.g., `create_tasks`, `update_tasks`) with discrete status enums (`pending`, `completed`) rather than relying on the LLM's context window.
- **Skill Injectors (Frontmatter RAG):** References to loading `SKILL.md` via a `skill_ref` or `load_skill` tool indicate a dynamic RAG/frontmatter-parsing layer that injects domain knowledge into the prompt on demand — Anthropic Skills, Claude Code's plugin layer, and Hermes use this shape.
- **Separation of Brain and Body:** API keys and core prompt orchestration live in a secured cloud VPC, while the agent executes tools in a restricted, ephemeral GUI sandbox (e.g., Ubuntu X11 with Playwright and Jupyter Kernels).
