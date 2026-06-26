---
name: feishu-groups
description: "Use when sending messages or cron jobs to Feishu groups, resolving known chat_ids, listing groups, handling bot availability, reading chat history/merge_forward messages, or parsing share_user contact cards."
---

# Feishu Group Directory

This skill documents how the bot talks to Feishu groups. The group roster itself
— every `chat_id` plus its per-group persona — lives in **one** place:
`~/.hermes/groups.yaml`. This skill no longer keeps a duplicate id table.

## Group roster — single source of truth (`~/.hermes/groups.yaml`)

`~/.hermes/groups.yaml` is the **only** entry point for group information. Each
list item under `groups:` carries the group's stable `chat_id` (plus `name`,
`style`, `capabilities`, `audience`, `intro` …). The gateway injects the matched
group's persona into the system prompt (`gateway/session.py`, sentinel
`group-profile`, PATCH-14); this only changes presentation — the
sandbox/read-only toolset is identical across groups.

## Instructions

1. **Routing / Delivery**: To send a message or set up a cronjob targeted at a
   group, look up its `chat_id` in `~/.hermes/groups.yaml` (delivery target
   `feishu:<chat_id>`).
2. **Adding / removing a group**: Edit `~/.hermes/groups.yaml` directly — add or
   remove the list item (with at least `chat_id` + `name`, and persona fields if
   it needs a distinct voice). Do **not** maintain a separate id list here.
3. **Nightly greeting opt-out**: `scripts/nightly_greeting.py` broadcasts the
   nightly greeting to every group in `groups.yaml`. To keep a group's persona
   but exclude it from the greeting (e.g. a test group), add
   `nightly_greeting: false` to that group's entry.

## 📮 Bot Messaging & Group Availability

The bot can send messages to any Feishu group it's a member of via the Open API.

### Sending to Groups

```python
token = get_tenant_token()
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
payload = {
    "receive_id": "oc_xxxxx",  # chat_id
    "msg_type": "text",
    "content": json.dumps({"text": "message"})
}
requests.post(url, headers=headers, json=payload).json()
```

### Listing Available Groups

Query `GET /im/v1/chats` with pagination to find all groups the bot can message.

### Direct Messaging Limitations

Sending DMs via `receive_id_type=open_id` returns **Error 230013** (`Bot has NO availability to this user`) if the target user isn't in the bot's "可用范围" (Availability Scope).
**Fix:** Admin or developer must add the user to the bot's availability in [open.feishu.cn/app](https://open.feishu.cn/app) → App → 版本管理与发布 → 可用范围。Or create a group chat with the user and bot as workaround.

### Reading Contact Cards (share_user)

When users share contact cards, message type is `share_user` with content `{"user_id": "ou_xxxxx"}`. Query chat history via `GET /im/v1/messages?container_id_type=chat&container_id=oc_xxxxx` and filter for `msg_type == "share_user"`.

### Reading Chat History & Merged Messages (merge_forward)

To retrieve recent messages in a group chat, query `GET /im/v1/messages` with `container_id_type=chat` and a group `chat_id`:

```python
url = "https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id=oc_xxxxx&page_size=50"
headers = {"Authorization": f"Bearer {token}"}
res = requests.get(url, headers=headers).json()
```

#### Parsing Merged and Forwarded Messages (merge_forward)

When a user forwards a bundle of messages, the top-level message type is `merge_forward` and its raw content is simply `"Merged and Forwarded Message"`. To extract the actual nested conversation logs:

1. Get the top-level `message_id` of the `merge_forward` message (e.g., `om_xxxxxx`).
2. Query `GET /im/v1/messages/:message_id`. This endpoint expands and returns the top-level message along with **all nested child messages** in the response `items` array, marked with `upper_message_id`.

```python
# Fetch details for the merge_forward message_id
url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
res = requests.get(url, headers=headers).json()
items = res.get("data", {}).get("items", [])

# Extract children linked to the merge_forward message
child_messages = [item for item in items if item.get("upper_message_id") == message_id]
for msg in child_messages:
    # content is usually a JSON string
    content_raw = msg.get("body", {}).get("content", "{}")
    content = json.loads(content_raw)
    print(f"[{msg.get('sender', {}).get('id')}]: {content.get('text')}")
```

See `references/bot-messaging-and-availability.md` for full patterns.
