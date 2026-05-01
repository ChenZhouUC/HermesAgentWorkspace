---
name: feishu-docs
description: "Master guide for Feishu (Lark) Docs: read via Bot API, convert Markdown via Import API, update existing docs (precise indexing, tables), and read Minutes (飞书妙记)."
category: productivity
---

# Feishu (Lark) Docs & Minutes Management

Use this skill whenever you need to read, summarize, create, or update documents in Feishu, as well as read Feishu Minutes.

## 🚨 Critical Rules & Pitfalls

1. **Reading**: **DO NOT** use `browser_navigate` or `web_extract`. Headless browsers hit login walls. Use the Bot API via Python.
2. **Creating from Markdown**: **NEVER parse Markdown manually to use the Blocks API**. The only way to get perfect native formatting is to upload the `.md` file to Feishu Drive and use the `import_tasks` API.
3. **Updating Existing Docs**: **NEVER BLINDLY APPEND (直接 append) to the end.** You MUST "blend" (融入) the new information into existing logical sections by finding the correct integer `index`.
4. **Permissions**: When the Bot creates a document, it owns it. You MUST grant the user Edit/Full Access immediately.
5. **Newlines**: Ensure you properly escape/remove literal `\n` characters before writing text to blocks, otherwise they will render as visible `\n` strings in the document.

---

## 🎙️ Reading Feishu Minutes (飞书妙记)

To read Feishu Minutes (Meetings), use the `minutes/v1/minutes` and `transcript` endpoints.

**Prerequisite:** The app must have the `minutes:minutes` scope granted in the Feishu Developer Console.

1.  **Extract `MINUTE_TOKEN`** from the URL (e.g., `obcn8ktpq4eh85jp821mib7g`, typically 24 chars).
2.  **Execute Python via `execute_code`**:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/.hermes/.env'))
APP_ID = os.getenv('FEISHU_APP_ID')
APP_SECRET = os.getenv('FEISHU_APP_SECRET')

# Get Tenant Access Token
tat_res = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                        json={"app_id": APP_ID, "app_secret": APP_SECRET}).json()
tat = tat_res.get("tenant_access_token")

minute_token = "YOUR_MINUTE_TOKEN_HERE"
headers = {"Authorization": f"Bearer {tat}"}

# Fetch Transcript (Returns Plain Text, NOT JSON)
res = requests.get(f"https://open.feishu.cn/open-apis/minutes/v1/minutes/{minute_token}/transcript", headers=headers)
res.encoding = 'utf-8' # CRITICAL: Fixes Chinese character encoding

if res.status_code == 200:
    print(res.text[:2000]) # The /transcript endpoint returns PLAIN TEXT, do NOT call .json()
else:
    print(f"API Error {res.status_code}: {res.text}")
```

3.  **Fallback Mechanism (No API Permissions):**
    If the API returns `99991672 (Access denied)`, use `browser_navigate` to load the public/shared URL, `browser_click` the "Transcript" tab, and extract the text via `browser_console`:

```javascript
Array.from(document.querySelectorAll("div"))
  .filter((el) => window.getComputedStyle(el).display !== "none" && el.innerText.trim().length > 0)
  .map((e) => e.innerText)
  .join("\\n");
```

---

## 📖 Reading Feishu Documents

1. **Extract `DOC_TOKEN`** from the URL (e.g., `https://domain.feishu.cn/docx/A2KPd...` -> `A2KPd...`).
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

### 1. Upload the file to Drive (Use `curl`)

Python's `urllib` struggles with `multipart/form-data`. Always use `curl`.

