§
Config repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git (tracks ~/.hermes/ personal config, not hermes-agent/ source)
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Gateway terminal approval flow works correctly in messaging platforms (e.g., Feishu). Sensitive terminal commands (like rm -rf) will successfully trigger interactive user approval prompts. Normal security approval flow is permitted; no need to bypass via Python.
§
Feishu Docs rules: 1) Update existing docs; no new ones for ongoing topics. 2) No version info in titles. Titles must be standard news-style formatting (mixed English/Chinese) with NO underscores. 3) Prepend version table (Version: YYYYMMDD.XXed, Time: YYYY-MM-DD HH:MM:SS UTC+8). 4) Append Chicago style references at the end, synced with content. 5) Always grant edit permissions instantly and send full URL.
§
Feishu Docs rules (Version Table): The version table at the top must be a multi-row log (Columns: Version, Time). Append a new row at the bottom for every update to maintain a full history. Never overwrite old version rows.
