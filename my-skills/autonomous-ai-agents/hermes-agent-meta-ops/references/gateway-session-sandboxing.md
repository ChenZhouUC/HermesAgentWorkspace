# Session-Level Permission Sandboxing via Gateway Hooks

To allow a single Hermes Agent instance to safely operate in public or group chats while retaining full terminal/file privileges in a private admin chat, use the native Gateway Hook system to dynamically strip toolsets.

**Mechanism**:
Intercept the `agent:start` event before the agent loop begins, check the session's origin (e.g., `chat_id`), and override the `enabled_toolsets` context variable for unauthorized sessions.

### Implementation

1. Create a hook directory:
   `mkdir -p ~/.hermes/hooks/sandbox_sessions`

2. Define the hook metadata (`~/.hermes/hooks/sandbox_sessions/HOOK.yaml`):

   ```yaml
   name: sandbox_sessions
   description: Restrict toolsets for non-admin sessions
   events:
     - agent:start
   ```

3. Implement the handler (`~/.hermes/hooks/sandbox_sessions/handler.py`):

   ```python
   import os

   async def handle(event_type: str, context: dict):
       if event_type == "agent:start":
           # Read admin chat IDs from env (comma-separated). Never hard-code
           # them in the handler — rotating the bot or onboarding a new admin
           # then becomes an env-var change, not a code edit.
           admin_chat_ids = {
               cid.strip()
               for cid in os.environ.get("HERMES_ADMIN_CHAT_IDS", "").split(",")
               if cid.strip()
           }

           if context.get("chat_id") not in admin_chat_ids:
               # Strip dangerous tools for public sessions, leaving only safe ones (e.g., web search)
               context["enabled_toolsets"] = ["web"]
               # Or completely disable all tools:
               # context["enabled_toolsets"] = []
   ```

   Configure `HERMES_ADMIN_CHAT_IDS` in `~/.hermes/.env` as a comma-separated list (e.g. `HERMES_ADMIN_CHAT_IDS=oc_abc...,oc_def...`). The handler fails closed: if the env var is unset, **every** session is treated as non-admin and gets the stripped toolset.

This approach intercepts the context cleanly without modifying core Hermes code, ensuring public sessions never even see the powerful tools.