```python
import os, json, subprocess, urllib.request
# ... get token ...
root_req = urllib.request.Request("https://open.feishu.cn/open-apis/drive/explorer/v2/root_folder/meta", headers={'Authorization': f'Bearer {token}'})
folder_token = json.loads(urllib.request.urlopen(root_req).read())["data"]["token"]

curl_cmd = ["curl", "-s", "-X", "POST", "https://open.feishu.cn/open-apis/drive/v1/files/upload_all", "-H", f"Authorization: Bearer {token}", "-H", "Content-Type: multipart/form-data", "-F", f"file=@/path/to/file.md", "-F", "file_name=Doc.md", "-F", f"parent_node={folder_token}", "-F", f"size={os.path.getsize('/path/to/file.md')}", "-F", "parent_type=explorer"]
file_token = json.loads(subprocess.check_output(curl_cmd).decode())["data"]["file_token"]
```

### 2. Create Import Task

```python
import_req = urllib.request.Request("https://open.feishu.cn/open-apis/drive/v1/import_tasks", data=json.dumps({"file_extension": "md", "file_token": file_token, "type": "docx", "point": {"mount_type": 1, "mount_key": ""}}).encode(), headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
ticket = json.loads(urllib.request.urlopen(import_req).read())["data"]["ticket"]
```

---

## 🧩 Updating Existing Documents & Precise Indexing

### 1. Precise Insertion Index Calculation

To insert blocks correctly before/after specific sections, you MUST find the integer index within the root document's `children` array.
**Do NOT** use the index from the flat `/blocks` response list!

```python
# Fetch all document blocks with page_size=500
blocks_req = urllib.request.Request(f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks?page_size=500", headers=headers)
all_blocks = json.loads(urllib.request.urlopen(blocks_req).read()).get("data", {}).get("items", [])

# Find root block's children
doc_block = next((b for b in all_blocks if b["block_id"] == doc_token), None)
root_children_ids = doc_block.get("document", {}).get("children", [])

target_phrase = "3. 私有化 Agent"
target_index = -1

# Iterate through root children to find exact insertion index
for i, block_id in enumerate(root_children_ids):
    child_block = next((b for b in all_blocks if b["block_id"] == block_id), None)
    if child_block and target_phrase in json.dumps(child_block, ensure_ascii=False):
        target_index = i
        break

# Insert at the calculated integer index
new_blocks_payload = {
    "index": target_index if target_index != -1 else len(root_children_ids),
    "children": [{"block_type": 2, "text": {"elements": [{"text_run": {"content": "New Content"}}]}}]
}
# POST to /blocks/{doc_token}/children
```

### 2. Bulk Index Shifting (400/429 Error Fix)

If you insert multiple sections at different places:

1. Calculate all integer indices _first_.
2. Sort the indices in **descending** (reverse) order.
3. Insert from bottom to top so index shifting doesn't break subsequent inserts.

### 3. Updating Text/Headings (Error 400 Fix)

When patching existing text blocks, you **MUST** use `update_text_elements`.

```python
{"update_text_elements": {"elements": [{"text_run": {"content": "New Text"}}]}}
```

Ultimate Fallback: `POST` new block, then `batch_delete` old block.

### 4. Complex Lists & Tables (1770001 Fix)

- **Lists:** Do NOT fallback to fake text bullets (`•`). Ensure payload matches native list schema exactly (Block type 12/13).
- **Tables:** Table's `children` array is a flattened 1D array of Cell blocks (not rows).
- **Row Limit:** Max 9 rows per `POST`. For more, split into consecutive tables.
- **Empty Cell Quirk:** Feishu pre-populates new cells with empty Text blocks. Delete or `batch_update` them when populating table cells.

### 5. Version Table Standard Template

- **Format**: `Version` | `Time` | `Author`
- `YYYYMMDD.XXed` | `YYYY-MM-DD HH:MM:SS UTC+8` | native `@小聪明蛋` mention
- Column Widths: `[150, 250, 150]`

### 6. Math Equations (LaTeX)

Render formulas natively using the `equation` element inside any text block:
`{"equation": {"content": "\\tau^* = \\arg\\max_{\\tau} (TPR(\\tau) - FPR(\\tau))"}}`
