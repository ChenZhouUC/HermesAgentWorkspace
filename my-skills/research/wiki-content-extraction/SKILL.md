---
name: wiki-content-extraction
description: Use when extracting structured knowledge from session history, documents, or tools into the local Karpathy-style wiki, including SCHEMA.md tag registration, _living source creation, and wiki_lint.py validation.
---

# Wiki Content Extraction

Extract structured knowledge from session history, documents, APIs, or tool outputs into a Karpathy-style LLM Wiki. Covers the full pipeline: mining → categorizing → writing → registering → validating.

## When This Skill Activates

Use when the user asks to:

- Extract past Q&A or topics from conversation history into the wiki
- Create a structured document/list from session DB queries
- Add content to an existing wiki that requires SCHEMA.md compliance
- Run wiki_lint.py and fix validation failures

## Core Workflow

### 1. Mine the Source Data

For session history mining (SQLite-backed Hermes state.db):

```python
import sqlite3
from pathlib import Path

db = sqlite3.connect(Path("~/.hermes/state.db").expanduser())
db.row_factory = sqlite3.Row
cursor = db.cursor()
keyword = "KEYWORD"

# Find matching user messages
query = """
SELECT m.session_id, m.id as msg_id, m.content, m.timestamp
FROM messages m
WHERE m.role = 'user' AND m.content LIKE ?
ORDER BY m.timestamp ASC
"""
cursor.execute(query, (f"%{keyword}%",))
results = cursor.fetchall()

# For each, fetch next assistant message
for msg in results:
    a_query = """
    SELECT content FROM messages
    WHERE session_id = ? AND role = 'assistant' AND timestamp > ?
    ORDER BY timestamp ASC LIMIT 1
    """
    cursor.execute(a_query, (msg['session_id'], msg['timestamp']))
```

### 2. Categorize and Synthesize

Don't dump raw transcripts. Group into logical categories with:

- Business context and background
- Clear problem statements
- Actionable requirements or solutions
- Structured formatting (tables, lists, code blocks)

### 3. Write the Wiki Page

Follow SCHEMA.md conventions exactly:

- Proper YAML frontmatter with all required fields
- Type matches directory (`entities/` → `entity`, `concepts/` → `concept`)
- Tags from the registered taxonomy ONLY

### 4. Register Tags in SCHEMA.md FIRST

**CRITICAL ORDER**: If you need new tags, add them to `SCHEMA.md` Tag Taxonomy _before_ using them in frontmatter.

`wiki_lint.py` will reject pages with unregistered tags. The validation loop will fail until you:

1. Add tags to SCHEMA.md taxonomy section
2. Keep frontmatter tags matching exactly

Example SCHEMA.md addition:

```markdown
- **业务与项目 (Business & Projects):** `spacesight`, `product-management`, `compliance`
```

### 5. Create _living Source and Update index.md

- Create `_living/<category>/<topic>.md` source file
- Register in `index.md` under correct section (alphabetical order)
- Update "Total pages" count and "Last updated" date in index header

### 6. Validate with wiki_lint.py

```bash
python3 ~/.hermes/scripts/wiki_lint.py
```

Fix any issues before declaring done. Common failure modes:

- **invalid_tags**: Tags not in SCHEMA.md taxonomy → add them first
- **unindexed_active**: Page not in index.md → register it
- **missing_fields**: Frontmatter incomplete → add sources, confidence
- **index_count_mismatch**: Total pages wrong → update count

## Pitfalls

- **Tag order matters**: Register in SCHEMA.md before using in frontmatter. Doing it backwards creates a validation loop.
- **Bundled skill limits**: `llm-wiki` is a bundled skill under `~/.hermes/skills/` — cannot be patched. Create custom skills or reference files for extensions.
- **Alphabetical index**: New entries in index.md must be alphabetically sorted within their section.
- **\_living sources required**: Every wiki page needs a _living source reference in frontmatter.
- **Type-directory alignment**: `type: entity` must be in `entities/`, `type: concept` in `concepts/`, etc.

## Related

- Primary wiki skill: `llm-wiki` (bundled, read-only)
- Schema validation: `wiki_lint.py` script
- Location: `~/.hermes/wiki/`
