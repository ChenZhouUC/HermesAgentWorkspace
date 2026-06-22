# Injecting Custom Version Table Rows

When the user asks to fabricate or insert custom version history entries (e.g., backdating versions to reflect prior edits), use this technique to directly manipulate the version table via `feishu_common` internals.

## Technique

```python
import os, sys
sys.path.append(os.path.expanduser('~/.hermes/my-skills/productivity/feishu-docs/scripts'))
import feishu_common

token = feishu_common.get_tenant_token()
doc_token = "<DOC_TOKEN>"

# 1. Read and delete existing version table
rows, table_count, block_map, root = feishu_common.read_version_tables(token, doc_token)
if table_count > 0:
    feishu_common.do_req(
        token,
        f"{feishu_common.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
        method="DELETE",
        payload={"start_index": 0, "end_index": table_count},
    )

# 2. Build custom rows (header + your entries)
new_rows = [
    feishu_common._header_row(),
    [
        [{"text_run": {"content": "20260620.01ed"}}],
        [{"text_run": {"content": "2026-06-20 14:30:00 UTC+8"}}],
        [{"mention_user": {"user_id": feishu_common.BOT_OPEN_ID}}]
    ],
    # ... add more rows as needed
]

# 3. Write the new table
feishu_common._write_version_tables(token, doc_token, new_rows, 0)
```

## Format Rules

- Version: `YYYYMMDD.NNed` (e.g., `20260620.01ed`)
- Time: `YYYY-MM-DD HH:MM:SS UTC+8`
- Author: `{"mention_user": {"user_id": feishu_common.BOT_OPEN_ID}}`
- First row must be `feishu_common._header_row()`
