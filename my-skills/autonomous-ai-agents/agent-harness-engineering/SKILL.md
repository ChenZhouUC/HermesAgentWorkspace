---
name: agent-harness-engineering
description: "Architectural patterns and SOTA frameworks for AI Agent Harnesses (Orchestration, Sandboxing, MCP/LSP, Human-in-the-loop)."
category: autonomous-ai-agents
---

# Agent Harness Engineering

A harness is the infrastructure layer surrounding an LLM that enables it to function as an autonomous Agent. It manages state, context, tool sandboxing, and execution flow.

## Key Paradigms

1. **Orchestration / State Machines**: E.g., **LangGraph**. Models agent loops as Directed Acyclic Graphs (DAGs). Excellent for complex, deterministic multi-agent workflows and checkpointing (pausing/resuming state).
2. **Terminal / Protocol-Heavy**: E.g., **Claude Code**, **Copilot CLI**. Heavily relies on **MCP (Model Context Protocol)** for decoupling tools and context, and **LSP (Language Server Protocol)** for providing the agent with exact "code vision" (go-to-definition, symbol resolution).
3. **Event-Driven / Heterogeneous**: E.g., **OpenClaw**, **Hermes**. Distributes execution across local machines, cloud brains, and IM apps for Human-in-the-loop (HITL) authorization.

## Audit Gates & HITL (Human-in-the-Loop)

Modern harnesses do not use linear "Stage 1 -> Gate -> Stage 2" CI/CD pipelines. They use **Action-based Interception** or **State-Machine Checkpoints**:

- **Tool-Level Interception**: The most efficient pattern. The harness suspends execution _only_ when the agent attempts a state-mutating or sensitive tool call (e.g., `execute_code`, `drop_table`).
- **Graph Checkpointing**: The graph engine (like LangGraph) is hardcoded to pause before specific nodes (`interrupt_before=["audit_node"]`), serializing state to a DB until external approval is received.

## Reference Materials

For a deep dive into SOTA harness implementations (LangGraph vs AutoGen vs Claude Code vs OpenClaw vs Copilot), see `references/sota-harness-architecture.md`.
