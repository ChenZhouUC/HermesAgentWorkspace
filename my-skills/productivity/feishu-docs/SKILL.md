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
3. **Markdown URL Parsing Bug (trailing period)**: When formatting URLs in any context (Chicago-style references, inline links, etc.), NEVER place a period `.` immediately after the URL (e.g. `.../instance-families.`). Feishu's link parser treats the trailing period as part of the URL, causing a 404. Leave a space before the period or drop the period.
4. **ALWAYS UPDATE VERSION TABLE**: After EVERY single modification to an existing document, you MUST append a new row to the Version Table at the top of the doc to log the update.
5. **Title & Formatting**: Always ensure the document has a professional Chinese/English title (e.g., "L20 vs RTX 5880 Ada: Parameters"). DO NOT use Markdown file names (no `.md` suffix in the doc title).
6. **Raw URLs Only (CRITICAL)**: When sending the final document URL to the user in Feishu chat, **always include the raw, unformatted URL string** (e.g., `https://domain.feishu.cn/docx/XYZ...`).
7. **References**: ALWAYS append a `## References` section formatted in Chicago style at the bottom of the document if you used ANY external search information. Do not skip this even if the primary task was running local SSH commands. End each line immediately after the URL — no trailing period (see rule 3).
8. **URL Verification**: NEVER rely on internal pre-training knowledge for documentation URLs, product links, or API endpoints. Training data gets stale. ALWAYS use `web_search` to find and verify the live, current URL before inserting it into a document.
9. **Bot Native Mention**: The user expects a native Feishu mention card for the author (e.g., `@小聪明蛋`), not plain text. For the bot, `小聪明蛋`'s `open_id` is `ou_0091f5c50226a4ee0dc8a6d51665db0f`. You must POST or PATCH text elements with `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}` instead of a plain text `@...`.
10. **Creating from Markdown**: **NEVER parse Markdown manually to use the Blocks API**. The only way to get perfect native formatting is to upload the `.md` file to Feishu Drive and use the `import_tasks` API.
11. **Updating Existing Docs**: **NEVER BLINDLY APPEND** to the end. You MUST "blend" the new information into existing logical sections by finding the correct integer `index`.
12. **Reading Docs (Scraping Fallacy)**: **NEVER use curl, wget, or BeautifulSoup to scrape Feishu URLs.** Feishu Docs are client-side rendered (SPA); HTML scraping only returns a loading screen. Always use the native `feishu_doc_read` tool or the `extract_docx_to_markdown.py` fallback script.
13. **403 Forbidden Fallbacks**: If appending to a user's doc fails with HTTP 403 Forbidden, and you create a fallback document, you MUST STILL apply all strict formatting rules (Professional Title, Version Table, Chicago References). Do NOT just dump raw markdown via append. Use `scripts/rebuild_doc_from_md.py` on the fallback doc to guarantee the Version Table and Title are initialized properly, and ensure your source markdown includes the `## References` section.
14. **Wiki vs Docx Permission Scope**: If the target URL is a Feishu Wiki link (`https://domain.feishu.cn/wiki/TOKEN`), the application MUST have `wiki:wiki:readonly` or `wiki:node:read` permissions. If it only has document permissions, the API will reject it with a `99991672 Access denied` error. Ask the user to grant the Wiki scope or provide the underlying standard `.docx` link.
15. **Shortcuts (404 / 1770032 forBidden)**: If you obtain a file token from a folder listing and that token is a `shortcut` type, reading its raw token or its metadata directly often fails with 404 or `1770032 forBidden`. If extraction fails on a shortcut, notify the user that the source file is either deleted or lacks public/group permissions inherited by the bot.

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
6. Writing the initial Version Table.

---

## ➕ Updating an Existing Doc (append + auto version row)

To blend new Markdown into an existing doc, use the append script. It imports the
Markdown, merges the blocks in source order, **and automatically appends a new
version-table row preserving all prior history** (no manual table surgery):

```bash
uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/append_md_to_doc.py <target_doc_token> <md_file_path>
```

The whole operation is **atomic** (see below): if any step fails, the document is
rolled back to its pre-update state.

---

## 🔨 Rebuild Document From Scratch (Clear + Re-import)

When the user says "清理旧内容并按规范重写" or asks for a full doc overhaul (new title, fresh content), DO NOT attempt incremental patches. Use this atomic rebuild script:

**Command:**

```bash
uv run --with requests python ~/.hermes/my-skills/productivity/feishu-docs/scripts/rebuild_doc_from_md.py <target_doc_token> <md_file_path> "<Professional_Title>"
```

