import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import get_tenant_token, upload_md, import_md_to_doc, append_version_row, atomic_update
from merge_markdown_blocks import merge_docs


def do_import():
    if len(sys.argv) < 3:
        print("Usage: python append_md_to_doc.py <target_doc_token> <md_file_path>")
        sys.exit(1)

    target_doc = sys.argv[1]
    md_file = sys.argv[2]

    print("Getting token...")
    token = get_tenant_token()

    # Non-destructive prep first: upload + import to temp doc. A failure here
    # never touches the target document.
    print("Uploading file...")
    f_token = upload_md(token, md_file)

    print("Importing to temp doc...")
    temp_doc = import_md_to_doc(token, f_token)

    def op():
        print(f"Merging {temp_doc} -> {target_doc}...")
        merge_docs(token, temp_doc, target_doc)
        print("Merge complete.")

        print("Appending version-table row...")
        version = append_version_row(token, target_doc)
        print(f"Version row appended: {version}")
        return version

    # Atomic: if the merge or version-table write fails, roll the doc back.
    atomic_update(token, target_doc, op)


if __name__ == "__main__":
    do_import()
