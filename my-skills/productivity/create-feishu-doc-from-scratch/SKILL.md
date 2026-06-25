---
name: create-feishu-doc-from-scratch
description: "Create a new Feishu document directly from scratch with proper tenant token auth, without using the legacy python scripts that rely on local python environments."
---

# Create Feishu Doc Directly

Uses the Open API to create a new `.docx` file in Feishu Drive.

```python
import os, json, urllib.request

API = "https://open.feishu.cn/open-apis"

def get_creds():
    env_path = os.path.expanduser("~/.hermes/.env")
    creds = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and ("FEISHU_APP_ID" in line or "FEISHU_APP_SECRET" in line):
                    key, val = line.split("=", 1)
                    creds[key] = val
    return creds.get("FEISHU_APP_ID", ""), creds.get("FEISHU_APP_SECRET", "")

def get_token(app_id, app_secret):
    url = f"{API}/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(
        url,
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())["tenant_access_token"]

def create_docx(token, title):
    url = f"{API}/docx/v1/documents"
    req = urllib.request.Request(
        url,
        data=json.dumps({"title": title}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())["data"]["document"]["document_id"]
```
