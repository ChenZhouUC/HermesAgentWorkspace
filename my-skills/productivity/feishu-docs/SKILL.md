---
name: feishu-docs
description: "Master guide for Feishu (Lark) Docs: read via Bot API, convert Markdown via Import API, update existing docs (precise indexing, tables, mentions), and read Minutes."
category: productivity
---

# Feishu (Lark) Docs & Minutes Management

Use this skill whenever you need to read, summarize, create, or update documents in Feishu, as well as read Feishu Minutes.

## 🚨 Critical Rules & Pitfalls

1. **NEVER CREATE NEW DOCS (CRITICAL)**: The user STRICTLY prefers to revise existing documents in-place. You MUST append/blend information into an existing document URL provided by the user or found in memory. DO NOT create a brand new standalone document unless explicitly forced.
2. **Permissions (Tenant Editable)**: If you absolutely MUST create a new document, you MUST immediately patch its permissions to allow the user to edit it (`"link_share_entity": "tenant_editable"`). Do not leave it as read-only.
3. **ALWAYS UPDATE VERSION TABLE**: After EVERY single modification to an existing document, you MUST append a new row to the Version Table at the top of the doc to log the update.
4. **Title & Formatting**: Always ensure the document has a professional Chinese/English title (e.g., "L20 vs RTX 5880 Ada: Parameters"). DO NOT use Markdown file names (no `.md` suffix in the doc title).
5. **Raw URLs Only (CRITICAL)**: When sending the final document URL to the user in Feishu chat, **always include the raw, unformatted URL string** (e.g., `https://domain.feishu.cn/docx/XYZ...`).
6. **References**: ALWAYS append a `## References` section formatted in Chicago style at the bottom of the document if you used ANY external search information. Do not skip this even if the primary task was running local SSH commands.
7. **Bot Native Mention**: The user expects a native Feishu mention card for the author (e.g., `@小聪明蛋`), not plain text. For the bot, `小聪明蛋`'s `open_id` is `ou_0091f5c50226a4ee0dc8a6d51665db0f`. You must POST or PATCH text elements with `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}` instead of a plain text `@...`.
8. **Creating from Markdown**: **NEVER parse Markdown manually to use the Blocks API**. The only way to get perfect native formatting is to upload the `.md` file to Feishu Drive and use the `import_tasks` API.
9. **Updating Existing Docs**: **NEVER BLINDLY APPEND** to the end. You MUST "blend" the new information into existing logical sections by finding the correct integer `index`.
10. **Reading Docs (Scraping Fallacy)**: **NEVER use curl, wget, or BeautifulSoup to scrape Feishu URLs.** Feishu Docs are client-side rendered (SPA); HTML scraping only returns a loading screen. Always use the native `feishu_doc_read` tool or the `extract_docx_to_markdown.py` fallback script.
11. **403 Forbidden Fallbacks**: If appending to a user's doc fails with HTTP 403 Forbidden, and you create a fallback document, you MUST STILL apply all strict formatting rules (Professional Title, Version Table, Chicago References). Do NOT just dump raw markdown via append. Use `scripts/rebuild_doc_from_md.py` on the fallback doc to guarantee the Version Table and Title are initialized properly, and ensure your source markdown includes the `## References` section.

---

## ✍️ Creating: Markdown to Perfect Feishu Docx

**USER RULE:** The user explicitly forbids creating new standalone documents (`NEVER create new docs`), strongly preferring to revise existing docs in-place.
If you absolutely MUST create a new document (e.g., explicitly forced), you MUST explicitly grant edit permissions so the user isn't locked out and handle correct title formatting and mention resolution.

**DO NOT** attempt to manually implement the upload, import, and patching logic using `curl` and `urllib`. Instead, use the robust, fully automated Python script provided in this skill directory.

**Command:**

```bash
uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/create_new_doc_from_md.py <md_file_path> "<Professional_Title>"
```

This script automatically handles:

1. Drive upload with correct `.md` extension.
2. Polling the Import API.
3. Patching the root block to set the professional title.
4. Setting permissions to `tenant_editable`.
5. Resolving plain text `@小聪明蛋` to native mention cards.

---

## 🔨 Rebuild Document From Scratch (Clear + Re-import)

When the user says "清理旧内容并按规范重写" or asks for a full doc overhaul (new title, fresh version table, new content), DO NOT attempt incremental patches. Use this atomic rebuild workflow via the provided script:

**Command:**

```bash
uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/rebuild_doc_from_md.py <target_doc_token> <md_file_path>
```

This script handles clearing old content, updating the title, creating a fresh Version Table, and safely merging the new Markdown.

---

## 🧩 Updating Existing Documents & Precise Indexing

### 1. Deleting Blocks (batch_delete)

