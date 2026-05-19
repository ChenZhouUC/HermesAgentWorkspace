import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

# Add Feishu skill scripts to path to import merge_docs
sys.path.append("/Users/chenzhou/.hermes/my-skills/productivity/feishu-docs")
from scripts.merge_markdown_blocks import merge_docs

APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")
DOC_TOKEN = "Imptd3epcoWJ5AxKOUncUBWvnYc"
MD_FILE = "/Users/chenzhou/.hermes/tmp/m5_migration_handbook_v2.md"


def do_req(token, url, method="GET", payload=None):
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method=method
    )
    if payload:
        req.data = json.dumps(payload).encode()
    for _ in range(3):
        try:
            return json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2)
                continue
            print(e.read().decode())
            raise e


def get_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = urllib.request.Request(
        url,
        data=json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]


def upload_file(token, file_path):
    file_size = os.path.getsize(file_path)
    curl_cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        "https://open.feishu.cn/open-apis/drive/v1/files/upload_all",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Content-Type: multipart/form-data",
        "-F",
        f"file=@{file_path}",
        "-F",
        "file_name=temp.md",
        "-F",
        f"size={file_size}",
        "-F",
        "parent_type=explorer",
        "-F",
        "parent_node=",
    ]
    res = subprocess.check_output(curl_cmd)
    return json.loads(res)["data"]["file_token"]


def create_import_task(token, file_token):
    url = "https://open.feishu.cn/open-apis/drive/v1/import_tasks"
    payload = {
        "file_extension": "md",
        "file_token": file_token,
        "type": "docx",
        "point": {"mount_type": 1, "mount_key": ""},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())["data"]["ticket"]


def poll_import_task(token, ticket):
    url = f"https://open.feishu.cn/open-apis/drive/v1/import_tasks/{ticket}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    while True:
        res = json.loads(urllib.request.urlopen(req).read())
        status = res["data"]["result"]["job_status"]
        if status == 0:
            return res["data"]["result"]["token"]
        elif status not in (1, 2):
            raise Exception(f"Import failed: {res}")
        time.sleep(1)


def rebuild():
    token = get_token()

    # 1. Clear old content
    res = do_req(token, f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{DOC_TOKEN}")
    children = res["data"]["block"].get("children", [])
    if children:
        print(f"Clearing {len(children)} blocks...")
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{DOC_TOKEN}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": len(children)},
        )

    # 2. Update Title
    print("Updating title...")
    do_req(
        token,
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{DOC_TOKEN}",
        method="PATCH",
        payload={
            "update_text_elements": {
                "elements": [{"text_run": {"content": "M5 Migration Handbook: Zero-Friction Transfer"}}]
            }
        },
    )

    # 3. Create Version Table
    print("Creating Version Table...")
    table_payload = {
        "block_type": 31,
        "table": {"property": {"row_size": 2, "column_size": 3, "column_width": [150, 250, 150]}},
    }
    res_table = do_req(
        token,
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{DOC_TOKEN}/children",
        method="POST",
        payload={"children": [table_payload], "index": -1},
    )
    cells = res_table["data"]["children"][0]["table"]["cells"]

    texts = [
        [{"text_run": {"content": "Version"}}],
        [{"text_run": {"content": "Time"}}],
        [{"text_run": {"content": "Author"}}],
        [{"text_run": {"content": "1.0"}}],
        [{"text_run": {"content": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}],
        [{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}],
    ]

    for i, cell_id in enumerate(cells):
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{cell_id}/children",
            method="POST",
            payload={"children": [{"block_type": 2, "text": {"elements": texts[i]}}], "index": -1},
        )
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{DOC_TOKEN}/blocks/{cell_id}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": 1},
        )

    # 4. Import and merge Markdown
    print("Importing Markdown...")
    file_token = upload_file(token, MD_FILE)
    ticket = create_import_task(token, file_token)
    temp_doc = poll_import_task(token, ticket)

    print("Merging blocks...")
    merge_docs(token, temp_doc, DOC_TOKEN)
    print("Done!")


if __name__ == "__main__":
    rebuild()
