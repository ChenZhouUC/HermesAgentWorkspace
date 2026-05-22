# Gateway Session-Level Tool Sandboxing

## The Problem

Running a single Hermes Agent instance across multiple platform chats (e.g., Feishu, Telegram) where the admin wants full system access (terminal, file) in their private chat, but wants to provide only a pure LLM chat experience (no system access) in public group chats or to other users.

## The Solution: Dynamic Toolset Override via Gateway Hook

Instead of relying on LLM prompting (which is highly vulnerable to jailbreaks), enforce tool isolation at the Gateway layer by manipulating the LLM request context.

1. Intercept the inbound message using a Gateway Hook.
2. Inspect the origin `chat_id` or `open_id`.
3. If the origin does not match the admin's whitelist, dynamically inject/override the `enabled_toolsets` parameter for that specific LLM request.
4. Force `enabled_toolsets = []` (or just `['web_search']` for basic lookup capabilities).

### Why this works

This approach physically deprives the model of tool schemas (like `terminal` or `execute_code`) in unauthorized chats. The model simply does not know the tools exist, ensuring it cannot execute system commands regardless of prompt injection or trickery, while remaining fully capable in the admin's private session.
