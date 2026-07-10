import os
import re

import requests


def get_tenant_access_token():
    with open(os.path.expanduser("~/.hermes/.env"), "r") as f:
        env_content = f.read()
    app_id = re.search(r"FEISHU_APP_ID=(.*)", env_content).group(1).strip()
    app_secret = re.search(r"FEISHU_APP_SECRET=(.*)", env_content).group(1).strip()
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
    )
    return resp.json().get("tenant_access_token")


def extract_text(elements):
    text = ""
    for e in elements:
        if "text_run" in e:
            text += e["text_run"].get("content", "")
        elif "mention_user" in e:
            text += "@" + e["mention_user"].get("user_id", "user")
        elif "equation" in e:
            text += f"${e['equation'].get('content', '')}$"
        elif "text_link" in e:
            text += f"[{e['text_link'].get('text_run', {}).get('content', '')}]({e['text_link'].get('url', '')})"
    return text


def parse_blocks(blocks):
    md_lines = []
    title = "Untitled"
    for b in blocks:
        b_type = b.get("block_type")
        if b_type == 1:
            title = extract_text(b.get("page", {}).get("elements", []))
            md_lines.append(f"# {title}")
        elif b_type == 2:
            md_lines.append(extract_text(b.get("text", {}).get("elements", [])))
        elif 3 <= b_type <= 9:
            md_lines.append(
                f"{'#' * (b_type - 2)} {extract_text(b.get(f'heading{b_type - 2}', {}).get('elements', []))}"
            )
        elif b_type == 11:
            md_lines.append("\n--- Grid/Table Area ---\n")
        elif b_type == 12:
            md_lines.append(f"- {extract_text(b.get('bullet', {}).get('elements', []))}")
        elif b_type == 13:
            md_lines.append(f"1. {extract_text(b.get('ordered', {}).get('elements', []))}")
        elif b_type == 14:
            md_lines.append(f"```\n{extract_text(b.get('code', {}).get('elements', []))}\n```")
        elif b_type == 15:
            md_lines.append(f"> {extract_text(b.get('quote', {}).get('elements', []))}")
        elif b_type == 31:
            md_lines.append("[Table Element]")
    return title, "\n\n".join(md_lines)


def download_doc_to_md(doc_token):
    token = get_tenant_access_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
    headers = {"Authorization": f"Bearer {token}"}
    blocks, page_token = [], ""
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params).json()
        if resp.get("code") != 0:
            raise Exception(str(resp))
        blocks.extend(resp.get("data", {}).get("items", []))
        if not resp.get("data", {}).get("has_more"):
            break
        page_token = resp.get("data", {}).get("page_token")
    return parse_blocks(blocks)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        title, md = download_doc_to_md(sys.argv[1])
        print(md)
