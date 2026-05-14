import os, re, requests, json, sys

# Robust script to download a Feishu Docx and convert its blocks to Markdown.
# Requires FEISHU_APP_ID and FEISHU_APP_SECRET in ~/.hermes/.env
# Usage: python download_docx_to_md.py <doc_token>


def get_tenant_access_token():
    with open(os.path.expanduser("~/.hermes/.env"), "r") as f:
        env = f.read()
    app_id = re.search(r"FEISHU_APP_ID=(.*)", env).group(1).strip()
    app_secret = re.search(r"FEISHU_APP_SECRET=(.*)", env).group(1).strip()
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


def fetch_and_convert(doc_token):
    token = get_tenant_access_token()
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
    headers = {"Authorization": f"Bearer {token}"}
    blocks = []
    page_token = ""
    while True:
        resp = requests.get(url, headers=headers, params={"page_size": 500, "page_token": page_token})
        data = resp.json()
        if data.get("code") != 0:
            print(f"Error fetching docs: {data}", file=sys.stderr)
            sys.exit(1)
        blocks.extend(data.get("data", {}).get("items", []))
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token")

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
            h_level = b_type - 2
            md_lines.append(f"{'#' * h_level} {extract_text(b.get(f'heading{h_level}', {}).get('elements', []))}")
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

    print(f"--- {title} ---\n\n" + "\n\n".join(md_lines))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_docx_to_md.py <doc_token>")
        sys.exit(1)
    fetch_and_convert(sys.argv[1])
