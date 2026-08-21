# Feishu Document to Local Wiki

Use this reference only when a Feishu document is being incorporated into the
local schema-governed Wiki.

## 1. Orient Before Extraction

Load `llm-wiki`, then read the current `wiki/SCHEMA.md`, `wiki/index.md`, and the
latest complete daily entry in `wiki/log.md`. The schema is authoritative; do
not reuse older directory, frontmatter, index, provenance, or log templates from
memory.

## 2. Extract the Feishu Source

Use the canonical extractor:

```bash
~/.hermes/hermes-agent/venv/bin/python \
  ~/.hermes/my-skills/productivity/feishu-docs/scripts/extract_docx_to_markdown.py \
  <doc_token>
```

For a folder explicitly approved for bulk ingest, use:

```bash
~/.hermes/hermes-agent/venv/bin/python \
  ~/.hermes/my-skills/productivity/feishu-docs/scripts/batch_ingest_folder.py \
  <folder_token> <absolute-category-path> --dry-run
```

Review the dry-run targets, then repeat without `--dry-run`. The script refuses
paths outside the active Wiki's `_living` tree, refuses to overwrite existing
sources, rolls back newly written files on failure, and records one subsection
under the current daily log entry. It transforms layout; it does not prove
semantic compliance. Review every output before treating it as a maintained
Wiki source.

## 3. Route to `_living`

Feishu documents are private, continuously maintained sources, so place their
cleaned Markdown under an existing valid `_living/<Topic>/` directory such as:

- `_living/AI-Infrastructure/`
- `_living/AI-Applications/`
- `_living/TCS-and-Math/`
- `_living/Whale-SpaceSight/`

Do not invent a new topic directory without checking the current schema naming
rule. Preserve a useful title and source meaning, but remove Feishu-specific
presentation artifacts such as the generated version table and native mention
tokens.

`_living` files are source material, not Active Layer 2 nodes:

- do not add `type`, `tags`, `sources`, or other semantic graph frontmatter;
- do not add graph wikilinks to the source body;
- do not register `_living` paths in `index.md`;
- do not use a Feishu URL or token as an Active node's `sources` entry.

## 4. Apply the Reusability Filter

Before saving an internal document as a living source, remove details that do
not transfer beyond the original implementation unless the user explicitly
needs them retained:

- private table, class, function, model-node, and configuration-key names;
- one-off thresholds, dimensions, experiment numbers, schedules, and store data;
- credentials, tenant identifiers, user identifiers, and internal URLs;
- product or dependency versions that are not themselves the subject of the
  source.

Keep reusable architecture, methodology, constraints, failure modes, rationale,
and qualitative effects. Record uncertainty rather than inventing generalized
claims.

## 5. Derive Active Knowledge Separately

After the living source is ready, use `wiki-content-extraction` to decide whether
it supports updates or new nodes under `entities/`, `concepts/`, `comparisons/`,
or `queries/`.

Active nodes must cite the local `_living` path using the exact provenance and
frontmatter syntax defined by `SCHEMA.md`. Only Active Layer 2 nodes are added to
`index.md`.

## 6. Log and Validate

Record structural work in the current date's single daily log entry. Append a
subsection when today's entry already exists instead of creating a duplicate
top-level heading.

Run from the repository root:

```bash
python3 scripts/wiki_lint.py
```

If the schema, validator, or a machine-readable convention changed, also run
`python3 scripts/wiki_lint.py --json`.

The batch wrapper's offline regression test is:

```bash
~/.hermes/hermes-agent/venv/bin/python \
  ~/.hermes/my-skills/productivity/feishu-docs/scripts/test_batch_ingest_folder.py
```
