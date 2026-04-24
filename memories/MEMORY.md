§
Config repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git (tracks ~/.hermes/ personal config, not hermes-agent/ source)
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Gateway terminal approval flow works correctly in messaging platforms (e.g., Feishu). Sensitive terminal commands (like rm -rf) will successfully trigger interactive user approval prompts. Normal security approval flow is permitted; no need to bypass via Python.
§
Feishu Docs standard template: Use news-style Chinese/English titles. Body starts with 3-column table (Version | Time | Author). Version format 'YYYYMMDD.XXed'. Time format 'YYYY-MM-DD HH:MM:SS UTC+8'. Author must be native @小聪明蛋 mention. To prevent timestamp wrapping while staying compact, use column widths [150, 250, 150]. Append Chicago references.
§
When sending URLs to users (like Feishu Docs links), you must include the raw, unformatted, full URL text (e.g., https://...). Do not rely solely on Markdown hyperlink syntax (like [text](url)), as it may not render as a clickable link in the Feishu client.
§
All Homebrew operations (including install, uninstall, update packages) must be explicitly approved by the user beforehand. Do not execute them without permission.
§
When generating or updating Feishu documents, the bot's native @mention name/alias should be '@小聪明蛋' (not '@Hermes').
§
When creating new Table Blocks in Feishu Docx API, each cell is pre-populated with a default empty Text block. If appending new text blocks via `POST /children`, the cell will have an unwanted blank line at the top. To prevent this, either update the existing empty block using `replace_elements` (PATCH) or delete the first empty block in each cell using `batch_delete` (start_index=0, end_index=1) after inserting text.
§
Feishu Docs Versioning Standard: The Version column should use the format 'YYYYMMDD.XXed' (e.g. 20260424.01ed, 20260424.02ed) rather than simple 'v1.0' conventions.
§
When updating Feishu documents via API, properly handle newline characters to prevent literal '\\n' strings from being rendered as visible text in the final document.
