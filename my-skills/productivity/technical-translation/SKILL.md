---
name: technical-translation
description: "Use when translating Chinese technical work messages."
---

# Technical Translation

Translate Chinese technical or business messages into natural English for Slack, Teams, Feishu, email, tickets, and technical handoff notes.

## When to Use

Use this skill when the user asks“翻译”, “帮我翻译”, “英文怎么说”, or provides Chinese text intended for an English-speaking colleague/customer.

## Output Style

1. **Default to one polished recommendation first.** The user often wants copy-pasteable text, not a lecture.
2. Keep it **concise, direct, and work-chat friendly** unless the user asks for formal/email tone.
3. Preserve technical nouns that are already established in English: `Dewarp`, `Fisheye view`, `Quad`, `Q1-Q4`, `backend`, `outbound`, `stream`, `hub`, `Lab`.
4. Translate intent, not word-for-word Chinese structure. Prefer idiomatic engineering phrases:
   - “投屏/共享屏幕” → `share their screen` / `screenshare`, not `cast` unless literally casting to a TV.
   - “上去研究研究” → `hop on and poke around` for informal engineer chat; `access it to investigate` for formal tone.
   - “搞出来/拉出来” → `extracted` / `pulled from` depending on formality.
   - “兜底方案” → `fallback plan/solution`; “very 兜底” → `absolute fallback`, `ultimate fallback`, or `last resort`.
5. If a Chinese term has a technical ambiguity, include a **short note only when it changes the English term**. Example: “反编译码流”should usually be `reverse-engineer/decode the camera stream`; reserve `decompile` for binaries, firmware, APK/JAR/ELF, or executables.
6. Avoid over-explaining every phrase. If offering variants, keep to 2-3 labeled options: recommended, formal, casual.

## Camera / Video / Retail AI Terms

See [`references/camera-stream-phrasing.md`](references/camera-stream-phrasing.md) for reusable wording around fisheye cameras, dewarping, quad views, stream access, sample images, and customer technical coordination.

## Recommended Response Shape

For a simple translation:

```markdown
推荐：

> "..."
```

For tone variants:

```markdown
**推荐 / 工作群：**

> "..."

**更正式：**

> "..."
```

Only add vocabulary notes when they prevent a likely mistranslation.

## Pitfalls

- Do not always provide long explanations; the user's repeated translation tasks are usually meant for immediate copy-paste.
- Do not translate security/video terms literally if industry English has a standard term: use `dewarp`, `fisheye`, `panorama`, `quad-view`, `pull the stream`, `backend/admin interface`, `outbound connectivity`.
- Be careful with vendor spelling: “韩华/Hanhua”in video security is usually **Hanwha**.
