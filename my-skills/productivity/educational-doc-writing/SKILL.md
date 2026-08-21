---
name: educational-doc-writing
description: Write rigorous teaching notes for abstract technical topics.
---

# Educational Document Writing

Turn the user's live confusion into the organizing problem of a teaching document. Rebuild the concept from its foundations instead of producing a generic source summary.

## When to Use

Use for rigorous teaching notes or reading guides where the user needs layers,
assumptions, proof scope, circularity, or analogy limits made explicit.

## Core Rules

- Separate object and meta layers before drawing conclusions.
- State the target property narrowly, list its assumptions, and say what remains unproved.
- Treat every proof as relative to accepted background reasoning; never claim an assumption-free or absolute proof.
- Distinguish neighboring concepts instead of hiding them under words such as “correct” or “valid”.
- Use analogies only after the formal structure is clear, and mark where each analogy stops working.

## Procedure

1. **Extract the live question.** Quote or paraphrase the exact tension near the top instead of summarizing the whole source.
   - Examples: “我是不是在用一些东西证明另一些东西？” “这是不是逻辑循环？” “这个论证究竟证明了什么？”
   - Separate what the user accepts from what they are challenging.
   - Complete this step when the document has a one-sentence problem statement.

2. **Build the layer model.** Name what is being studied and what is doing the studying.
   - Use the distinctions that fit the domain: object/meta, system/observer, syntax/semantics, rules/reasoning about rules, or data/schema/meta-schema.
   - For formal systems, distinguish object-level symbols and proofs from meta-level claims about them.
   - For knowledge systems, distinguish instances, schema or ontology, rule-internal inference, validation, and meta-theory.
   - Complete this step when every important claim can be assigned to a layer.

3. **Separate operations and target properties.** Do not let adjacent ideas collapse into one another.
   - Definition/schema: what objects and relations are allowed.
   - Audit/validation: whether concrete instances obey constraints.
   - Rule-internal inference: deriving new facts inside the system.
   - Meta-proof: proving global properties of the rule system itself.
   - Compare consistency, soundness or reliability, completeness, applicability, uniqueness, usefulness, safety, and rationality when they are in play.
   - Complete this step when vague uses of“正确”have been replaced with testable properties.

4. **Surface the accepted foundations.** List the background resources actually used: finite strings, proof sequences, recursive definitions, induction, truth values, quantification, model semantics, meta-logic, validators, reasoners, or invariants.
   - Explain “more basic” in the relevant sense: epistemically more acceptable, ontologically lighter, proof-theoretically weaker or more transparent, or operationally more inspectable.
   - Name a source category, school, or representative tradition only when it helps the reader orient the claim.
   - Complete this step when no hidden premise carries a major conclusion silently.

5. **Audit proof scope and circularity.** Define what would count as a vicious circle before deciding whether one exists.
   - Distinguish same-level self-certification from a meta-level audit of an object system.
   - State the accepted background theory and explain that the conclusion is relative to it.
   - Say what the argument proves and what it does not prove. For example, consistency does not establish unique rationality, scientific truth, or real-world applicability.
   - Complete this step with an explicit “proven / not proven / assumed” boundary.

6. **Map the argument and alternatives.** Show the shortest logical skeleton from assumptions to conclusion.
   - When a semantic route is used, mention relevant syntactic or proof-theoretic alternatives such as invariants, normalization, cut elimination, canonical models, or direct model construction.
   - State whether an alternative is a special-case technique or a general proof method.
   - Complete this step when the reader can see which link would fail if an assumption changed.

7. **Tighten analogies.** Start from the user's analogy when possible, map each component, then name the mismatch.
   - Useful families include program invariants, proof checkers, model checkers, and schema/ontology plus validator/reasoner/auditor.
   - Never present an analogy as evidence for the formal conclusion.
   - Complete this step when the analogy has an explicit failure boundary.

8. **Revise the artifact deliberately.** Keep one document as the source of truth.
   - During ordinary iterative refinement, integrate the new insight into the existing logical structure.
   - When the user asks for a full rethink or rewrite, or the document has accumulated contradictory appendices, rebuild it atomically from the foundations instead of appending another section.
   - Complete this step when the final document reads as one argument rather than a conversation log.

## Document Structure

```markdown
# <Title>

## 0. What this document answers

<Restate the user's confusion in plain language.>

## 1. Layer model

<Separate object, meta, syntax, semantics, system, and observer as needed.>

## 2. What is being proven and not proven

<Define the narrow target and adjacent properties.>

## 3. Hidden assumptions / resources used

<Explicit list of background concepts and inference tools.>

## 4. Proof map

<Show the logical route from assumptions to conclusion.>

## 5. Why this is or is not circular

<Explain level-crossing versus same-level circularity.>

## 6. Alternative routes and analogy limits

<Offer relevant alternatives and mark where analogies stop.>

## 7. Compressed takeaway

<Give the reader a reusable one- or two-sentence formulation.>
```

## Feishu Execution

Load `feishu-docs` for document mechanics. Preserve these content-level rules:

- Keep the same document token unless the user explicitly requests a new document.
- Write the markdown to a real file under `~/.hermes/tmp/` first.
- Use the Feishu markdown import/rebuild scripts rather than manual block construction.
- Rebuild atomically when the user requests a full rethink; preserve version history and read the result back.
- Avoid Feishu-problematic Markdown such as nested bold inside list items when possible.

## Tone

Use concise but intellectually serious Chinese for 琛哥 unless he asks otherwise. Prefer crisp contrasts:

- “不是 A，而是 B”
- “关键不是有没有 X，而是 X 发生在哪一层”
- “它证明的是不会自爆，不是宇宙真理”

## Pitfalls

- Do not over-answer with general history if the user's pain point is conceptual structure.
- Do not say syntax “has semantics”; say the meta-theory assigns an interpretation.
- Do not describe a proof as absolute without naming the remaining assumptions.
- Do not collapse consistency, soundness, completeness, applicability, uniqueness, usefulness, safety, and rationality into “correctness”.
- Do not treat semantic consistency proofs as the only route when a proof-theoretic route is relevant.
- Do not treat analogies as exact equivalences; explicitly state where the analogy breaks.
- Do not create multiple Feishu docs during an iterative explanation unless the user explicitly asks for a new one.

## Verification

Before delivering the document, verify that:

- The user's live question appears near the beginning.
- Every central claim belongs to a named layer.
- Hidden assumptions and the accepted background are explicit.
- The proof target is separated from neighboring properties.
- The document states what is proven, not proven, and assumed.
- Circularity is analyzed as same-level self-certification versus meta-level audit.
- Alternative proof routes are labeled as special-case or general where relevant.
- Every analogy has a stated failure boundary.
- Every linked reference exists and every external factual claim that needs sourcing is supported.
- A Feishu rebuild preserves the intended document token and passes read-back verification.
