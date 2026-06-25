# Reading Feishu Sheets (Spreadsheets) via Open API

Links in the form `https://domain.feishu.cn/sheets/TOKEN` are native Feishu Spreadsheets (电子表格). **Neither `feishu_doc_read` nor the docx extraction scripts work on sheet tokens** — they return `1770002 not found`.

## API Pattern

### 1. Get Tenant Access Token

```python
import feishu_common
token = feishu_common.get_tenant_token()
```

### 2. List Sheets (Query Sheet Metadata)

The v3 `/sheets` endpoint may return 404. Use `/sheets/query` instead:

```python
import urllib.request, json

sheet_token = "<TOKEN_FROM_URL>"
url = f"{API}/sheets/v3/spreadsheets/{sheet_token}/sheets/query"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())

sheets = data["data"]["sheets"]
for s in sheets:
    print(s["title"], s["sheet_id"])  # e.g. "指标", "0rMOqI"
```

### 3. Read Cell Values

Use the v2 values API. Note the `%21` encoding for `!` in the range:

```python
sheet_id = "0rMOqI"  # from step 2
url = f"{API}/sheets/v2/spreadsheets/{sheet_token}/values/{sheet_id}%21A1:Z300"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read())
values = data["data"]["valueRange"]["values"]

for row in values:
    while len(row) < 9:
        row.append(None)
    print("\t".join(str(c) if c else "" for c in row[:9]))
```

### 4. Alternative: Download as Excel File

You can also download the sheet as an `.xlsx` file and use `read_file` (which auto-extracts):

```python
# Download via Drive API
url = f"{API}/drive/v1/files/{sheet_token}/download"
res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, allow_redirects=True)
# Save as .xlsx and read_file auto-extracts
```

## Permission Fallback

If the bot lacks permission, both Sheets APIs and Drive download will return `1061004 forbidden` or `1770032 forBidden`. Resolution: share the sheet link into a group chat containing the bot, or set link sharing to "Tenant Readable".

**Why a Docx link can read while a Sheet needs setup**: the `feishu_doc_read` native tool uses a different permission channel (likely a _user_ token), so a Docx may read even when the bot's _tenant_ token has no grant. The Sheets API here always uses the **tenant** token, so it only succeeds when the bot itself has been granted access. Sharing a Docx link into a group can incidentally extend the bot's grant to other files in the same folder — including sheets — which is why a Sheet sometimes becomes readable after an unrelated Docx share.
