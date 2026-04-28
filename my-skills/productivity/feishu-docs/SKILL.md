---
name: feishu-docs
description: "Master guide for Feishu (Lark) Docs: read via Bot API, convert Markdown via Import API, update existing docs (inserting, blending, tables), and handle API gotchas."
category: productivity
---

# Feishu (Lark) Docs Management

Use this skill whenever you need to read, summarize, create, or update documents in Feishu.

## 🚨 Critical Rules & Pitfalls

1. **Reading**: **DO NOT** use `browser_navigate` or `web_extract`. Headless browsers hit login walls. Use the Bot API via Python.
2. **Creating from Markdown**: **NEVER parse Markdown manually to use the Blocks API**. The only way to get perfect native formatting is to upload the `.md` file to Feishu Drive and use the `import_tasks` API.
3. **Updating Existing Docs**: **NEVER BLINDLY APPEND (直接 append) to the end.** You MUST "blend" (融入) the new information into existing logical sections by finding the correct integer `index`.
4. **Permissions**: When the Bot creates a document, it owns it. You MUST grant the user Edit/Full Access immediately.
5. **Newlines**: Ensure you properly escape/remove literal `\n` characters before writing text to blocks, otherwise they will render as visible `\n` strings in the document.

---

## 🎙️ Reading Feishu Minutes (飞书妙记)

### Reading Feishu Minutes (Meetings)

To read Feishu Minutes (Meetings), use the `minutes/v1/minutes` and `transcript` endpoints.

**Prerequisite:** The app must have the `minutes:minutes` scope granted in the Feishu Developer Console.

1.  **Get basic metadata (Title, Duration, URL):**
    `GET https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}`
    _The `minute_token` is the 24-character string at the end of the URL (e.g., `obcn8ktpq4eh85jp821mib7g`)._

2.  **Get the full transcript (Speaker separation, exact words):**
    `GET https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}/transcript`
    - **Crucial:** Use `response.encoding = 'utf-8'` before reading `response.text` in Python `requests`, as the response may contain raw UTF-8 bytes that `requests` misinterprets, leading to garbled Chinese text or `JSONDecodeError` if attempting `.json()` directly.
    - The `/summary` endpoint is deprecated/unreliable (often returns 404), so parse the `transcript` text directly to generate your own AI summaries.

3.  **Fallback Mechanism (No API Permissions):**
    If the API returns `99991672 (Access denied)`, it means the app lacks the `minutes:minutes` scope. If the user cannot grant this permission but the link is accessible to anyone in the workspace, you can use the **browser tool** (`browser_navigate`) to visit the URL, use `browser_click` on the "Show More" or "Transcript" tabs, and extract the visible DOM text using `browser_console` as a workaround.

**Fallback Strategy (Browser Scraping):**

1. Use `browser_navigate` to load the public/shared URL.
2. Find the "Show More" button (for AI Notes or Transcripts) in the `browser_snapshot` and `browser_click` it.
3. The DOM hides content with anti-scraping `display: none` elements. Use `browser_console` to extract only the visible text:

```javascript
Array.from(document.querySelectorAll("div"))
  .filter((el) => {
    const styles = window.getComputedStyle(el);
    return styles.display !== "none" && el.innerText.trim().length > 0;
  })
  .map((e) => e.innerText)
  .join("\\n");
```

---

## 📖 Reading Feishu Documents

1. **Extract `DOC_TOKEN`** from the URL (e.g., `https://domain.feishu.cn/docx/A2KPd...` -> `A2KPd...`). _For `/wiki/` URLs, pass the token directly to the `/docx/v1/documents` API to bypass `wiki:node:read` permission issues._
2. **Execute Python via `execute_code`**:

