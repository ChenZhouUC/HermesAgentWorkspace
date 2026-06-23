---
name: bilingual-dictionary-cataloging
description: Use when generating bilingual dictionary catalog metadata, English descriptions, or bilingual introductions that must follow strict layout and style constraints.
---

# Bilingual Dictionary Cataloging

The user builds bilingual metadata catalogs for dictionaries. When asked to generate an "English description" or a "bilingual introduction" for a dictionary, you **must strictly adhere to the following layout and formatting constraints**.

## Core Constraints

1. **Single Paragraph Rule for English**: The `English Description` must be a **single, highly-condensed paragraph**. Do NOT break it into multiple paragraphs. Do NOT use bullet points in the English section. It should capture key features, target audience, and highlights smoothly without any line breaks.
2. **Specific Chinese Bullet Structure**: The `中文简介` must follow a specific bulleted structure using markdown lists and bold text.

## Required Layout Template

```markdown
**English Description:**
The [Dictionary Name] ([Edition]) is a [highly-condensed, single-paragraph overview describing its core philosophy, target audience, major features like defining vocabulary or corpus usage, and why it is historically or practically significant].

**中文简介 (核心特点):**

- **适用对象**：[Target audience, e.g., 中高级英语学习者、大中学生等]
- **核心特色（[Brief Highlight]）**：
  - **[Feature 1]**：[Description]
  - **[Feature 2]**：[Description]
- **[Edition Info] 重大升级与特色**：
  - **[Update 1]**：[Description]
  - **[Update 2]**：[Description]
```

## Examples of Preferred Style

- **Conciseness**: The user prefers "EXTREME conciseness, rigour, bullet lists, 100% completion". Do not add filler conversational text before or after the catalog block. Just output the requested block.
- **English Example**: "The Longman Dictionary of Contemporary English (4th Edition) is a highly revered reference tool globally celebrated for its unparalleled accessibility and focus on active language production. Regarded by many as the pinnacle of the series for retaining the most exhaustive and uncut corpus of authentic examples, its most defining feature is the strict use of the Longman Defining Vocabulary..." (No paragraph breaks).

## Context / Naming Quirks

- Publishing Abbreviations: `9th ed.` is the standard publishing abbreviation. `9ed` or `9E` is informal/commercial but commonly used in digital dictionary circles (like FreeMdict).
- Always include specific edition quirks if known (e.g., LDOCE4's uncut corpus, CCALD9's 2017 online data leak).
