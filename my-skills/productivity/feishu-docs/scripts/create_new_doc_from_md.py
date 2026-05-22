import os
import sys
import json
import urllib.request
import subprocess
import time
import re


def get_tenant_access_token():
    with open(os.path.expanduser("~/.hermes/.env"), "r") as f:
        env_content = f.read()
    app_id = re.search(r"FEISHU_APP_ID=(.*)", env_content).group(1).strip()
    app_secret = re.search(r"FEISHU_APP_SECRET=(.*)", env_content).group(1).strip()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]


def create_doc(md_path, title):
    token = get_tenant_access_token()
    size = os.path.getsize(md_path)

    print(f"Uploading {md_path}...")
    cmd = [
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
        f"file=@{md_path}",
        "-F",
        "file_name=temp.md",
        "-F",
        f"size={size}",
        "-F",
        "parent_type=explorer",
        "-F",
        "parent_node=",
    ]
    f_token = json.loads(subprocess.check_output(cmd))["data"]["file_token"]

    print("Creating import task...")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/drive/v1/import_tasks",
        data=json.dumps(
            {"file_extension": "md", "file_token": f_token, "type": "docx", "point": {"mount_type": 1, "mount_key": ""}}
        ).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    ticket = json.loads(urllib.request.urlopen(req).read())["data"]["ticket"]

    print("Polling import task...")
    while True:
        req = urllib.request.Request(
            f"https://open.feishu.cn/open-apis/drive/v1/import_tasks/{ticket}",
            headers={"Authorization": f"Bearer {token}"},
        )
        res = json.loads(urllib.request.urlopen(req).read())["data"]["result"]
        if res["job_status"] == 0:
            doc_token = res["token"]
            break
        time.sleep(2)

    print(f"Doc created: {doc_token}. Patching title...")
    title_payload = {"update_text_elements": {"elements": [{"text_run": {"content": title}}]}}
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}",
        data=json.dumps(title_payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    urllib.request.urlopen(req)

    print("Patching permissions to tenant_editable...")
    perm_payload = {
        "external_access_entity": "anyone_can_edit",
        "security_entity": "anyone_can_view",
        "comment_entity": "anyone_can_view",
        "share_entity": "anyone",
        "link_share_entity": "tenant_editable",
    }
    req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/drive/v1/permissions/{doc_token}/public?type=docx",
        data=json.dumps(perm_payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="PATCH",
    )
    urllib.request.urlopen(req)

    print("Patching mentions...")

    def patch_mention(block_token):
        req = urllib.request.Request(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{block_token}/children?page_size=500",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            children = json.loads(urllib.request.urlopen(req).read())["data"].get("items", [])
        except:
            return False
        for c in children:
            if c["block_type"] == 2:
                for e in c.get("text", {}).get("elements", []):
                    if e.get("text_run", {}).get("content", "").find("@小聪明蛋") != -1:
                        payload = {
                            "update_text_elements": {
                                "elements": [{"mention_user": {"user_id": "ou_0091f5c50226a4ee0dc8a6d51665db0f"}}]
                            }
                        }
                        preq = urllib.request.Request(
                            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{c['block_id']}",
                            data=json.dumps(payload).encode(),
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                            method="PATCH",
                        )
                        urllib.request.urlopen(preq)
                        return True
            elif c.get("has_child", False):
                if patch_mention(c["block_id"]):
                    return True
        return False

    patch_mention(doc_token)
    print(f"DONE: https://domain.feishu.cn/docx/{doc_token}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_new_doc_from_md.py <md_file_path> <title>")
        sys.exit(1)
    create_doc(sys.argv[1], sys.argv[2])