When you need to delete a block (e.g., an old table or an empty cell text), you MUST use `DELETE` (not POST) on the parent's `batch_delete` endpoint, providing the integer indices, NOT block IDs.

```python
del_req = urllib.request.Request(
    f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{parent_block_id}/children/batch_delete",
    data=json.dumps({"start_index": target_idx, "end_index": target_idx + 1}).encode(),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    method='DELETE'
)
```

### 2. Version Table Standard Template & Appending Rows

The standard Version Table has 3 columns: `Version` | `Time` | `Author`
Column Widths: `[150, 250, 150]`

**Data Format Rules (CRITICAL):**

- `Version`: Must follow `YYYYMMDD.XXed` (e.g., `20260518.01ed`).
- `Time`: Must be `YYYY-MM-DD HH:MM:SS UTC+8`.
- `Author`: MUST be a native mention card (`@小聪明蛋` -> `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}`), NOT plain text.

**CRITICAL: Adding a row to an existing table is NOT natively supported.** You MUST replace the table:

- `Version`: `YYYYMMDD.XXed` format (e.g., `20260518.01ed`). Increment the suffix (`01ed`, `02ed`, `03ed`...) per edit session.
- `Time`: `YYYY-MM-DD HH:MM:SS UTC+8` format.
- `Author`: Native `@小聪明蛋` mention card via `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}`. **Never plain text.**
- Append a NEW row on EVERY modification. Never replace or collapse old rows.

**CRITICAL: Adding a row to an existing table is NOT natively supported.** You MUST replace the table:

1. Re-read all existing cell contents from the old table.
2. Create a NEW Table block. **CRITICAL:** Do NOT include a `children` array, `cells`, or `merge_info` in the table payload! Only pass `row_size`, `column_size`, and `column_width`. Let Feishu auto-create the cells.
   **CRITICAL (9-Row Limit):** Feishu's Block API limits table creation to a maximum of **9 rows** (`row_size <= 9`). If you need more (e.g. copying a large table), you MUST split it into multiple adjacent table blocks. Otherwise, it throws `HTTP 400 (1770001 invalid param)`.

```python
new_table_payload = {
    "block_type": 31,
    "table": {
        "property": {
            "row_size": new_row_size,
            "column_size": 3,
            "column_width": [150, 250, 150]
        }
    }
}
# POST to /blocks/{parent_id}/children with the appropriate index
```

3. Fetch the new table's auto-generated cell IDs (`res['data']['children'][0]['table']['cells']`).
4. `POST` your text blocks (including the old ones and your new row) to each cell's `/children` endpoint.
5. Use `batch_delete` (as shown above) to delete the old table block from the document, and delete the default empty text block (index 0) from each new cell (**wrap the cell deletion in a `try...except` block**, as Feishu may return `HTTP 404 (1770002)` if the block is already absent or processed).

### 3. Complex Lists (1770001 Fix)

- Do NOT fallback to fake text bullets (`•`).
- When POSTing a list, the payload is `{"block_type": 12, "bullet": {"elements": [...]}}` (Note the key is `bullet` or `ordered`, NOT `text`).

### 4. Updating Text/Headings (Error 400 Fix)

When patching existing text blocks, you **MUST** use `update_text_elements`:
`{"update_text_elements": {"elements": [{"text_run": {"content": "New Text"}}]}}`

**Deep Traversal Pitfall (Tables & Cells):** When searching for text to patch (e.g., to fix plain text `@小聪明蛋` mentions), be aware that Table (31) and Cell (32) blocks might not reliably expose `has_child: true` in the parent's `/children` API response. You MUST explicitly check for `block_type in (31, 32)` and recursively fetch their children to reach the nested Text (2) blocks.

### 5. Document Metadata & Creation Time

The `documents/{doc_token}` API does NOT return `created_at` or `update_time` directly. To get a document's creation time (especially for Wiki docs), query the Wiki API `wiki/v2/spaces/get_node?token={wiki_token}` and read `obj_create_time` or `node_create_time` (Unix timestamp).

### 6. Copying Content (Import Temp Doc -> Existing Doc)

To merge large Markdown content into an existing document with perfect native formatting:

1. Import the MD file via `import_tasks` to a temporary document.
2. Read all blocks from the temp document.
3. Build a hierarchical POST payload for the target document.
   - **Strip all `block_id`s.**
   - **Tables:** ONLY copy `row_size`, `column_size`, and `column_width`. Do NOT include `cells` or `merge_info` in the payload. Split tables if they exceed the 9-row limit.
