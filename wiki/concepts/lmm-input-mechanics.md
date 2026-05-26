---
title: LMM Input Mechanics
created: 2026-05-15
updated: 2026-05-15
type: concept
tags: [vlm, architecture, agent]
sources: [_living/AI-Infrastructure/LMM-Input-Mechanics.md]
confidence: high
---

# LMM Input Mechanics

The mechanism by which Large Multimodal Models (LMMs) process user inputs (like Markdown with embedded media) into underlying mathematical tokens.

## Architecture Evolution

- **Pipeline Architecture**: Converts media to text via intermediate models (OCR, VQA, ASR) before sending to the LLM. Causes information loss.
- **Native End-to-End (E2E)**: Models like GPT-4o and Gemini 1.5 Pro use dedicated encoders to map raw media directly to high-dimensional tokens. ^[[[_living/AI-Infrastructure/LMM-Input-Mechanics|LMM-Input-Mechanics]]]

## Modality to Token Mapping

All modalities are reduced to a homogeneous token sequence:

- **Image -> Visual Tokens**: Patching -> Vision Encoder -> Visual Tokens.
- **Audio -> Audio Tokens**: Waveform -> Spectrogram -> Audio Encoder -> Audio Tokens.
- **Video -> Spatiotemporal Tokens**: Frame Extraction + Audio Track -> Spatial & Audio Tokens + Timestamp Embeddings. ^[[[_living/AI-Infrastructure/LMM-Input-Mechanics|LMM-Input-Mechanics]]]

## Markdown sequence and Attention

Transformer models consume tokens linearly. The physical layout in Markdown dictates the token sequence. Placing text adjacent to `![image]()` markers ensures Text Tokens and Visual Tokens are contiguous, maximizing Self-Attention correlation and reducing hallucinations. ^[[[_living/AI-Infrastructure/LMM-Input-Mechanics|LMM-Input-Mechanics]]]

## Agent API Translation

LMM APIs do not parse Markdown UI sugar natively. Agents must:

1. Parse the AST to identify media links.
2. Extract and upload files to get system URIs.
3. Construct a standard JSON Payload (Multi-part Array) preserving the chronological interleave of text and media. ^[[[_living/AI-Infrastructure/LMM-Input-Mechanics|LMM-Input-Mechanics]]]

**Related:**

- [[markdown-llm-protocol]]
