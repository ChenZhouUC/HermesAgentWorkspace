import os
import re
import sys

import requests


def get_tenant_access_token():
    try:
        with open(os.path.expanduser("~/.hermes/.env"), "r") as f:
            env_content = f.read()
        app_id = re.search(r"FEISHU_APP_ID=(.*)", env_content).group(1).strip()
        app_secret = re.search(r"FEISHU_APP_SECRET=(.*)", env_content).group(1).strip()
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
        return resp.json().get("tenant_access_token")
    except Exception as e:
        print("Failed to get token:", e)
        sys.exit(1)


def recursive_extract(blocks_dict, root_id):
    b = blocks_dict.get(root_id)
    if not b:
        return ""
    b_type = b.get("block_type")

    def get_text(element_key):
        elements = b.get(element_key, {}).get("elements", [])
        text = ""
        for e in elements:
            if "text_run" in e:
                text += e["text_run"].get("content", "")
            elif "text_link" in e:
                text += f"[{e['text_link'].get('text_run', {}).get('content', '')}]({e['text_link'].get('url', '')})"
            elif "mention_user" in e:
                text += f"@{e['mention_user'].get('user_id', 'user')}"
        return text

    content = ""
    if b_type == 2:
        content = get_text("text") + "\n"
    elif 3 <= b_type <= 9:
        content = f"\n{'#' * (b_type - 2)} {get_text(f'heading{b_type - 2}')}\n\n"
    elif b_type == 12:
        content = f"- {get_text('bullet')}\n"
    elif b_type == 13:
        content = f"1. {get_text('ordered')}\n"
    elif b_type == 14:
        code_lang = b.get("code", {}).get("style", {}).get("language", "")
        content = f"```{code_lang}\n{get_text('code')}\n```\n"
    elif b_type == 15:
        content = f"> {get_text('quote')}\n"
    elif b_type == 31:  # Table
        col_size = b.get("table", {}).get("property", {}).get("column_size", 1)
        content += "\n| " + " | ".join([f"Col {i}" for i in range(col_size)]) + " |\n"
        content += "| " + " | ".join(["---" for i in range(col_size)]) + " |\n"
        cells = b.get("table", {}).get("cells", [])
        for i, cell_id in enumerate(cells):
            cell_content = recursive_extract(blocks_dict, cell_id).replace("\n", " ").strip()
            content += f"| {cell_content} "
            if (i + 1) % col_size == 0:
                content += "|\n"
        content += "\n"
        return content  # Stop recursing on table children directly, already handled cells

    if b.get("children"):
        for child_id in b["children"]:
            content += recursive_extract(blocks_dict, child_id)

    return content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_docx_to_markdown.py <doc_token>")
        sys.exit(1)

    token = get_tenant_access_token()
    doc_token = sys.argv[1]

    # Check if it's a Wiki node
    wiki_check_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={doc_token}"
    resp = requests.get(wiki_check_url, headers={"Authorization": f"Bearer {token}"}).json()
    if resp.get("code") == 0:
        doc_token = resp["data"]["node"]["obj_token"]  # Extract the real doc token from the wiki node

    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
    headers = {"Authorization": f"Bearer {token}"}
    blocks = []
    page_token = ""

    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()

        if data.get("code") != 0:
            print("API Error:", data)
            sys.exit(1)

        items = data.get("data", {}).get("items", [])
        blocks.extend(items)
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token")

    blocks_dict = {b["block_id"]: b for b in blocks}
    if not blocks:
        print("No blocks found.")
        sys.exit(1)

    full_md = recursive_extract(blocks_dict, blocks[0]["block_id"])
    print(full_md)
