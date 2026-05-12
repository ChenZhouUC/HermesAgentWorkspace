---
name: feishu-docs
description: "Master guide for Feishu (Lark) Docs: read via Bot API, convert Markdown via Import API, update existing docs (precise indexing, tables, mentions), and read Minutes."
category: productivity
---

# Feishu (Lark) Docs & Minutes Management

Use this skill whenever you need to read, summarize, create, or update documents in Feishu, as well as read Feishu Minutes.

## 🚨 Critical Rules & Pitfalls

1. **Title & Formatting**: Always ensure the document has a professional Chinese/English title (e.g., "L20 vs RTX 5880 Ada: Parameters"). DO NOT use Markdown file names (no `.md` suffix in the doc title). When uploading via `curl`, the `file_name` parameter becomes the document title.
2. **Raw URLs Only (CRITICAL)**: When sending the final document URL to the user in Feishu chat, **always include the raw, unformatted URL string** (e.g., `https://domain.feishu.cn/docx/XYZ...`). If you only use Markdown hyperlink syntax (`[text](url)`), the Feishu client often strips or hides the link.
3. **References**: ALWAYS append a `## References` section formatted in Chicago style at the bottom of the document if you used any external search information.
4. **Bot Native Mention**: The user expects a native Feishu mention card for the author (e.g., `@小聪明蛋`), not plain text. For the bot, `小聪明蛋`'s `open_id` is `ou_0091f5c50226a4ee0dc8a6d51665db0f`. You must POST or PATCH text elements with `{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}` instead of a plain text `@...`.
5. **Creating from Markdown**: **NEVER parse Markdown manually to use the Blocks API**. The only way to get perfect native formatting is to upload the `.md` file to Feishu Drive and use the `import_tasks` API.
6. **Updating Existing Docs**: **NEVER BLINDLY APPEND** to the end. You MUST "blend" the new information into existing logical sections by finding the correct integer `index`.

---

## ✍️ Creating: Markdown to Perfect Feishu Docx

### 1. Upload the file to Drive (Use `curl`)

**CRITICAL FIX**: Feishu's Import API strictly checks the `file_name` extension during upload. You MUST upload it with a `.md` extension (e.g. `file_name=temp.md`).
_Do not_ attempt to set the professional title during the curl upload.

```python
curl_cmd = ["curl", "-s", "-X", "POST", "https://open.feishu.cn/open-apis/drive/v1/files/upload_all", "-H", f"Authorization: Bearer {token}", "-H", "Content-Type: multipart/form-data", "-F", f"file=@/path/to/file.md", "-F", "file_name=temp.md", "-F", f"parent_node={folder_token}", "-F", f"size={os.path.getsize('/path/to/file.md')}", "-F", "parent_type=explorer"]
# ...
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

### 3. Granting Permissions (Public Link Sharing)

Use the `v1` permissions API (`drive/v1/permissions/{doc_token}/public?type=docx`).

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
2. Create a NEW Table block. **CRITICAL:** Do NOT include a `children` array in the table payload! Let Feishu auto-create the cells.

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

---

## 🎙️ Reading Feishu Minutes (飞书妙记)

Use `minutes/v1/minutes/{token}/transcript` returning PLAIN TEXT, do NOT `.json()`.
Ensure `res.encoding = 'utf-8'`.
