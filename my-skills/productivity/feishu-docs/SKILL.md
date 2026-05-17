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

---

## ✍️ Creating: Markdown to Perfect Feishu Docx

### 1. Upload the file to Drive (Use `curl` NOT `requests`)

**CRITICAL FIX**: Feishu's Import API strictly checks the `file_name` extension during upload. You MUST upload it with a `.md` extension (e.g. `file_name=temp.md`).
_Do not_ attempt to set the professional title during the curl upload.
**CRITICAL FIX 2**: Using `requests` with `multipart/form-data` for the upload API often fails with `1061002 params error` or boundaries issues. You MUST use the `curl` CLI through `subprocess` for the upload step.

```python
file_size = os.path.getsize(file_path)
curl_cmd = [
    "curl", "-s", "-X", "POST",
    "https://open.feishu.cn/open-apis/drive/v1/files/upload_all",
    "-H", f"Authorization: Bearer {token}",
    "-H", "Content-Type: multipart/form-data",
    "-F", f"file=@{file_path}",
    "-F", "file_name=temp.md",
    "-F", f"size={file_size}",
    "-F", "parent_type=explorer",
    "-F", "parent_node=" # empty string for personal space root
]
```

### 1.5 Rename the Document Title (Post-Creation)

Because you uploaded it as `temp.md`, the resulting document title will be `temp`. You must rename it by PATCHing the root block (the block whose ID is the `doc_token`).

```python
title_payload = {
    "update_text_elements": {
        "elements": [{"text_run": {"content": "Professional Title Here"}}]
    }
}
title_req = urllib.request.Request(
    f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}",
    data=json.dumps(title_payload).encode(),
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    method='PATCH'
)
urllib.request.urlopen(title_req)
```

### 2. Create and Poll Import Task (Same as before)

### 3. Granting Permissions (Tenant Editable & Public)

**USER RULE:** The user explicitly forbids creating new standalone documents (`NEVER create new docs`), strongly preferring to revise existing docs in-place.
If you absolutely MUST create a new document (e.g., explicitly forced), you MUST explicitly grant edit permissions so the user isn't locked out.
PATCH to `https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_token}/public?type=docx`

```json
{
  "external_access_entity": "anyone_can_edit",
  "security_entity": "anyone_can_view",
  "comment_entity": "anyone_can_view",
  "share_entity": "anyone",
  "link_share_entity": "tenant_editable"
}
```

### 4. Native Mention Fix (Post-Creation)

Because Markdown import converts `@小聪明蛋` into plain text, fetch the block containing it and PATCH it:

```python
payload = {"update_text_elements": {"elements": [{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}]}}
# PATCH to /blocks/{block_id}
```

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
5. Use `batch_delete` (as shown above) to delete the old table block from the document, and delete the default empty text block (index 0) from each new cell.

### 3. Complex Lists (1770001 Fix)

- Do NOT fallback to fake text bullets (`•`).
- When POSTing a list, the payload is `{"block_type": 12, "bullet": {"elements": [...]}}` (Note the key is `bullet` or `ordered`, NOT `text`).

### 4. Updating Text/Headings (Error 400 Fix)

When patching existing text blocks, you **MUST** use `update_text_elements`:
`{"update_text_elements": {"elements": [{"text_run": {"content": "New Text"}}]}}`

### 5. Copying Content (Import Temp Doc -> Existing Doc)

To merge large Markdown content into an existing document with perfect native formatting:

1. Import the MD file via `import_tasks` to a temporary document.
2. Read all blocks from the temp document.
3. Build a hierarchical POST payload for the target document.
   - **Strip all `block_id`s.**
   - **Tables:** ONLY copy `row_size`, `column_size`, and `column_width`. Do NOT include `cells` or `merge_info` in the payload. Split tables if they exceed the 9-row limit.
4. Insert top-level blocks in chunks (e.g., 40 at a time) to avoid payload size/timeout errors.
5. Re-map the newly created auto-generated cell IDs and sequentially POST their nested children. (See `scripts/merge_markdown_blocks.py` for a robust implementation of this exact block-mapping and table-splitting workflow).

---

## 📖 Reading Feishu Docs (Fallback)

If the native `feishu_doc_read` tool fails with `Feishu client not available (not in a Feishu comment context)`, use the bundled extraction scripts via the Open API.

- **Canonical extractor**: `python <SKILL_DIR>/scripts/extract_docx_to_markdown.py <doc_token>`
  Handles nested blocks, tables, lists, and wiki-token-to-doc-token resolution automatically.
- **Lightweight fallback**: `python <SKILL_DIR>/scripts/read_docx_to_markdown.py <doc_token>`
  Useful when you only need a straightforward block dump to Markdown.
- **Compatibility helper**: `python <SKILL_DIR>/scripts/download_docx_to_md.py <doc_token>`
  Keeps older workflows working when the lightweight extraction path is sufficient.
- **Wiki vs Docx Pitfall**: If the target URL is a Feishu Wiki link (`https://domain.feishu.cn/wiki/TOKEN`), the application MUST have `wiki:wiki:readonly` or `wiki:node:read` permissions. If it only has document permissions, the API will reject it with a `99991672 Access denied` error. Ask the user to grant the Wiki scope or provide the underlying standard `.docx` link.

## 🎙️ Reading Feishu Minutes (飞书妙记)

Use `minutes/v1/minutes/{token}/transcript` returning PLAIN TEXT, do NOT `.json()`.
Ensure `res.encoding = 'utf-8'`.
