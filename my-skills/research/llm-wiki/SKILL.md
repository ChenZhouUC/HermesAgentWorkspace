---
name: llm-wiki
description: Maintain, query, and audit the local schema-governed wiki.
---

# Local LLM Wiki

Maintain the user's long-lived Markdown knowledge base without weakening its
schema, provenance, graph, or audit-history guarantees. The current
`wiki/SCHEMA.md` is the single authority for structure and policy; this skill
defines the operating workflow and must not override a newer schema rule.

## When to Use

Use this skill when the user asks to:

- query or synthesize knowledge from the local Wiki;
- ingest a public source or a private living document;
- create, update, rename, split, merge, archive, or delete Wiki nodes;
- audit or repair Wiki structure, provenance, links, index entries, logs, or
  Obsidian carrier configuration;
- initialize a new schema-governed Markdown Wiki.

For mining session history or converting source material into reusable nodes,
also load `wiki-content-extraction`. For extracting a Feishu document, first use
`feishu-docs`, then apply this skill's source-routing and Layer 2 rules.

## Wiki Location and Access

Resolve the Wiki root in this order:

1. Explicitly configured `WIKI_PATH`.
2. The active `HERMES_HOME/wiki`.
3. `~/.hermes/wiki` for the standard profile.

Pass resolved paths directly to file tools. Never pass a literal shell variable
such as `$WIKI_PATH` to `read_file` or `search_files`.

### Feishu group boundary

In a sandboxed Feishu group, the Wiki is read-only:

- Use `read_file` and `search_files` with an explicit path under
  `~/.hermes/wiki`.
- Do not use `terminal`, omit `search_files.path`, or probe other local paths.
- Do not attempt Wiki writes, schema changes, lint fixes, or Obsidian
  maintenance from the group. Explain that mutation must continue in an
  owner/private or CLI session.
- Do not reveal host paths, private source details, local operational metadata,
  or unrelated Wiki content in group-visible output.

## Mandatory Orientation

Before any Wiki operation:

1. Read `wiki/SCHEMA.md` completely.
2. Read `wiki/index.md` completely.
3. Read the most recent complete daily entry in `wiki/log.md`.
4. Search the active graph and source layers for the requested topic before
   creating anything.
5. Classify the request as read-only query, Layer 1 source maintenance, Active
   Layer 2 maintenance, Meta maintenance, Obsidian carrier maintenance, or lint
   tooling maintenance.

If this file and `SCHEMA.md` disagree, follow `SCHEMA.md` and report the stale
skill instruction for maintenance.

## Current Storage Model

- `_living/**`: private, user-maintained, evolving source documents. Keep them
  cohesive and free of graph wikilinks and semantic Layer 2 frontmatter.
- `raw/**`: versioned public source material such as articles and papers. Treat
  captured source bodies as immutable; record provenance metadata when the
  schema requests it.
- `entities/**`, `concepts/**`, `comparisons/**`, `queries/**`: Agent-maintained
  Active Layer 2 knowledge nodes.
- `SCHEMA.md`, `index.md`, `log.md`: Meta pages. They are operational state, not
  graph nodes, and must keep zero inbound and outbound local-document edges.
- `_archive/**`: historical, inactive pages. Active nodes must not link to them
  as normal graph targets.

Do not register `_living`, `raw`, Meta, or Archive files in `index.md`. The index
contains Active Layer 2 nodes only.

## Operation Modes

### Query

1. Use `index.md` to locate likely Active Layer 2 nodes.
2. Search Active Layer 2 and relevant `_living`/`raw` sources for supporting
   evidence, especially when the index summary is insufficient.
3. Read the relevant pages and synthesize the answer with clear source
   boundaries.
4. Treat a normal query as read-only. Create a `queries/` or `comparisons/` node
   only when the user asks to retain the result or the task explicitly includes
   Wiki maintenance.

### Ingest or synchronize a source

1. Route the source before writing:
   - private, hand-maintained, continuously evolving material → `_living/**`;
   - public material with a meaningful published/retrieved version → `raw/**`.
