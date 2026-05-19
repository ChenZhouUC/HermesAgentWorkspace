import os, sys, json, time, subprocess, urllib.request


def do_import():
    if len(sys.argv) < 3:
        print("Usage: python append_md_to_doc.py <target_doc_token> <md_file_path>")
        sys.exit(1)

    target_doc = sys.argv[1]
    md_file = sys.argv[2]

    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print("Error: FEISHU_APP_ID and FEISHU_APP_SECRET required.")
        sys.exit(1)

    print("Getting token...")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    token = json.loads(urllib.request.urlopen(req).read())["tenant_access_token"]

    print("Uploading file...")
    size = os.path.getsize(md_file)
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
        f"file=@{md_file}",
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
        res = json.loads(
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://open.feishu.cn/open-apis/drive/v1/import_tasks/{ticket}",
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).read()
        )
        status = res["data"]["result"]["job_status"]
        if status == 0:
            temp_doc = res["data"]["result"]["token"]
            break
        elif status not in [1, 2]:
            raise Exception(f"Import failed: {res}")
        time.sleep(1)

    print(f"Merging {temp_doc} -> {target_doc}...")
    # Add skill path to import merge_docs
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(skill_dir)
    from merge_markdown_blocks import merge_docs

    merge_docs(token, temp_doc, target_doc)
    print("Merge complete.")


if __name__ == "__main__":
    do_import()
