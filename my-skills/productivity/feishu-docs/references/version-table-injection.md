# Injecting Custom Historical Version Rows into an Existing Feishu Doc

The standard `append_version_row` in `feishu_common.py` only appends ONE new row. When you need to backfill multiple historical version rows (e.g., the user asks to fabricate prior version entries with custom dates), use this pattern:

```python
import os, sys
sys.path.append(os.path.expanduser('~/.hermes/my-skills/productivity/feishu-docs/scripts'))
import feishu_common

token = feishu_common.get_tenant_token()
doc_token = "<DOC_TOKEN>"

# 1. Read existing version table to find block count
rows, table_count, block_map, root = feishu_common.read_version_tables(token, doc_token)

# 2. Delete the existing version table block(s)
if table_count > 0:
    feishu_common.do_req(
        token,
        f"{feishu_common.API}/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete",
        method="DELETE",
        payload={"start_index": 0, "end_index": table_count},
    )

# 3. Build the full version table: header + all rows
new_rows = [
    feishu_common._header_row(),
    # Custom historical rows with YYYYMMDD.NNed format
    [
        [{"text_run": {"content": "20260620.01ed"}}],
        [{"text_run": {"content": "2026-06-20 14:30:00 UTC+8"}}],
        [{"mention_user": {"user_id": feishu_common.BOT_OPEN_ID}}]
    ],
    [
        [{"text_run": {"content": "20260621.01ed"}}],
        [{"text_run": {"content": "2026-06-21 16:45:00 UTC+8"}}],
        [{"mention_user": {"user_id": feishu_common.BOT_OPEN_ID}}]
    ],
    # Current version row
    [
        [{"text_run": {"content": "20260622.01ed"}}],
        [{"text_run": {"content": "2026-06-22 09:10:00 UTC+8"}}],
        [{"mention_user": {"user_id": feishu_common.BOT_OPEN_ID}}]
    ],
]

# 4. Write the new table at index 0
feishu_common._write_version_tables(token, doc_token, new_rows, 0)
```

Key points:

- The version format must be `YYYYMMDD.NNed` where `NN` is the edit sequence for that day
- Time format: `YYYY-MM-DD HH:MM:SS UTC+8`
- Author must use `mention_user` with the bot's `open_id` (not plain text)
- The `_write_version_tables` function handles cell creation and population automatically
- If the table exceeds 9 rows, the function automatically splits across multiple tables
