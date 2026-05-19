import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.parse

from scripts.merge_markdown_blocks import merge_docs

APP_ID = os.environ.get("FEISHU_APP_ID")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET")


def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    res = json.loads(urllib.request.urlopen(req).read())
    return res["tenant_access_token"]


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
    data = json.loads(res)
    return data["data"]["file_token"]


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
    res = json.loads(urllib.request.urlopen(req).read())
    return res["data"]["ticket"]


def poll_import_task(token, ticket):
    url = f"https://open.feishu.cn/open-apis/drive/v1/import_tasks/{ticket}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    while True:
        res = json.loads(urllib.request.urlopen(req).read())
        status = res["data"]["result"]["job_status"]
        if status == 0:
            return res["data"]["result"]["token"]
        elif status != 1 and status != 2:
            raise Exception(f"Import failed: {res}")
        time.sleep(1)


def do_import():
    target_doc = "Imptd3epcoWJ5AxKOUncUBWvnYc"
    md_file = "/Users/chenzhou/.hermes/tmp/m5_migration_handbook.md"

    print("Getting token...")
    token = get_tenant_access_token()
    print("Uploading file...")
    file_token = upload_file(token, md_file)
    print("Creating import task...")
    ticket = create_import_task(token, file_token)
    print("Polling import task...")
    temp_doc = poll_import_task(token, ticket)
    print(f"Temp doc created: {temp_doc}, merging into {target_doc}...")
    merge_docs(token, temp_doc, target_doc)
    print("Merge complete.")


if __name__ == "__main__":
    do_import()