4. Insert top-level blocks in chunks (e.g., 40 at a time) to avoid payload size/timeout errors.
5. Re-map the newly created auto-generated cell IDs and sequentially POST their nested children. (See `scripts/merge_markdown_blocks.py` for the block-mapping implementation. For a fully automated end-to-end wrapper, run: `python ~/.hermes/my-skills/productivity/feishu-docs/scripts/append_md_to_doc.py <target_doc_token> <md_file_path>`).

**CRITICAL ORDERING PITFALL (Table/Text interleaving):** When the Markdown contains alternating headings, text, and tables, the original `merge_markdown_blocks.py` would batch ALL non-table blocks and POST them AFTER the tables in each chunk, destroying document order (headings ended up below their tables). The fix: use a `flush_payload()` mechanism that immediately POSTs accumulated non-table blocks whenever a table is encountered, then POSTs the table individually, then continues. This preserves strict source-order insertion. The patched script at `scripts/merge_markdown_blocks.py` already implements this — do NOT revert to the old batch-at-end-of-chunk pattern.

---

## 📖 Reading Feishu Docs (Fallback)

If the native `feishu_doc_read` tool fails with `Feishu client not available (not in a Feishu comment context)`, use the bundled extraction scripts via the Open API.

- **Canonical extractor**: `uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/extract_docx_to_markdown.py <doc_token>`
  Handles nested blocks, tables, lists, and wiki-token-to-doc-token resolution automatically.
- **Lightweight fallback**: `uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/read_docx_to_markdown.py <doc_token>`
  Useful when you only need a straightforward block dump to Markdown.
- **Compatibility helper**: `uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/download_docx_to_md.py <doc_token>`
  Keeps older workflows working when the lightweight extraction path is sufficient.
- **Dependency note**: All three scripts require the `requests` Python package. The base system Python does NOT have it installed. You MUST prefix with `uv run --with requests` (or ensure `requests` is available) to avoid `ModuleNotFoundError`.
- **Wiki vs Docx Pitfall**: If the target URL is a Feishu Wiki link (`https://domain.feishu.cn/wiki/TOKEN`), the application MUST have `wiki:wiki:readonly` or `wiki:node:read` permissions. If it only has document permissions, the API will reject it with a `99991672 Access denied` error. Ask the user to grant the Wiki scope or provide the underlying standard `.docx` link.

---

## 🔄 Converting Feishu Docs to Local LLM Wiki Markdown

When the user asks to extract a Feishu Document and save it into their local LLM Wiki (`~/.hermes/wiki/_living/` or similar), follow this specific transformation pipeline to bridge the two formats:

1. **Extract Raw Markdown**:
   Use the extraction script to get the Feishu document content:
   `uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/extract_docx_to_markdown.py <doc_token>`

2. **Clean Feishu Artifacts**:
   - **Extract Dates**: Before deleting the Version Table, extract the creation date (first row) and update date (last row) to use in the YAML frontmatter.
   - **Remove the Version Table**: Delete the Markdown table at the top of the document that tracks `Version | Time | Author`. This is a Feishu-specific artifact that pollutes the static wiki.
   - **Remove Native Mentions**: Clean up any `@小聪明蛋` or similar Feishu user mentions, converting them to plain text (e.g., "周琛") or removing them if redundant.

3. **Add Wiki YAML Frontmatter (CRITICAL)**:
   Prepend standard LLM Wiki frontmatter to the top of the file. You MUST include `type`, `tags`, and `sources` per the `llm-wiki` schema.

   ```yaml
   ---
   title: <Clean Professional Title>
   created: <YYYY-MM-DD>
   updated: <YYYY-MM-DD>
   type: <entity | concept | comparison | summary>
   tags: [<applicable tags from wiki taxonomy>]
   sources: [Feishu Doc URL or Token]
   ---
   ```

   _(Keep the original `# <Title>` H1 header below the frontmatter as well)._

4. **Save to Wiki**:
   Determine the appropriate subdirectory in `~/.hermes/wiki/_living/` (e.g., `AI-Infrastructure/`, `AI-Applications-and-Ops/`, `TCS-and-Math/`).
   Write the file using `write_file` with lowercase, hyphenated naming: `~/.hermes/wiki/_living/<Category>/<title-with-hyphens>.md`.

5. **Update Wiki Navigation (CRITICAL)**:
   - **Index**: You MUST append a one-line summary and wikilink to `~/.hermes/wiki/index.md` under the appropriate section.
   - **Log**: You MUST append an entry to `~/.hermes/wiki/log.md` recording the ingest action (`## [YYYY-MM-DD] ingest | Feishu Doc: <Title>`).

## 🎙️ Reading Feishu Minutes (飞书妙记)

Use `minutes/v1/minutes/{token}/transcript` returning PLAIN TEXT, do NOT `.json()`.
Ensure `res.encoding = 'utf-8'`.
