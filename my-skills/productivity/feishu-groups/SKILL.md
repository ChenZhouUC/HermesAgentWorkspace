---
name: feishu-groups
description: "Directory of frequently used Feishu group chat_ids, plus how to interact with groups via the Open API: sending messages, listing available groups (GET /im/v1/chats), bot availability scope (Error 230013), and reading shared contact cards (share_user). Use when sending messages or scheduling cron jobs to Feishu groups."
category: productivity
version: 2026.06.23
author: Chen Zhou <chenzhou@uchicago.edu>
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

See `references/bot-messaging-and-availability.md` for full patterns.
