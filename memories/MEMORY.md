**Never auto-commit**: Always wait for explicit user instruction (`提交`, `commit this`, etc.) before running `git commit` / `git push`. Private skills in ~/.hermes/my-skills/, official in ~/.hermes/skills/.
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Feishu API Quirks: Max 9-row tables. Skip H1. POST index relative. DELETE 404 (use batch). No trailing dots in MD URLs. Nested bold text in lists triggers 400 errors during rebuild/insert. Bot: ou_0091f5c50226a4ee0dc8a6d51665db0f
§
Feishu Docs: 'AI Benchmark', 'Edge/Cloud Arch'. PaaS: SpaceSight/Echo. KeepAgile/dicts. Gemini quirk: Canvas survives session delete; Images are lost. Claude quirk: bg process hangs on trust prompt; bypass with data='1\\n'. Whale repos: ~/Documents/WhaleRepo/ (wh4a, wh4f, wh4i, whjs). Uses git-delta.
§
Write ALL temp files strictly to ~/.hermes/tmp (never ~/ unless explicitly requested). Subagents spawned via `delegate_task` lack session memory; explicitly pass this path rule and other constraints. Homebrew ops require user approval. Naming: [Folio|Showcase]\_Project_YYYYMMDDTHHMMSS+0800.
§
Env: `uv` data in `~/.local/share/uv/`. macOS sleep: Amphetamine automation blocked by OS; use `caffeinate -di -t 7200 &`. Repo: git@github.com:ChenZhouUC/HermesAgentWorkspace.git.
§
User operates a 32-core, 64GB RAM machine for AI inference workloads (e.g., ONNX, FastReID).
§
Edge AI nodes: RK3576 (private lab host, local credentials, NPU load: `cat /sys/kernel/debug/rknpu/load`), Sophgo 7.2T CV186AH/BM1688 (private lab host, local credentials, TPU util: `/opt/sophon/libsophon-current/bin/bm-smi`), Sophgo 32T BM1684X (private lab host, local credentials, TPU util: `.../bm-smi`).
§
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs. L2 (entities/concepts) = Authorities. L2 cites L1 via `^[[[_living/...|Alias]]]`. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
Skill maintenance preference: Prioritize agent execution efficiency. Keep SKILL.md concise by extracting inline scripts into separate files under a scripts/ directory to reduce token load. Prefers generic, scalable directory names (e.g., 'editor-configs' instead of 'macvim-ops').
