---
name: technical-investor-docs
description: Use when drafting investor-facing technical narratives.
---

# Technical Investor Documents

Use this skill when the user asks for investor-facing, board-facing, fundraise, due-diligence, or executive technical narrative materials: technology highlights, technical moat, Q&A prep, pitch support, “先进性”packaging, or product/algorithm capability summaries grounded in internal sources.

## Core principle

Do **not** dump every technical detail. Convert evidence into a small number of durable, investor-legible technology pillars.

Preferred shape:

1. 5–7 high-level technology pillars, not a 20+ item laundry list.
2. Each pillar should have:
   - concise concept summary;
   - what is technically advanced;
   - investor packaging / positioning sentence;
   - investor Q&A value;
   - what evidence supports it;
   - what still needs more source material.
3. Keep implementation evidence behind the narrative, not in front of it.

Do not default to Q&A format. For investor decks, roadshows, and demos, write a polished narrative with short presentation bullets. Use Q&A only when the user explicitly asks for diligence or objection handling.

Prioritize investor decision variables:

- deployment and operating cost;
- rollout speed and multi-site scalability;
- gross-margin or labor-efficiency impact;
- data/process moat and integration depth;
- credible technical differentiation without inflated claims.

Avoid “future expansion directions” in the main document. Replace them with current evidence, commercial impact, why-now logic, or explicit evidence gaps.

## Workflow

### 1. Gather sources before writing

Prioritize source material in this order:

1. User-provided Feishu docs / local files / repo paths.
2. The local wiki, especially `_living/` and active Layer 2 pages.
3. Existing product documents and reports.
4. Web search only if external market validation is explicitly needed.

When reading repositories, extract architecture and evidence, not raw code trivia. Look for data flow, model boundaries, geometry, event protocols, config systems, evaluation reports, and deployment constraints.

### 2. Separate evidence-backed claims from roadmap narrative

Mark or phrase claims according to evidence strength:

- **已验证 / existing capability**: supported by docs, reports, code, measurements, or production architecture.
- **产品路线 / packaging**: plausible framing based on existing components but not fully documented.
- **待补资料**: needs dedicated evidence before becoming a strong investor claim.

This is especially important for terms like “world model”, “agent”, “active vision”, or “digital twin”, where over-claiming hurts credibility.

### 3. Use the same Feishu document unless explicitly asked otherwise

If the user is iterating on a Feishu document, update/rebuild the **same document**. Do not create a second parallel doc for a rewrite or restructuring pass.

Use Feishu document rebuild/append scripts through the Feishu docs workflow. Preserve the version table and audit trail. If a new doc was mistakenly created, clean up the old/fallback copy only when the user asks or the intended canonical doc is clear.

### 4. Distill into technology pillars

For each proposed pillar, ask:

- What technical system or capability is this really about?
- Why would an investor care?
- Is this a current capability, an integration opportunity, or a roadmap narrative?
- What source supports the claim?
- Can it be explained in plain business language without losing technical depth?

Avoid vague claims like “AI-powered” or “advanced algorithm”. Prefer concrete system language: identity continuity, spatial state model, edge/cloud event protocol, automated geometric configuration, active visual sensing, model lifecycle, weak-network robustness.

### 5. Write for technical management + investors

Tone: professional, concise, high-level, but not fluffy.

Use strong but defensible wording:

- “身份连续性引擎”instead of merely“ReID model”.
- “空间状态模型”or“垂直空间世界模型”instead of over-claiming a general-purpose world model.
- “算法化交付”instead of ordinary“configuration”.
- “主动观察”for AI PTZ / active camera control.

Avoid academic formulas and excessive implementation names in the main text. Put details in evidence notes or follow-up expansion sections.

## Recommended section template

For each technology pillar:

```markdown
## NN. <技术亮点>: <投资人可理解的一句话>

### 概括

<2–4 sentences explaining what it is and why it matters.>

### 技术亮点

<Short paragraphs, not deeply nested bullet lists.>

### 投资人包装

> <1–2 polished sentences suitable for pitch/Q&A.>

### 投资人问答价值

<How to answer likely diligence questions.>

### 证据边界

<What is verified, what is positioning, and what evidence is still missing.>
```

## Feishu formatting guardrails

- Avoid nested bold inside bullet list items; Feishu can reject it during rebuild.
- Prefer short paragraphs and blockquotes over deeply nested lists.
- Do not include a manual Markdown version table; Feishu scripts handle it.
- If a doc URL already exists, rebuild/append that doc rather than creating a new one.

## SpaceSight investor narrative pattern

When the topic is SpaceSight technical moat, a good first-pass pillar set is:

1. 边缘 / 云端 ReID — identity continuity across cameras and regions.
2. 鱼眼与空间重建 — lower-cost spatial coverage via dewarp/multi-view reconstruction.
3. 空间世界模型 — vertical world model for commercial spaces; state, identity, region, event, metric.
4. AI 摇头机 / PTZ — active visual sensing; only expand when source material exists.
5. VLM / SpaceSight Claw — natural-language querying of site facts; only expand when source material exists.
6. 自动化配置与算法化交付 — SAM/geometric/model-assisted configuration that turns demos into scalable deployment.
