---
name: educational-doc-writing
description: "Use when writing explanatory teaching notes, Feishu docs, reading guides, or structured reinterpretations from the user's abstract math/technical/AI/systems confusion. Trigger for requests like“帮我写个文档教育我一下”, “重新解读这一章”, “我感觉有循环/边界不清”, “把上面的讨论融入文档”, or when the user needs object/meta-layer separation, proof-scope clarification, hidden assumptions, or tightened analogies."
---

# Educational Document Writing

Use this skill when the user asks for a written explanation, teaching note, reading guide, or Feishu document that clarifies conceptual confusion rather than simply summarizing source material.

## Core principle

Do **not** write a generic encyclopedia summary. Convert the user's actual confusion into the document's organizing problem, then teach by separating layers, assumptions, and scope.

The desired output is usually:

1. A concise diagnosis of the user's confusion.
2. A layer-by-layer conceptual model.
3. A table separating related concepts that the user is blending.
4. A direct statement of what the argument proves and does not prove.
5. A short, memorable formulation the user can reuse.

## Workflow

1. **Extract the user's live questions.** Quote or paraphrase them near the top. Treat them as the document thesis.
   - Example: “我是不是在用一些东西证明另一些东西？”
   - Example: “这是不是逻辑循环？”
   - Distinguish what the user is not questioning from what they are questioning.
2. **Identify the object layer and the meta layer.** Name what is being studied and what is doing the studying.
   - For formal systems: object layer = symbols/formulas/axioms/proofs; meta layer = logic used to reason about those objects.
   - For knowledge systems: data/instances, schema/ontology/rules, and meta-theory/validation/reasoning layers.
   - Call out when the same-looking word appears at different layers, such as object-level `->` versus meta-level “if...then...”.
3. **Separate definition, audit, inference, and proof.** Users often conflate them.
   - Definition/schema: what objects and relations are allowed.
   - Audit/validation: whether concrete instances obey constraints.
   - Rule-internal inference: deriving new facts inside the system.
   - Meta-proof: proving global properties of the rule system itself.
4. **List hidden assumptions explicitly.** For abstract proof discussions, call out finite strings, recursive definitions, truth values, quantification, induction, contradiction/negation reasoning, and semantic interpretation where relevant.
5. **State the proof target narrowly.** Say what is actually proven and what is not.
   - Example: consistency means the system will not derive contradictions; it does not prove the system is uniquely rational, scientifically true, or applicable to reality.
6. **Use the user's own analogy, but tighten boundaries.** When the user offers a KG/schema analogy, validate it, then add the missing distinction: ontology/schema may include logic, but meta-theory studies the rule system itself.
7. **Iteratively update the same document.** If the user continues refining the idea, blend the new insight into the existing doc as a new logical section instead of creating a new doc.
8. **Do not declare “no circularity” too quickly.** First acknowledge that every proof uses background reasoning, then explain why that is different from same-level self-certification.

## Document structure template

```markdown
# <Title>

## 0. The question this note answers

<Restate the user's confusion in plain language.>

## 1. What the source text is trying to prove

<Define the narrow target.>

## 2. Layer separation

| Layer        | Contains | What it can do |
| ------------ | -------- | -------------- |
| Object layer | ...      | ...            |
| Meta layer   | ...      | ...            |

## 3. Hidden assumptions / resources used

<Explicit list of background concepts and inference tools.>

## 4. Why this is or is not circular

<Explain level-crossing versus same-level circularity.>

## 5. What is proven, and what is not proven

| Claim | Proven here? | Notes |
| ----- | ------------ | ----- |

## 6. Better analogy

<Use the user's analogy, then clarify its limits.>

## 7. One-sentence takeaway

<A memorable formulation.>
```

For long iterative conversations, add new logical sections instead of compressing everything into one dense essay.

## Feishu-specific execution

If the target is a Feishu doc, also load `feishu-docs` and follow its rules. In particular:

- Prefer updating/rebuilding the same doc token when the user asks to“融入进去文档”.
- Write the markdown to a real file under `~/.hermes/tmp/` first.
- Use the Feishu markdown import/rebuild scripts rather than manual block construction.
- Avoid Feishu-problematic Markdown such as nested bold inside list items when possible.

## Tone for 琛哥

Use concise but intellectually serious Chinese. It is fine to say“你这个困惑非常关键/已经很接近核心”, but keep the explanation rigorous. Prefer crisp contrasts:

- “不是 A，而是 B”
- “关键不是有没有 X，而是 X 发生在哪一层”
- “它证明的是不会自爆，不是宇宙真理”

## Pitfalls

- Do not over-answer with general history if the user's pain point is conceptual structure.
- Do not collapse “consistency”, “soundness”, “completeness”, “applicability”, and “rationality” into one vague notion of “correctness”.
- Do not treat analogies as exact equivalences; explicitly state where the analogy breaks.
- Do not create multiple Feishu docs during an iterative explanation unless the user explicitly asks for a new one.
