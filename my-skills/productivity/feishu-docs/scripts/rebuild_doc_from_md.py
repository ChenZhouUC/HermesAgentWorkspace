"""Rebuild a Feishu document from scratch: clear content, set title, create version table, import markdown.

Usage: python rebuild_doc_from_md.py <target_doc_token> <md_file_path>
Requires FEISHU_APP_ID and FEISHU_APP_SECRET env vars.
"""

import os, sys, json, time, subprocess, urllib.request, urllib.error
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_markdown_blocks import merge_docs

APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")


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
        f"size={str(file_size)}",
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


def rebuild(doc_token, md_file, title=None):
    token = get_token()

    # 1. Clear old content
    res = do_req(token, f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}")
    children = res["data"]["block"].get("children", [])
    if children:
        print(f"Clearing {len(children)} blocks...")
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": len(children)},
        )

    # 2. Update Title
    title = title or "Document Title"
    print(f"Setting title: {title}")
    do_req(
        token,
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}",
        method="PATCH",
        payload={"update_text_elements": {"elements": [{"text_run": {"content": title}}]}},
    )

    # 3. Create Version Table at index 0
    print("Creating Version Table...")
    table_payload = {
        "block_type": 31,
        "table": {"property": {"row_size": 2, "column_size": 3, "column_width": [150, 250, 150]}},
    }
    res_table = do_req(
        token,
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
        method="POST",
        payload={"children": [table_payload], "index": 0},
    )
    cells = res_table["data"]["children"][0]["table"]["cells"]

    bot_id = "ou_0091f5c50226a4ee0dc8a6d51665db0f"
    texts = [
        [{"text_run": {"content": "Version"}}],
        [{"text_run": {"content": "Time"}}],
        [{"text_run": {"content": "Author"}}],
        [{"text_run": {"content": "1.0"}}],
        [{"text_run": {"content": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}],
        [{"mention_user": {"user_id": bot_id}}],
    ]

    for i, cell_id in enumerate(cells):
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{cell_id}/children",
            method="POST",
            payload={"children": [{"block_type": 2, "text": {"elements": texts[i]}}], "index": -1},
        )
        # Delete default empty text block in cell
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{cell_id}/children/batch_delete",
            method="DELETE",
            payload={"start_index": 0, "end_index": 1},
        )

    # 4. Import and merge Markdown
    print("Importing Markdown...")
    file_token = upload_file(token, md_file)
    ticket = create_import_task(token, file_token)
    temp_doc = poll_import_task(token, ticket)

    print(f"Merging blocks from temp doc {temp_doc} into {doc_token}...")
    merge_docs(token, temp_doc, doc_token)
    print("Done!")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python rebuild_doc_from_md.py <doc_token> <md_file> [title]")
        sys.exit(1)
    doc_token = sys.argv[1]
    md_file = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else None
    rebuild(doc_token, md_file, title)
