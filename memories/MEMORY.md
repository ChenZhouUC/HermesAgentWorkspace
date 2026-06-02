**Never auto-commit**: NEVER run `git commit`/`git push` or bypass `copilot-git-approve` without explicit instruction. Private skills in ~/.hermes/my-skills/, official in ~/.hermes/skills/.
§
**400 cascade fix**: If 400 errors loop, run `hermes sessions list` then `hermes sessions delete SESSION_ID` to remove the broken session.
§
Feishu API Quirks: Max 9-row tables. Skip H1. POST index relative. DELETE 404 (use batch). No trailing dots in MD URLs. Nested bold text in lists triggers 400 errors during rebuild/insert. Bot: ou_0091f5c50226a4ee0dc8a6d51665db0f
§
Projects: SpaceSight (PaaS, NEVER use the name 'Echo' anymore), KeepAgile/dicts, HyperTex (TeX/graph network system with Admin/User roles, Token/Latency tracking; PPT generation via Heuristic and Declarative/Instruction modes).
§
Write ALL temp files strictly to ~/.hermes/tmp (never ~/ unless explicitly requested). Subagents spawned via `delegate_task` lack session memory; explicitly pass this path rule and other constraints. Homebrew ops require user approval. Naming: [Folio|Showcase]\_Project_YYYYMMDDTHHMMSS+0800.
§
macOS lock screen check via CLI: use `ioreg -n Root -d1 | grep CGSSessionScreenIsLocked` (returns 'Yes' if locked, 'No' or absent if unlocked). Ignore prior memory stating it fails due to privacy.
§
User operates a 32-core, 64GB RAM machine for AI inference workloads (e.g., ONNX, FastReID).
§
Edge AI nodes (private lab hosts, local creds): RK3576 (NPU load: `cat /sys/kernel/debug/rknpu/load`), Sophgo 7.2T CV186AH/BM1688 & 32T BM1684X (TPU util: `/opt/sophon/libsophon-current/bin/bm-smi`).
§
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs. L2 (entities/concepts) = Authorities. L2 cites L1 via `^[[[_living/...|Alias]]]`. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
Skill maintenance preference: Prioritize agent execution efficiency. Keep SKILL.md concise by extracting inline scripts into separate files under a scripts/ directory to reduce token load. Prefers generic, scalable directory names (e.g., 'editor-configs' instead of 'macvim-ops').