It clears old content, sets the title, **re-creates the Version Table preserving the
existing history (and appending a new row)**, and merges the new Markdown. The
upload+import happen before anything destructive, and the rewrite is atomic.

---

## ⚛️ Atomicity & Failure Handling (CRITICAL)

The `append_md_to_doc.py` and `rebuild_doc_from_md.py` scripts wrap their destructive
work in `feishu_common.atomic_update`:

- The doc is **snapshotted to a local backup file** (`~/.hermes/db_workspace/feishu_backups/`) before any destructive write.
- On **any** failure mid-update, the doc is **rolled back** to its pre-update state. You end up with either the fully-updated doc or the original — never a half-written, garbled doc.
- If rollback itself fails, the backup file path is printed for manual recovery.
- All API calls retry automatically on rate limits, 5xx, and dropped connections (the `RemoteDisconnected` that large `batch_delete`s trigger).

**RULE: If a script fails, READ the printed error, fix the input/cause, and RE-RUN the script.** Do NOT hand-roll the upload/import/table logic with inline `curl`/`urllib`/`requests` as a fallback — improvised manual API calls are exactly what produced duplicate version tables and garbled docs in the past. The scripts are the only supported write path.

---

## 🧩 Updating Existing Documents & Precise Indexing

### 1. Deleting Blocks (batch_delete)

When you need to delete a block (e.g., an old table or an empty cell text), you MUST use `DELETE` (not POST) on the parent's `batch_delete` endpoint, providing the integer indices, NOT block IDs.

**Pitfall (Large Deletions)**: Deleting hundreds of blocks simultaneously (e.g., clearing a large document for a rebuild) can cause the Feishu API to abruptly close the connection, resulting in a `http.client.RemoteDisconnected` crash. If this happens, simply retry the execution, or update your script to chunk large `batch_delete` operations.

```python
del_req = urllib.request.Request(
    f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{parent_block_id}/children/batch_delete",
    data=json.dumps({"start_index": target_idx, "end_index": target_idx + 1}).encode(),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    method='DELETE'
)
```

### 2. Version Table (automated — do not hand-roll)

Appending a version row is **fully automated** by `feishu_common.append_version_row`,
which `append_md_to_doc.py` calls after every content merge. It reads the existing
table, computes the next version, preserves all history, appends the new row, and
splits across consecutive tables if the history exceeds Feishu's 9-row table limit.
You normally never touch this by hand — run `append_md_to_doc.py`.

**Format spec (enforced by the script; reference only):**

- `Version`: `YYYYMMDD.NNed` (e.g., `20260518.01ed`). The suffix `NN` auto-increments for multiple edits on the same day and resets to `01` on a new day.
- `Time`: `YYYY-MM-DD HH:MM:SS UTC+8`.
- `Author`: native mention card `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}` — **never** plain text.
- Columns: `Version | Time | Author`, widths `[150, 250, 150]`.
- A NEW row is appended on every modification; old rows are preserved, never collapsed.

**Why it can't just "add a row":** Feishu has no native "append row" — the table must
be rebuilt. The script handles this (re-read rows → new table with `row_size`/`column_size`/`column_width`
only, no `cells`/`merge_info` → refill cells → delete old table), including the 9-row
split that otherwise throws `HTTP 400 (1770001)`. If you ever must debug it, see
`scripts/feishu_common.py`; do not reimplement it inline. Use `batch_delete` (as shown above) to delete the old table block from the document, and delete the default empty text block (index 0) from each new cell (**wrap the cell deletion in a `try...except` block**, as Feishu may return `HTTP 404 (1770002)` if the block is already absent or processed).

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

---

## 🔄 Converting Feishu Docs to Local LLM Wiki Markdown

When the user asks to extract a Feishu Document and save it into their local LLM Wiki (`~/.hermes/wiki/_living/` or similar), follow this specific transformation pipeline to bridge the two formats:

1. **Extract Raw Markdown**:
   Use the extraction script to get the Feishu document content:
   `uv run --with requests python <SKILL_DIR>/scripts/extract_docx_to_markdown.py <doc_token>`
   _(For bulk ingest of a folder, use the bundled automation script: `uv run --with requests python <SKILL_DIR>/scripts/batch_ingest_folder.py <folder_token> <absolute_category_path> <comma_separated_tags>`)_
   - **Clean Feishu Artifacts**:
     - **Extract Dates**: Before deleting the Version Table, extract the creation date (first row) and update date (last row) to use in the YAML frontmatter.
     - **Remove the Version Table**: Delete the Markdown table at the top of the document that tracks `Version | Time | Author`. This is a Feishu-specific artifact that pollutes the static wiki. Use a regex to strip it (e.g., `re.sub(r"^\| Col 0.*?\n(?:\|.*?\n)+", "", content, count=1, flags=re.MULTILINE)`).
     - **Remove Native Mentions**: Clean up any `@小聪明蛋` or similar Feishu user mentions, converting them to plain text (e.g., "周琛") or removing them entirely (e.g., `re.sub(r"\[@ou_[a-zA-Z0-9]+\]|@ou_[a-zA-Z0-9]+", "", content)`).

