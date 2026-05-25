import os
import sys

# Copy Feishu blocks from a Temp Document (e.g. from Markdown Import) into a
# Target Document. The block-copy engine (id/style stripping, >9-row table
# splitting, strict source ordering, table-cell mapping) lives in
# feishu_common.write_block_tree and is shared with the atomic-restore path.

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feishu_common import API, do_req, write_block_tree  # noqa: E402


def merge_docs(token, source_doc_token, target_doc_token):
    root = do_req(token, f"{API}/docx/v1/documents/{source_doc_token}/blocks/{source_doc_token}")["data"]["block"]
    items = do_req(token, f"{API}/docx/v1/documents/{source_doc_token}/blocks?page_size=500")["data"]["items"]
    block_map = {b["block_id"]: b for b in items}
    write_block_tree(token, target_doc_token, root.get("children", []), block_map, skip_first_h1=True)
