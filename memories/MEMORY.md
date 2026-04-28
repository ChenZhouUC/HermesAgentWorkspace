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
Feishu API Quirks: 1. Tables: flat cell list. Adding rows unsupported (PATCH existing cells). 2. Mention fallback: plain text @小聪明蛋 via update_text_elements. 3. Skip inserting H1. 4. PATCH /permissions requires ?type=docx. 5. POST /children 'index' is relative to parent's children. 6. DELETE /blocks/{id} gives 404; use parent batch_delete with start_index/end_index. 7. Bullets are block_type: 12 (11 is Grid).
§
When updating Feishu documents via API, properly handle newline characters to prevent literal '\\n' strings from being rendered as visible text in the final document.
§
Known Feishu Documents for user: 'AI Benchmark Report' (CjeZdC6XioH0VnxsRKscJb1LnVe), 'Edge/Cloud Architecture & VLM' (Mw6CdkF33oRZosx8L3WcgWU4nAc).
§
Write ALL temporary/intermediate files (JSON dumps, analysis, scripts) strictly to ~/.hermes/tmp. Never write to ~/ or outside ~/.hermes/ unless explicitly requested. Homebrew operations require explicit user approval.
