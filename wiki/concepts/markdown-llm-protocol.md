---
title: Markdown as LLM Protocol
created: 2026-05-14
updated: 2026-05-14
type: concept
tags: [architecture, llm]
sources: [_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md]
confidence: high
---

# Markdown as LLM Protocol

Markdown is increasingly becoming the preferred format for LLM interactions, replacing heavier rich text formats.

## Core Drivers

1. **High Token Efficiency**: It expresses structures (`#`, `-`, `*`) with minimal characters compared to HTML or XML, saving tokens and allowing more effective information in context windows.
2. **Clear Semantic Boundaries**: The markers map well to LLM attention, making parsing structural context easier.[^1]] ]

**Related:**

- [[llm-benchmark-methodology]]
- [[lmm-input-mechanics]]
- [[advanced-markdown-syntax]]

---

[^1]: [[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]
