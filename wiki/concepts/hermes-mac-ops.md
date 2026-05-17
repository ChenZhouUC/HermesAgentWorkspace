---
title: Hermes Agent macOS Operations
created: 2026-05-14
updated: 2026-05-14
type: concept
tags: [agent, macos, ops]
sources: [_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops.md]
confidence: high
---

# Hermes Agent macOS Operations

Deployment and operational manual for Hermes Agent on macOS.

## Configuration & Deployment

1. **Pre-requisites**: Requires GCP Service Account JSON (Vertex AI) with `aiplatform.endpoints.predict` permissions.
2. **Fallback Models**: Utilizes DashScope (Aliyun) API Keys for fallbacks.
3. **Integration**: Requires migration of memory and skills from OpenClaw, and integrates with Feishu Bot endpoints.[^1]] ]

---

**关联知识点 (Links):**

- [[agent-frameworks]]
- [[markdown-llm-protocol]]

---

[^1]: [[_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]
