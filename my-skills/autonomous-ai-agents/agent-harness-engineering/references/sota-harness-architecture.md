# SOTA AI Agent Harness Architecture & Engineering (2026)

This document captures architectural patterns for Agent Harness Engineering, focusing on how modern AI agents are orchestrated in production environments. It moves beyond naive CI/CD pipeline mindsets (Stages + Audit Gates) into event-driven and state-graph paradigms.

## 1. The Autonomous Loop (ReAct) & The Halting Problem

Modern agents do not run on linear stages; they run in an autonomous loop (ReAct: Reason -> Act -> Observe). The harness feeds the LLM the prompt and available tools, the LLM outputs a tool call (e.g., JSON), the harness suspends the LLM, executes the tool in a sandbox, and feeds the output (stderr/stdout) back as a `tool_response` for the next tick.

**Who decides when the task is done?**

1. **AI Autonomous Decision (Submit Tool)**: The LLM calls a `submit_task` tool when it subjectively believes the task is done. (Flaw: LLM overconfidence/hallucination).
2. **Test-Driven Termination (TDD)**: The harness runs unit tests, linters, or compilation. If it fails, the harness intercepts the exit, rejects the submission, and injects the stderr back into the loop to force the LLM to fix it.
3. **LLM-as-a-Judge (Critic)**: A secondary Reviewer agent grades the Worker agent's output before the harness accepts it.

**Preventing Infinite Loops**:
Harnesses maintain a rolling hash of recent tool calls. If the agent repeats the exact same tool name and arguments N times, the harness intercepts the execution and injects a system prompt: "System Warning: You are repeating the same action. Stop and try a new approach."

## 2. Audit Gates & Human-in-the-Loop (HITL) Patterns

Determining _when_ to trigger an audit gate is not about stage completion, but about state and side effects.

1. **Graph Routing Breakpoints (e.g., LangGraph)**: The harness compiles a DAG (`StateGraph`). It uses `interrupt_before=["audit_node"]`. When the state router hits this node, it serializes the entire state to a DB (e.g., PostgresSaver), suspends the thread, and waits for a `resume` API call. (Heavy, rigorous).
2. **Tool-Level Aspect Interception (e.g., Hermes, Claude Code)**: The harness listens strictly to tool dispatch. If the LLM attempts to use a sensitive tool (e.g., `execute_code`, `git push`), the middleware intercepts it and prompts the human via CLI `[Y/n]` or an asynchronous IM card (e.g., OpenClaw via Slack/Telegram). (Efficient, side-effect focused).
3. **Physical Acceptance State (e.g., Copilot, Codex)**: The agent has zero autonomous execution rights. Its output is rendered as Ghost Text or a diff, and the only gate is the human pressing `Tab` or `Apply`.

## 3. Communication Protocols

- **MCP (Model Context Protocol)**: Decouples the agent from local tools. The harness is lightweight; tools are provided by external MCP servers, handling auth and execution securely.
- **LSP (Language Server Protocol) / ACP (Agent Context Protocol)**: Gives the agent "code vision" (go-to-definition, references) without requiring it to blindly `grep` or `cat` files.
