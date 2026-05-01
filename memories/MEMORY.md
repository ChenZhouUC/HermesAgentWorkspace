Config repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Feishu gateway terminal approval works natively; no need to bypass security via Python for sensitive commands.
§
Feishu Docs standard template: Use news-style Chinese/English titles. Body starts with 3-column table (Version | Time | Author). Version format 'YYYYMMDD.XXed'. Time format 'YYYY-MM-DD HH:MM:SS UTC+8'. Author must be native @小聪明蛋 mention. To prevent timestamp wrapping while staying compact, use column widths [150, 250, 150]. Append Chicago references.
§
When sending URLs to users (like Feishu Docs links), you must include the raw, unformatted, full URL text (e.g., https://...). Do not rely solely on Markdown hyperlink syntax (like [text](url)), as it may not render as a clickable link in the Feishu client.
§
Feishu API Quirks: 1. Tables: flat cell list. Adding rows unsupported. Table max 9 rows. Mention fallback: plain text @小聪明蛋 via update_text_elements. 2. Skip inserting H1. 3. POST /children 'index' is relative to parent's children. 4. DELETE /blocks/{id} gives 404; use parent batch_delete. 5. Bullets are block_type: 12 (11 is Grid).
§
When updating Feishu documents via API, properly handle newline characters to prevent literal '\\n' strings from being rendered as visible text in the final document.
§
Known Feishu Documents for user: 'AI Benchmark Report' (CjeZdC6XioH0VnxsRKscJb1LnVe), 'Edge/Cloud Architecture & VLM' (Mw6CdkF33oRZosx8L3WcgWU4nAc).
§
Write ALL temp files strictly to ~/.hermes/tmp (never ~/ unless explicitly requested). Subagents spawned via `delegate_task` lack session memory; explicitly pass this path rule and other constraints in their context/goal. Homebrew ops require user approval.
§
Avoid fragmenting skills. Before creating a new skill, use skills_list to see if the knowledge can be patched into an existing, broader skill in the same domain.
§
Env: `uv` data (python/tools) is in `~/.local/share/uv/` (not macOS default). User uses `pyenv` with `uv`.
