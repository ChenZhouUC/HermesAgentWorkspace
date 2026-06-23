---
name: feishu-groups
description: "Use when sending messages or cron jobs to Feishu groups, resolving known chat_ids, listing groups, handling bot availability, reading chat history/merge_forward messages, or parsing share_user contact cards."
---

# Feishu Group Directory

This skill acts as a persistent directory for frequently used Feishu groups.

## Known Groups

| Group Name             | chat_id                               | Notes           |
| :--------------------- | :------------------------------------ | :-------------- |
| SI Owners              | `oc_baeecd57161e7ffd13ab880596f418d2` | Added June 2026 |
| 无能宝们               | `oc_762bc7151b62028453555c1ecef97fec` | Added June 2026 |
| Data Pipeline Workshop | `oc_e11903076f3393e0f237cb406b6c3a07` | Added June 2026 |

## Instructions

1. **Routing / Delivery**: When the user wants to send a message or set up a cronjob targeted at these groups, use the `chat_id` from the table above (e.g., delivery target `feishu:oc_baeecd57161e7ffd13ab880596f418d2`).
2. **Updating**: When the user provides a new group ID, immediately use `skill_manage(action='patch', name='feishu-groups', ...)` to add the new group to the Markdown table. Keep the table clean and readable.

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