```python
import os, json, urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.hermes/.env"))
app_id, app_secret = os.getenv("FEISHU_APP_ID"), os.getenv("FEISHU_APP_SECRET")
doc_token = "REPLACE_WITH_ACTUAL_TOKEN"

req = urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(), headers={"Content-Type": "application/json"})
token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]

docs_req = urllib.request.Request(f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks", headers={"Authorization": f"Bearer {token}"})
blocks = json.loads(urllib.request.urlopen(docs_req).read()).get("data", {}).get("items", [])

content = []
for block in blocks:
    b_type = block.get("block_type")
    if b_type in range(1, 16):
        key = {2: "text", 3: "heading1", 4: "heading2", 5: "heading3", 12: "bullet", 13: "ordered", 14: "code", 31: "table"}.get(b_type, "text")
        text = "".join([el.get("text_run", {}).get("content", "") for el in block.get(key, {}).get("elements", [])])
        if text.strip(): content.append(text)

print("\\n".join(content) if content else "Empty document.")
```

---

## ✍️ Creating: Markdown to Perfect Feishu Docx

### 1. Upload the file to Drive (Use `curl` via `subprocess`)

Python's `urllib` struggles with `multipart/form-data`. Always use `curl`. If generating Markdown dynamically, write it to a file _inside the same `execute_code` script_ first.

```python
import os, json, time, subprocess, urllib.request
# ... get token ...
root_req = urllib.request.Request("https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta", headers={'Authorization': f'Bearer {token}'})
folder_token = json.loads(urllib.request.urlopen(root_req).read())["data"]["token"]

curl_cmd = ["curl", "-s", "-X", "POST", "https://open.feishu.cn/open-apis/drive/v1/files/upload_all", "-H", f"Authorization: Bearer {token}", "-H", "Content-Type: multipart/form-data", "-F", f"file=@/path/to/file.md", "-F", "file_name=Doc.md", "-F", f"parent_node={folder_token}", "-F", f"size={os.path.getsize('/path/to/file.md')}", "-F", "parent_type=explorer"]
file_token = json.loads(subprocess.check_output(curl_cmd).decode())["data"]["file_token"]
```

### 2. Create Import Task & Grant Permissions

```python
import_req = urllib.request.Request("https://open.feishu.cn/open-apis/drive/v1/import_tasks", data=json.dumps({"file_extension": "md", "file_token": file_token, "type": "docx", "point": {"mount_type": 1, "mount_key": ""}}).encode(), headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
ticket = json.loads(urllib.request.urlopen(import_req).read())["data"]["ticket"]

# Poll for completion...
# ... grant edit permission to user/openchat ...
```

---

## 🧩 Updating Existing Documents & Workarounds

### 1. Inserting/Appending Content

- **Max 50 Limit:** A single `POST .../blocks/{block_id}/children` request can insert a maximum of 50 blocks. If you have more, you MUST chunk the `children` array (e.g., 45 at a time) and send multiple sequential requests.
- **Bulk Errors:** If a bulk insertion fails with `400` or `1770001`, test inserting the blocks one-by-one. Feishu will reject the entire batch if a single block has an invalid `block_type` or schema mismatch (e.g. a typo in `block_type: 12` vs `11`).
- **Read First:** Always fetch the parent's `children` array to find the correct logical insertion index. To insert _before_ a specific block, use `index = parent_children.index(target_block_id)`.
- **Append to End:** Omit the `index` key entirely in the `POST` payload. Providing an invalid/out-of-bounds index throws `1770001 invalid param`.
- **Insert at Location & Bulk Index Shifting (400/429 Error Fix):** Provide the exact integer `index`. **CRITICAL:** When inserting multiple blocks at different locations, inserting a block shifts the indices of all subsequent blocks, which will cause `400 Bad Request` or place blocks in the wrong sections. You MUST:
  1. Calculate all target integer indices _first_.
  2. Sort the target indices in **descending** (reverse) order.
  3. Insert from bottom to top so that index shifting only affects the bottom (already processed) parts of the document.
  4. Add a slight delay (e.g., `time.sleep(0.5)`) between API calls to prevent `429 Too Many Requests` when doing bulk insertions.

### 2. Updating Text/Headings (Error 400 Fix)

When patching existing text/heading blocks, **do not** use `replace_elements` or `replace_text`. You **MUST** use `update_text_elements` (wrong keys cause `400 Bad Request`).

