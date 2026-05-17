Repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git. NEVER auto-commit/push without explicit user request. Run `~/.config/git/hooks/copilot-git-approve commit` (or push) first. No --no-verify.
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Feishu gateway terminal approval works natively; no need to bypass security via Python for sensitive commands.
§
Feishu API Quirks: 1. Tables: flat cell list. Adding rows unsupported. Table max 9 rows. Mention fallback: plain text @小聪明蛋 via update_text_elements. 2. Skip inserting H1. 3. POST /children 'index' is relative to parent's children. 4. DELETE /blocks/{id} gives 404; use parent batch_delete. 5. Bullets are block_type: 12 (11 is Grid).
§
When updating Feishu documents via API, properly handle newline characters to prevent literal '\\n' strings from being rendered as visible text in the final document.
§
Feishu Docs: 'AI Benchmark' (CjeZdC6XioH0VnxsRKscJb1LnVe), 'Edge/Cloud Arch' (Mw6CdkF33oRZosx8L3WcgWU4nAc), '老乡鸡评估' (N422deLZjopVCVxMfsMcJFHwnaf).
§
Write ALL temp files strictly to ~/.hermes/tmp (never ~/ unless explicitly requested). Subagents spawned via `delegate_task` lack session memory; explicitly pass this path rule and other constraints in their context/goal. Homebrew ops require user approval.
§
Env: `uv` data (python/tools) is in `~/.local/share/uv/` (not macOS default). User uses `pyenv` with `uv`.
§
User operates a 32-core, 64GB RAM machine for AI inference workloads (e.g., ONNX, FastReID).
§
Edge AI nodes: RK3576 (private lab host, local credentials, NPU load: `cat /sys/kernel/debug/rknpu/load`), Sophgo 7.2T CV186AH/BM1688 (private lab host, local credentials, TPU util: `/opt/sophon/libsophon-current/bin/bm-smi`), Sophgo 32T BM1684X (private lab host, local credentials, TPU util: `.../bm-smi`).
§
LLM Wiki `~/.hermes/wiki`. L1 (\_living/) has NO tags/wikilinks. L2 extracts NOUNS (entities/theories) only. NEVER extract processes/manuals as L2 nodes; extract core entities instead. Link backward to L1 manual via COMPACT inline footnote: `^[[[_living/...|Alias]]]` (NO SPACES). Deep sync purges ghosts.
