# Feishu Bot Messaging & Availability Scope

## Sending Messages to Groups

Use the Open API to send messages to groups where the bot is a member:

```python
import requests, json

token = get_tenant_token()
url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "receive_id": "oc_xxxxx",  # chat_id of the group
    "msg_type": "text",
    "content": json.dumps({"text": "Your message here"})
}

res = requests.post(url, headers=headers, json=payload).json()
```

## Direct Messaging Limitations

### Error: `230013 - Bot has NO availability to this user`

When trying to send a direct message via `receive_id_type=open_id`, the bot may return:

```json
{ "code": 230013, "msg": "Bot has NO availability to this user." }
```

**Root Cause:** The bot's "Availability" (可用范围) in the Feishu Developer Console doesn't include the target user.

**Solutions:**

1. **Developer Console**: Go to [open.feishu.cn/app](https://open.feishu.cn/app) → Your App → 应用发布 → 版本管理与发布 → 可用范围 → Add the user or department → Create new version & publish
2. **Admin Console**: Go to [admin.feishu.cn](https://admin.feishu.cn/) → 工作台 → 应用管理 → Your App → 可用范围 → Add user (immediate effect)
3. **Group Chat Workaround**: Create a group with the user and bot, then send messages in that group context.

## Reading share_user Messages

When users share contact cards in chat, the message type is `share_user` and contains:

```json
{ "user_id": "ou_xxxxx" }
```

To find these messages, query the chat message history:

```python
url = "https://open.feishu.cn/open-apis/im/v1/messages"
params = {
    "container_id_type": "chat",
    "container_id": "oc_xxxxx",  # your chat ID with the user
    "sort_type": "ByCreateTimeDesc",
    "page_size": 20
}
res = requests.get(url, headers=headers, params=params).json()
# Filter for msg_type == "share_user" and extract content.user_id
```

## Common Chat Types

| Type           | receive_id_type | Example                               |
| -------------- | --------------- | ------------------------------------- |
| Group Chat     | `chat_id`       | `oc_e11903076f3393e0f237cb406b6c3a07` |
| Direct Message | `open_id`       | `ou_33eeacfbd0c0559b7b734f83503719ab` |

## Listing Available Groups

To find all groups the bot can message:

```python
url = "https://open.feishu.cn/open-apis/im/v1/chats"
headers = {"Authorization": f"Bearer {token}"}

chats = []
page_token = ""
while True:
    params = {"page_size": 100}
    if page_token:
        params["page_token"] = page_token
    res = requests.get(url, headers=headers, params=params).json()
    if res.get("code") != 0:
        break
    items = res.get("data", {}).get("items", [])
    chats.extend(items)
    if not res.get("data", {}).get("has_more"):
        break
    page_token = res.get("data", {}).get("page_token")
```
