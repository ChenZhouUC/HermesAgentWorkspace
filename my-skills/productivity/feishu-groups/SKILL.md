---
name: feishu-groups
description: Registry of frequently used Feishu group IDs (chat_id) for quick reference when sending messages or scheduling cron jobs.
---

# Feishu Group Directory

This skill acts as a persistent directory for frequently used Feishu groups.

## Known Groups

| Group Name | chat_id                               | Notes           |
| :--------- | :------------------------------------ | :-------------- |
| SI Owners  | `oc_baeecd57161e7ffd13ab880596f418d2` | Added June 2026 |

## Instructions

1. **Routing / Delivery**: When the user wants to send a message or set up a cronjob targeted at these groups, use the `chat_id` from the table above (e.g., delivery target `feishu:oc_baeecd57161e7ffd13ab880596f418d2`).
2. **Updating**: When the user provides a new group ID, immediately use `skill_manage(action='patch', name='feishu-groups', ...)` to add the new group to the Markdown table. Keep the table clean and readable.
