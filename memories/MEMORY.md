§
Config repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git (tracks ~/.hermes/ personal config, not hermes-agent/ source)
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Gateway terminal approval flow works correctly in messaging platforms (e.g., Feishu). Sensitive terminal commands (like rm -rf) will successfully trigger interactive user approval prompts. Normal security approval flow is permitted; no need to bypass via Python.
§
Feishu Docs standard template: Use news-style Chinese/English mixed titles (no underscores or version numbers). The body must start with a 3-column table (Version | Time | Author). The Author column must use native @mention for the current bot, with sufficient column width (e.g. [200, 300, 250]) to prevent wrapping. Do not duplicate the title in the body. Append Chicago-style references at the end. Instantly grant edit permissions upon creation/update and send the full, clickable raw URL to the user.
§
When sending URLs to users (like Feishu Docs links), you must include the raw, unformatted, full URL text (e.g., https://...). Do not rely solely on Markdown hyperlink syntax (like [text](url)), as it may not render as a clickable link in the Feishu client.
§
All Homebrew operations (including install, uninstall, update packages) must be explicitly approved by the user beforehand. Do not execute them without permission.