2. **Add Wiki YAML Frontmatter (CRITICAL)**:
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

3. **Save to Wiki**:
   Determine the appropriate subdirectory in `~/.hermes/wiki/_living/` (e.g., `AI-Infrastructure/`, `AI-Applications-and-Ops/`, `TCS-and-Math/`).
   Write the file using `write_file` with lowercase, hyphenated naming: `~/.hermes/wiki/_living/<Category>/<title-with-hyphens>.md`.

4. **Update Wiki Navigation (CRITICAL)**:
   - **Index**: You MUST append a one-line summary and wikilink to `~/.hermes/wiki/index.md` under the appropriate section.
   - **Log**: You MUST append an entry to `~/.hermes/wiki/log.md` recording the ingest action (`## [YYYY-MM-DD] ingest | Feishu Doc: <Title>`).

> **⚠️ Ingest Quality Warning (lesson from ReID ingest, May 2026)**: This bridge transforms _layout_, not _semantics_. The output of this script is RAW Feishu markdown — full of project-internal table names, column names, specific thresholds, gantt charts, single-store experiment results. That is implementation detail, NOT reusable knowledge, and violates the user's Layer 1 principle ("只撰写可复现的知识和技术，不体现具体实现的细节"). After running the script, you MUST manually rewrite the doc to:
>
> 1. Strip all project-internal names (table names like `hidalgo_*`, model node names like `cloth_detection`, config keys like `seq_sn_threshold`);
> 2. Strip all concrete parameter values (specific thresholds, dimensions, time windows, pixel distances);
> 3. Strip all specific effect numbers (specific AUC values, accuracy ranges, dedup rates);
> 4. Strip all specific product/library versions (Milvus / pgvector / Airflow / Spark — keep tech categories, not products);
> 5. Replace project-internal names with generic functional descriptions ("clothing detection model", "config table", "similarity threshold");
> 6. Keep only the reproducible architecture, methodology, design rationale, and qualitative effect descriptions.
>
> Then extract reusable knowledge into Layer 2 `concepts/` or `entities/`, NOT register `_living/` paths in `index.md`'s registry (SCHEMA forbids it — index registers Active Layer 2 only).

## 🎙️ Reading Feishu Minutes (飞书妙记)

Use `minutes/v1/minutes/{token}/transcript` returning PLAIN TEXT, do NOT `.json()`.
Ensure `res.encoding = 'utf-8'`.

## 🔒 Debugging 403 Forbidden Errors (Permission Denied)

When the agent encounters a `1061004 forbidden` or `1770032 forBidden` error while trying to read a Feishu document or folder using the Open API, it indicates the Bot is physically blocked by Feishu's permission model.

### Root Causes

1. **The Target is Not Shared with the Bot:** The user provided a link to a private document or a document inside a folder, but the Bot app was never explicitly added as a reader/collaborator.
2. **Hidden from Search:** Custom enterprise Bot apps are often hidden from the standard "Share/Collaborator" search bar in the Feishu UI, making it impossible for the user to manually type the Bot's name to grant access.

### Resolution Paths to provide the User

Do not just say "I don't have permission." Instruct the user exactly how to bypass the physical isolation:

1. **The Group Chat Bypass (Recommended):**
   - Instruct the user to create a small Feishu group chat containing only the user and the Bot.
   - Tell the user to **share the specific document link** (or folder link) directly into that group chat.
   - _Why it works:_ Bots inherit the read permissions of any document explicitly shared into a group they are a member of.
   - _Pitfall:_ If the user wants you to read a child document inside a folder, they **must** share the direct link to the child document into the group. Sharing only the parent folder link will not recursively grant access to hidden children if the children themselves have strict permission overrides.
2. **The Global Share Override:**
   - Instruct the user to click "Share" on the document and change the Link Sharing settings to **"Tenant Readable"** (组织内获得链接的人可阅读).
   - _Why it works:_ This makes the document public to the entire organization, instantly bypassing the Bot's 403 restriction when it makes API calls.
