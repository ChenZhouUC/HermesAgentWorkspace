Repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git. NEVER auto-commit/push without explicit user request. Run `~/.config/git/hooks/copilot-git-approve commit` (or push) first. No --no-verify.
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Feishu gateway terminal approval works natively; no need to bypass security via Python for sensitive commands.
§
Feishu API Quirks: 1. Tables: flat cell list, max 9 rows, no direct row append. 2. Skip H1 insert. 3. POST /children 'index' relative to parent. 4. DELETE /blocks/{id} gives 404; use parent batch_delete. 5. Bullets are block_type 12. Domain: whales.feishu.cn. Bot @小聪明蛋 open_id: ou_0091f5c50226a4ee0dc8a6d51665db0f.
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
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs. L2 (entities/concepts) = Authorities. L2 cites L1 via `^[[[_living/...|Alias]]]`. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
Products: SpaceSight, Echo (PaaS). Maintains dict catalog: KeepAgile/dicts.
