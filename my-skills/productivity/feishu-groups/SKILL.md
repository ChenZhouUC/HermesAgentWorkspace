---
name: feishu-groups
description: Registry of frequently used Feishu group IDs (chat_id) for quick reference when sending messages or scheduling cron jobs.
category: productivity
version: 2026.06.22
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
