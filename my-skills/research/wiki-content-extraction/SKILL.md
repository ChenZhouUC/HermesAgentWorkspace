---
name: wiki-content-extraction
description: Extract sources into the schema-governed local wiki.
---

# Wiki Content Extraction

Turn private session history, internal documents, public sources, or tool output
into reusable Wiki knowledge without dumping transcripts or bypassing the
current schema. This skill is intentionally separate from group-visible
`llm-wiki` because session history and source preparation can expose private
local data.

## When to Use

Use this skill when the user asks to:

- mine earlier conversations for reusable knowledge;
- convert internal documents or tool output into Wiki source material;
- synchronize an existing `_living` source into Active Layer 2;
- repair extraction-related `wiki_lint.py` failures.

Do not invoke session-history extraction in a shared or Feishu group context.
Do not expose session IDs, raw transcripts, local paths, credentials, private
rosters, or unrelated source material in user-visible output.

## Required Orientation

Before extracting or writing anything:

1. Load `llm-wiki`.
2. Read `wiki/SCHEMA.md` completely; it is the authority for layer boundaries,
   types, frontmatter, provenance, links, index, log, and validation.
3. Read `wiki/index.md`, the most recent complete daily entry in `wiki/log.md`,
   and existing pages related to the topic.
4. Classify the operation as source capture, incremental synchronization, deep
   synchronization, or Active Layer 2 maintenance.

## 1. Mine the Source Safely

For Hermes conversation history, prefer the built-in session-search capability
over direct SQLite queries. Search narrowly by topic or time range, then read
only the conversations needed for the requested extraction.

Use direct read-only access to `state.db` only when the normal search surface is
insufficient and the user has requested that level of inspection. Do not assume
the database schema, pair a user message with the next assistant row blindly,
or copy raw conversation records into the Wiki.

For documents and tool output:

- preserve the user's meaning, decisions, and reusable technical evidence;
- remove chat scaffolding, duplicated status text, credentials, identifiers,
  and unrelated implementation details;
- keep uncertainty and conflicting claims explicit rather than smoothing them
  into unsupported certainty.

## 2. Route the Source Layer

- Private, hand-maintained, continuously evolving material belongs under
  `_living/**`.
- Public material with a meaningful published or retrieved version belongs
  under `raw/**`.
- Do not add Active Layer 2 semantic frontmatter or graph wikilinks to `_living`
  sources.
- Do not register `_living` or `raw` files in `index.md`.
- Treat captured `raw` bodies as immutable; later corrections and synthesis
  belong in Active Layer 2.

When importing an internal document into `_living`, preserve reusable
architecture, method, constraints, and rationale. Remove private implementation
names, one-off measurements, project schedules, and configuration details that
would not transfer to another organization or product unless the user explicitly
needs them retained.

## 3. Synthesize Active Layer 2

Search before creating. Update an existing coherent node when possible; do not
create a one-to-one wrapper for every source document.

Choose the node type using the current schema:

- `entity`: a concrete product, system, model, organization, device, or named
  framework with an independent identity;
- `concept`: a reusable mechanism, method, principle, or abstract capability;
- `comparison`: a genuine selection problem with a comparison table,
  trade-offs, and when-to-use guidance;
- `query`: a concrete problem or diagnostic scenario with an actionable method.

For every Active Layer 2 node:

- use a globally unique lowercase kebab-case slug;
- keep `type` aligned with its directory;
- populate every required frontmatter field with non-empty, valid `tags` and
  local `sources` paths;
- register new tags in `SCHEMA.md` before using them and trigger the schema/lint
  co-evolution checks when taxonomy or structural rules change;
- add only evidence-backed wikilinks with an explicit relationship in the
  surrounding prose; there is no minimum link count;
- use the exact `_living` or `raw` provenance marker required by the schema;
- update the `updated` date whenever content, links, slug, or frontmatter change.

## 4. Synchronization Modes

- **Incremental is the default:** add or revise claims supported by current
  source material without deleting knowledge merely because it disappeared
  from a newer draft.
- **Deep synchronization requires explicit user intent:** follow provenance
  references back from Layer 2 and remove claims no longer present in the
  authoritative source.
- **Single-node override:** use only when the user identifies one source as the
  authoritative replacement for a specific node.

Before a deep synchronization or a plan affecting 10 or more existing pages,
present the intended scope and wait for confirmation.

## 5. Register and Log

- Add every new Active Layer 2 node to `index.md` exactly once, under the
  matching type section and sorted by slug.
- Use a code-formatted path plus one-line summary; never use wikilinks or local
  Markdown links in the index.
- Keep the index count and structural date accurate.
- Record structural work in the current day's single
  `## [YYYY-MM-DD] daily | ...` entry. Append a subsection or bullets when that
  date already exists.
- Preserve Trigger, Actions, Boundary, and Verification details. Do not create a
  log entry for a read-only query that changed no files.

## 6. Validate

Run from the repository root after every write:

```bash
python3 scripts/wiki_lint.py
```

If the schema, lint implementation, or a machine-readable convention changed,
also run:

```bash
python3 scripts/wiki_lint.py --json
```

Do not declare success until the applicable lint command exits zero. Report the
source-routing decision, every changed file, and any semantic checks that remain
manual, especially evidence strength, relationship quality, and granularity.

## Related

- Operational Wiki workflow: `llm-wiki`
- Feishu source extraction: `feishu-docs`
- Validator: `~/.hermes/scripts/wiki_lint.py`
- Standard Wiki root: `~/.hermes/wiki/`
