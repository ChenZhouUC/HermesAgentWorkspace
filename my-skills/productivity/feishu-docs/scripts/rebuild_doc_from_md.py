"""Rebuild a Feishu document from scratch: clear content, set title, preserve the
version-table history (appending a fresh row), then import markdown.

Atomic: the whole rewrite runs under feishu_common.atomic_update, so a failure
mid-way rolls the document back to its pre-update state (or leaves a backup).

Usage: python rebuild_doc_from_md.py <target_doc_token> <md_file_path> [title]
Requires FEISHU_APP_ID / FEISHU_APP_SECRET in env or ~/.hermes/.env.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import (
    do_req,
    get_tenant_token,
    upload_md,
    import_md_to_doc,
    read_version_tables,
    build_and_write_version_table,
    atomic_update,
)
from merge_markdown_blocks import merge_docs


def rebuild(doc_token, md_file, title=None):
    token = get_tenant_token()

    # Do the fallible, NON-destructive prep first: upload + import to a temp doc.
    # If anything here fails, the live document has not been touched at all.
    print("Uploading + importing markdown to a temp doc...")
    file_token = upload_md(token, md_file)
    temp_doc = import_md_to_doc(token, file_token)

    def op():
        # Snapshot version history while the table is still intact.
        existing_rows, _count, _bm, _root = read_version_tables(token, doc_token)

        root = do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}",
        )
        children = root["data"]["block"].get("children", [])
        if children:
            print(f"Clearing {len(children)} blocks...")
            do_req(
                token,
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
                method="DELETE",
                payload={"start_index": 0, "end_index": len(children)},
            )

        t = title or "Document Title"
        print(f"Setting title: {t}")
        do_req(
            token,
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}",
            method="PATCH",
            payload={"update_text_elements": {"elements": [{"text_run": {"content": t}}]}},
        )

        print("Writing Version Table (preserving history)...")
        version = build_and_write_version_table(token, doc_token, existing_rows, insert_index=0)
        print(f"Version row: {version}")

        print(f"Merging blocks from temp doc {temp_doc} into {doc_token}...")
        merge_docs(token, temp_doc, doc_token)
        print("Done!")

    atomic_update(token, doc_token, op)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python rebuild_doc_from_md.py <doc_token> <md_file> [title]")
        sys.exit(1)
    doc_token = sys.argv[1]
    md_file = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else None
    rebuild(doc_token, md_file, title)
