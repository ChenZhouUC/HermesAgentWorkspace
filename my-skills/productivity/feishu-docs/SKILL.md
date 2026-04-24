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
        key = {1: "text", 2: "heading1", 3: "heading2", 4: "heading3", 11: "bullet", 12: "ordered", 13: "code"}.get(b_type, "text")
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

- **Read First:** Always fetch the children list first to find the correct logical insertion index.
- **Append to End:** Omit the `index` key entirely in the `POST` payload. Providing an invalid/out-of-bounds index throws `1770001 invalid param`.
- **Insert at Location:** Provide the exact integer `index`.

### 2. Updating Text/Headings (Error 400 Fix)

When patching existing text/heading blocks, **do not** use `replace_elements`. You **MUST** use `update_text_elements`.

```python
# PATCH payload to update a heading or text block:
{
    "update_text_elements": {
        "elements": [{"text_run": {"content": "New Text"}}]
    }
}
```

**Ultimate Fallback:** If `PATCH` still fails with 400 (e.g., when trying to fix corrupted characters like literal `\n` that break validation), bypass the update entirely: `POST` a brand new block with the corrected text at the same `index`, then `DELETE` the old block via `batch_delete`.

### 3. Complex Lists (Error 1770001 Fix)

Creating complex Bullet (`12`) or Numbered Lists (`14`) via API often fails strict validation.
**Workaround:** Downgrade the list blocks to standard Text blocks (`block_type: 2`) and manually prepend bullet characters (`• `) or numbers (`1. `).

### 4. Tables: Appending Rows & Blank Cell Fix

You **cannot** append a row directly to a table. You must:

1. Recreate a **new** table block with `row_size` incremented. Schema quirk: `row_size`, `column_size`, `column_width` go inside the `property` object.
2. Fill the new table with old + new data.
3. **Empty Cell Quirk:** Feishu pre-populates new cells with an empty Text block. When you insert your content, call `batch_delete` (`start_index: 0, end_index: 1`) on the cell's children to remove the blank line.
4. Delete the old table using `batch_delete`. (Remember to sort indices in reverse order when deleting multiple blocks).

### 5. Version Table Standard Template

- **Header**: Version | Time | Author
- **Version Format**: `YYYYMMDD.XXed` (e.g., `20260424.01ed`)
- **Time Format**: `YYYY-MM-DD HH:MM:SS UTC+8`
- **Author**: Must use native `@小聪明蛋` mention (`{"mention_user": {"user_id": bot_open_id}}`)
- **Column Widths**: `[150, 250, 150]` (Prevents timestamp wrapping).