```python
# PATCH payload to update a heading or text block:
{
    "update_text_elements": {
        "elements": [{"text_run": {"content": "New Text"}}]
    }
}
```

**Ultimate Fallback:** If `PATCH` still fails with 400 (e.g., when trying to fix corrupted characters like literal `\n` that break validation), bypass the update entirely: `POST` a brand new block with the corrected text at the same `index`, then delete the old block via `batch_delete` (requires HTTP `DELETE` to `/blocks/{parent_id}/children/batch_delete` with a JSON payload `{"start_index": int, "end_index": int}`, where `end_index` is exclusive).

### 3. Complex Lists (Error 1770001 Fix)

Creating native Bullet (`12`) or Ordered Lists (`13`) via the `children` POST API often fails with `1770001 invalid param` due to strict nested element validation.
**CRITICAL User Preference:** The user STRICTLY prefers **native list blocks** (`12` for bullet, `13` for ordered) over fake text bullets (like `• `). Do NOT fallback to text blocks. Ensure your payload exactly matches the nested schema:

```json
{ "block_type": 12, "bullet": { "elements": [{ "text_run": { "content": "Text" } }] } }
```

If you encounter manually typed fake bullets in a document, convert them to native list blocks to maintain strict formatting consistency.

### 4. Tables: Structure, Appending & Blank Cell Fix

**CRITICAL Structure Quirk:** A Table block's `children` array does NOT contain Row blocks. It directly contains the **Cell blocks** (`block_type: 34`) in a flattened, row-major 1D array. For a 2x3 table, `children[0..2]` are Row 0, and `children[3..5]` are Row 1. Do not try to index into rows.

You **cannot** append a row directly to a table. You must:

1. Recreate a **new** table block with `row_size` incremented. Schema quirk: `row_size`, `column_size`, `column_width` go inside the `property` object.
2. Fill the new table with old + new data by iterating over the flattened cell array.
3. **Empty Cell Quirk:** Feishu pre-populates new cells with an empty Text block. When you insert your content into a cell (`POST .../blocks/{cell_id}/children`), you should delete the default empty text block to remove the blank line.
   - **Best Practice for New Tables (e.g. Version Table):** Instead of inserting new blocks and deleting the empty ones, update the empty text blocks directly via `batch_update`. Fetch the new table's cells, then for each `cell_id`, fetch its children (`GET .../blocks/{cell_id}/children`) to reliably get the pre-populated empty text block ID. Then send a `PATCH .../blocks/batch_update` with `update_text_elements` for each text block. This avoids the 400 Bad Request issues common with `batch_get`.
4. Delete the old table using `batch_delete` on the parent's children (HTTP `DELETE` with `{"start_index": int, "end_index": int}` payload).
   - **CRITICAL Index Shift Pitfall**: If you inserted the new table at the `old_table_index`, the old table has been shifted down to `old_table_index + 1`. You MUST use `start_index: old_table_index + 1, end_index: old_table_index + 2` to avoid accidentally deleting your newly inserted table!

### 5. Version Table Standard Template

- **Header**: Version | Time | Author
- **Version Format**: `YYYYMMDD.XXed` (e.g., `20260424.01ed`)
- **Time Format**: `YYYY-MM-DD HH:MM:SS UTC+8`
- **Author**: Must use native `@小聪明蛋` mention (`{"mention_user": {"user_id": bot_open_id}}`)
- **Column Widths**: `[150, 250, 150]` (Prevents timestamp wrapping).

### 6. Math Equations (LaTeX)

You can natively render mathematical formulas in Feishu Docs using the `equation` element inside any text, bullet, or heading block. This is highly recommended to improve professionalism.

- Place `{"equation": {"content": "LaTeX_string"}}` alongside `{"text_run": ...}` inside the `elements` array.
- **Example Payload:**

```json
{
  "block_type": 12,
  "bullet": {
    "elements": [
      { "text_run": { "content": "The threshold is determined by: " } },
      { "equation": { "content": "\\tau^* = \\arg\\max_{\\tau} (TPR(\\tau) - FPR(\\tau))" } }
    ]
  }
}
```
