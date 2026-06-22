# Downloading Feishu File Attachments

Feishu links in the form `https://whales.feishu.cn/file/TOKEN` are file attachments (not docs), typically `.xlsx`, `.pdf`, etc. The `feishu_doc_read` tool and docx extraction scripts **will not work** on these.

## Download Pattern

Use the `drive/v1/files/:token/download` endpoint:

```python
import feishu_common, requests

token = feishu_common.get_tenant_token()
file_token = "<TOKEN_FROM_URL>"
headers = {"Authorization": f"Bearer {token}"}

url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/download"
res = requests.get(url, headers=headers, allow_redirects=True)

# res.content contains the raw binary file
# Save to disk with the correct extension
```

## Reading Excel Files

After downloading, rename the file with `.xlsx` extension and use `read_file` — Hermes auto-extracts `.xlsx` files to readable text:

```bash
cp downloaded_file /tmp/whatever.xlsx
```

Then `read_file("/tmp/whatever.xlsx")` returns the sheet content as formatted text.

## Pitfall

- The `/open-apis/drive/v1/files/{token}` info endpoint and `/drive/v1/metas/batch_get` may return 404 for chat file tokens. The download endpoint works regardless.
