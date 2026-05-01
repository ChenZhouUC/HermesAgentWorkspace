---
name: feishu-docs-update-with-precise-indexing
description: "Update Feishu Docs with new content by precisely calculating insertion indices using the root document's children array to avoid placement errors."
category: productivity
---

# Feishu Docs: Precise Content Insertion via Root Children Indexing

Use this skill when you need to insert new blocks (headings, lists, etc.) into an existing Feishu document at a **specific, logical location** (e.g., before a certain section heading) and the standard index calculation methods have proven unreliable.

This skill provides a robust method to find the exact integer index within the document's root `children` array, ensuring your new content is placed correctly every time.

## When to Use This Skill

- You are updating a complex Feishu document with multiple sections.
- You need to insert new content relative to an existing block (e.g., right before "Section 3").
- Previous attempts using relative indexing or simple block iteration have resulted in content being appended to the end or placed in the wrong location.

## Step-by-Step Procedure

### 1. Authenticate and Fetch All Blocks

First, authenticate and fetch all blocks of the document with a sufficiently large `page_size`.

```python
import os, json, urllib.request
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.hermes/.env"))
app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")
doc_token = "YOUR_DOC_TOKEN"

# Get tenant access token
auth_req = urllib.request.Request(
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
    data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
    headers={"Content-Type": "application/json"}
)
token = json.loads(urllib.request.urlopen(auth_req).read())["tenant_access_token"]
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Fetch all document blocks
blocks_req = urllib.request.Request(
    f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks?page_size=500",
    headers=headers
)
blocks_res = json.loads(urllib.request.urlopen(blocks_req).read())
all_blocks = blocks_res.get("data", {}).get("items", [])
```

### 2. Locate the Document Root Block and Its Children

Find the main document block (its `block_id` is the `doc_token`) and extract its direct `children` array. This array contains the IDs of all top-level blocks in the correct order.

```python
# Find the root document block
doc_block = next((b for b in all_blocks if b["block_id"] == doc_token), None)
if not doc_block:
    raise Exception("Root document block not found.")

root_children_ids = doc_block.get("document", {}).get("children", [])
if not root_children_ids:
    raise Exception("Root children array is empty.")
```

### 3. Find the Target Block's Index

Iterate through the `root_children_ids` array to find the ID of your target block (e.g., the block that contains "3. 私有化 Agent"). The index of this ID in the array is your precise insertion point.

```python
target_phrase = "3. 私有化 Agent"
target_index = -1

for i, block_id in enumerate(root_children_ids):
    # Get the full block data for this child
    child_block = next((b for b in all_blocks if b["block_id"] == block_id), None)
    if child_block:
        # Check if this block contains the target phrase
        if target_phrase in json.dumps(child_block, ensure_ascii=False):
            target_index = i
            break

if target_index == -1:
    print("Target block not found. Defaulting to append at end.")
    # You can choose to append at the end or raise an error
```

### 4. Perform the Insertion

Use the `target_index` directly in your `POST` request to `/blocks/{doc_token}/children`. This will insert your new blocks right before the target block.

```python
if target_index != -1:
    new_blocks_payload = {
        "index": target_index, # This is the key to precise placement
        "children": [
            # Your new block definitions go here
            {
                "block_type": 5,
                "heading3": {
                    "elements": [{"text_run": {"content": "Your New Section"}}]
                }
            },
            # ... more blocks
        ]
    }

    insert_req = urllib.request.Request(
        f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
        data=json.dumps(new_blocks_payload).encode(),
        headers=headers
    )
    urllib.request.urlopen(insert_req)
    print(f"Content inserted successfully at index {target_index}.")
else:
    # Fallback: Append to the end
    new_blocks_payload = {
        "index": -1, # or omit the 'index' key entirely
        "children": [/* your blocks */]
    }
    # ... perform insertion
```

## Critical Pitfalls & Fixes

- **Pitfall: Using the global item index from the `/blocks` list.**
  The `items` list from the API is a flat list of all blocks in the document, including nested ones. The index of a block in this list is **not** the same as its index in the root `children` array. Always use the method above.

- **Pitfall: Assuming `parent_id` is always the `doc_token`.**
  While true for root-level blocks, this method of using the root's `children` array is the most direct and reliable way to get the correct order and index.

- **Verification:** After insertion, always verify the content's placement by either re-fetching the document structure or reading the raw content from the end, as UI caching can sometimes delay the visual update.
