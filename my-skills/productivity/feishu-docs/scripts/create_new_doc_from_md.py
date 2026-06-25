import os
import sys
import json
import argparse
import base64
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import get_tenant_token, upload_md, import_md_to_doc, append_version_row


def _decode_inline_content(value):
    return value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")


def _write_temp_markdown(content):
    tmp_root = Path(os.path.expanduser(os.getenv("HERMES_HOME", "~/.hermes"))) / "tmp" / "feishu-docs"
    tmp_root.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(
        prefix="create_doc_",
        suffix=".md",
        dir=str(tmp_root),
        text=True,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")
    return path


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Create a Feishu docx by importing Markdown.",
    )
    parser.add_argument(
        "positional",
        nargs="*",
        help=("Legacy form: <md_file_path> <title>. With --content, one positional title is allowed."),
    )
    parser.add_argument("--title", help="Professional document title.")
    parser.add_argument(
        "--content",
        help="Inline Markdown body. Literal \\n sequences are converted to newlines.",
    )
    parser.add_argument(
        "--content-b64",
        help="Base64-encoded UTF-8 Markdown body, useful when shell quoting would be awkward.",
    )
    args = parser.parse_args(argv)

    inline_sources = [value for value in (args.content, args.content_b64) if value is not None]
    if len(inline_sources) > 1:
        parser.error("use only one of --content or --content-b64")

    if inline_sources:
        if len(args.positional) > 1:
            parser.error("with --content/--content-b64, pass at most one positional title")
        title = args.title or (args.positional[0] if args.positional else None)
        if not title:
            parser.error("--title is required when using --content/--content-b64")
        if args.content_b64 is not None:
            try:
                content = base64.b64decode(args.content_b64).decode("utf-8")
            except Exception as exc:
                parser.error(f"invalid --content-b64: {exc}")
        else:
            content = _decode_inline_content(args.content or "")
        if not content.strip():
            parser.error("markdown content cannot be empty")
        return _write_temp_markdown(content), title

    if len(args.positional) < 2:
        parser.error("Usage: python create_new_doc_from_md.py <md_file_path> <title>")
    title = args.title or args.positional[1]
    return args.positional[0], title


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
                    if e.get("text_run", {}).get("content", "").find("@Gödel") != -1:
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
    md_path, title = _parse_args(sys.argv[1:])
    create_doc(md_path, title)
