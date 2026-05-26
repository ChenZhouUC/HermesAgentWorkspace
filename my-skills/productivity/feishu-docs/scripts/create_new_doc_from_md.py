import os
import sys
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import get_tenant_token, upload_md, import_md_to_doc, append_version_row


def create_doc(md_path, title):
    token = get_tenant_token()

    print(f"Uploading {md_path}...")
    f_token = upload_md(token, md_path)

    print("Importing to docx...")
    doc_token = import_md_to_doc(token, f_token)

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

    print("Writing initial Version Table...")
    version = append_version_row(token, doc_token)
    print(f"Version row: {version}")

    print(f"DONE: https://whales.feishu.cn/docx/{doc_token}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python create_new_doc_from_md.py <md_file_path> <title>")
        sys.exit(1)
    create_doc(sys.argv[1], sys.argv[2])
