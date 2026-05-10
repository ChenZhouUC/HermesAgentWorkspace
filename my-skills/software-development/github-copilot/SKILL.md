---
name: github-copilot
description: Usage tips, quirks, and troubleshooting for GitHub Copilot IDE integrations, including rate limit mitigation.
category: software-development
---

# GitHub Copilot Troubleshooting & Quirks

## Rate Limits & Fair Use Policy

GitHub Copilot (including Pro and Pro+ tiers) enforces dynamic token limits to prevent abuse. The exact numerical token limits are black-boxed by GitHub and cannot be viewed or modified by the user. Ghost-text code completions appear unmetered; Chat, Workspace agents, and reviews are what actually burn quota.

### 1. Session Usage Limit (1-Hour Window)

**Symptom:** `"You've used over 50% of your session usage limit. Your limit resets in 1 hour."`
**Cause:** Too much context (tokens) sent within the _current_ chat session. Sensitive to:

- Using expensive models (Claude Sonnet, o1-preview, GPT-4o).
- Attaching very large files via `#file` or `@workspace`.
- Maintaining a long chat history without clearing it.

**Mitigation (Immediate Fixes):**

1. **Start a New Chat (`+`):** Drops accumulated conversation history, resetting the token payload per request. Usually clears the warning immediately.
2. **Downgrade the Model:** Switch the chat model to a lighter version (e.g., `GPT-4o-mini`) which has a significantly higher allowed token threshold.
3. **Targeted Context:** Highlight specific code blocks instead of dropping entire files into the context.

### 2. Premium / Weekly Limit (7-Day Window)

**Symptom:** Forced model downgrade, features disabled, or logs showing `user_weekly_rate_limited`.
**Cause:** Total consumption of premium model tokens over a rolling 7-day period has hit the account's maximum cap.
**Mitigation:**

- Cannot bypass this by starting a new chat. The system will automatically force auto-model selection (fallback to cheaper models) until the premium request allocation resets.
- Consider upgrading from Pro to Pro+ if you routinely exhaust the cap.