2. Preserve `_living` as a source layer: do not add graph links or Layer 2
   semantic metadata to it. When importing internal documents, remove private
   implementation details that are not reusable outside their original project.
3. Preserve `raw` content as captured source material; put corrections and
   synthesis in Layer 2 rather than silently rewriting the source body.
4. Search for existing nodes before creating new ones. Prefer updating a
   coherent node over creating a duplicate or a one-source wrapper page.
5. Apply the current `SCHEMA.md` type semantics and granularity rules. Multiple
   mentions are only a discovery signal, not an automatic creation threshold.
6. For ordinary synchronization, update claims supported by the current source
   but do not remove knowledge merely because it disappeared silently. Perform
   deletion-oriented deep synchronization only when the user explicitly asks
   for it.

### Create or update Active Layer 2 nodes

For every changed Active node:

- Place it only under `entities/`, `concepts/`, `comparisons/`, or `queries/`,
  with `type` matching its directory.
- Use a globally unique lowercase kebab-case slug.
- Keep all required frontmatter fields current, including non-empty `tags` and
  `sources`; use only tags registered in the current schema.
- Prefer evidence quality and applicability over source recency. Preserve real
  disagreements with their scope instead of letting the newest source
  automatically overwrite the older one.
- Add a wikilink only when the surrounding text states a concrete relationship
  supported by evidence. There is no minimum link count; zero justified links
  is better than invented graph structure.
- Use the schema's exact provenance syntax: compact `_living` footnotes for
  private sources and raw-path markers for public captured sources.
- Update `updated` whenever body, frontmatter, slug, or links change.

When creating or changing a `comparison`, preserve its required comparison
table, trade-offs, and operational selection guidance. When creating a `query`,
preserve a concrete problem statement and actionable method rather than a
generic concept explanation.

### Rename, replace, archive, or delete

- Resolve every inbound reference before changing the target.
- A rename updates the file, active links, contradiction slugs, and index entry
  atomically; do not leave compatibility stubs or empty old files.
- A split, merge, or replacement updates all affected links and navigation in
  the same change.
- Delete accidental, empty, or short-lived ghost pages directly.
- Archive only material with historical value, remove it from `index.md`, and
  remove active graph links to it.

## Index and Log Discipline

- Register every Active Layer 2 page exactly once under its matching section in
  `index.md`, sorted by slug.
- Use a code-formatted path plus one-line summary. Do not use wikilinks or local
  Markdown links in the index.
- Keep `Total pages` equal to the number of registered Active nodes and update
  the structural date when the registry changes.
- Use one top-level `## [YYYY-MM-DD] daily | ...` entry per local calendar day.
  Add `###` subsections or bullets to the existing daily entry instead of
  creating multiple same-date headings.
- Preserve Trigger, Actions, Boundary, and Verification details for structural
  maintenance. A read-only query or audit does not modify the log unless the
  user asks to record it.

## Validation

After any Wiki write, run from the repository root:

```bash
python3 scripts/wiki_lint.py
```

If `SCHEMA.md`, `scripts/wiki_lint.py`, or a machine-readable Wiki convention
changed, also run:

```bash
python3 scripts/wiki_lint.py --json
```

Treat `SCHEMA.md` and `scripts/wiki_lint.py` as a co-evolving contract. Add a
mechanical check when a new rule can be checked reliably; leave evidence
strength, relationship quality, granularity, and reusable-knowledge judgment as
explicit manual review constraints.

If `.obsidian/**` or the Obsidian operating procedure changes, perform the
carrier checks required by `SCHEMA.md` and clearly separate local verification
from actions that still require the Obsidian UI.

## Change Safety and Reporting

- Before a deep synchronization or a change expected to touch 10 or more
  existing pages, present the scope and obtain confirmation.
- Do not report success solely because Markdown was written. Require the
  applicable lint command to exit successfully.
- Report every created, updated, moved, archived, or deleted file, the source
  routing decision, and the validation result.
- If validation is incomplete, state exactly what was not checked and why.
