import os
import sys
import subprocess
from datetime import datetime

sys.path.insert(0, "/Users/chenzhou/.hermes/my-skills/productivity/feishu-docs/scripts")
from feishu_common import get_tenant_token, do_req  # noqa: E402  (sys.path injection)


def clean_feishu_markdown(content):
    import re

    # Remove version table if exists
    table_pattern = re.compile(r"^\| Col 0.*?\n(?:\|.*?\n)+", re.MULTILINE)
    content = table_pattern.sub("", content, count=1)

    # Remove mentions
    mention_pattern = re.compile(r"\[@ou_[a-zA-Z0-9]+\]|@ou_[a-zA-Z0-9]+")
    content = mention_pattern.sub("", content)

    # Clean multiple blank lines
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def ingest_folder(folder_token, category_path, default_tags):
    token = get_tenant_token()
    print("Fetching folder contents...")
    res = do_req(token, f"https://open.feishu.cn/open-apis/drive/v1/files?folder_token={folder_token}")
    files = res["data"]["files"]

    os.makedirs(category_path, exist_ok=True)
    saved_files = []
    log_additions = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    for f in files:
        name = f["name"]
        f_type = f["type"]
        f_token = f["token"]

        # Shortcut logic: attempts direct extraction using token, expect 404/1770032 if missing permissions
        if f_type == "shortcut":
            print(f"File {name} is a shortcut, attempting direct extraction...")

        print(f"Extracting {name}...")
        try:
            extract_cmd = [
                "uv",
                "run",
                "--with",
                "requests",
                "python",
                "/Users/chenzhou/.hermes/my-skills/productivity/feishu-docs/scripts/extract_docx_to_markdown.py",
                f_token,
            ]
            res_ext = subprocess.check_output(extract_cmd, stderr=subprocess.STDOUT)
            raw_md = res_ext.decode("utf-8")

            cleaned_md = clean_feishu_markdown(raw_md)

            title = name
            filename = title.replace(" ", "-").replace("、", "-").replace("，", "-").lower()
            if not filename.endswith(".md"):
                filename += ".md"

            yaml_fm = f"---\ntitle: {title}\ncreated: {today_str}\nupdated: {today_str}\ntype: summary\ntags: [{', '.join(default_tags)}]\nsources: [{f_token}]\n---\n"
            final_md = yaml_fm + "\n# " + title + "\n\n" + cleaned_md

            file_path = os.path.join(category_path, filename)
            with open(file_path, "w") as out_f:
                out_f.write(final_md)

            print(f"Saved: {file_path}")
            saved_files.append(file_path)
            log_additions.append(f"## [{today_str}] ingest | Feishu Doc: {title}")

        except subprocess.CalledProcessError as e:
            print(f"Failed to extract {name}. Output:\n{e.output.decode('utf-8')}")

    # Append to log.md
    log_path = "/Users/chenzhou/.hermes/wiki/log.md"
    if os.path.exists(log_path) and log_additions:
        with open(log_path, "a") as f:
            f.write("\n" + "\n".join(log_additions) + "\n")

    # IMPORTANT: This script intentionally does NOT register the ingested _living/
    # files into wiki/index.md.  Per SCHEMA.md, index.md is the registry of Active
    # Layer 2 nodes (entities/concepts/comparisons/queries) ONLY — registering
    # _living/ paths there breaks `python3 scripts/wiki_lint.py`
    # (stale_index_entries).  Lesson from the May 2026 ReID ingest.
    print(f"\nBatch ingest complete. {len(saved_files)} files saved under {category_path}.")
    print("\nNEXT STEPS (manual, do NOT auto-run):")
    print("  1. The dumped files are raw Feishu markdown — likely full of project-internal")
    print("     table/column/config names and concrete parameter values. Per the user's")
    print("     Layer 1 policy ('只撰写可复现的知识和技术，不体现具体实现的细节'), rewrite each")
    print("     file to strip impl details and keep only reproducible architecture & methodology.")
    print("  2. Consider consolidating multiple thin Feishu docs into 1–2 thicker _living docs")
    print("     directly under the category folder (avoid sub-sub-directories).")
    print("  3. Extract reusable knowledge into Layer 2 (wiki/concepts/ or wiki/entities/) and")
    print("     register the NEW Layer 2 slugs in wiki/index.md — NEVER register _living/ paths.")
    print("  4. Run `python3 ~/.hermes/scripts/wiki_lint.py` and ensure it prints `wiki_lint: OK`.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: python batch_ingest_folder.py <folder_token> <category_path_under_wiki_living> <tag1,tag2,tag3>")
        sys.exit(1)
    ingest_folder(sys.argv[1], sys.argv[2], sys.argv[3].split(","))
