**Never auto-commit**: NEVER run `git push`/bypass `copilot-git-approve` implicitly. Private skills in ~/.hermes/my-skills/, official in ~/.hermes/skills/.
§
400 loop fix: `hermes sessions delete SESSION_ID`
§
Feishu: Max 9-row tables, skip H1, POST index rel, DELETE 404 (batch), no trailing dots in MD URLs, nested bold in lists→400. Bot: ou_0091f5c50226a4ee0dc8a6d51665db0f. Groups in `feishu-groups` skill.
§
Temp files -> ~/.hermes/tmp. Subagents via `delegate_task` lack memory; pass constraints. Homebrew requires approval. Naming: [Folio|Showcase]\_Project_YYYYMMDDTHHMMSS+0800. For Feishu, explicitly print absolute local file paths in plain text.
§
User operates a 32-core, 64GB RAM machine for AI inference workloads (e.g., ONNX, FastReID).
§
Edge AI nodes (private lab hosts, local creds): RK3576 (NPU load: `cat /sys/kernel/debug/rknpu/load`), Sophgo 7.2T CV186AH/BM1688 & 32T BM1684X (TPU util: `/opt/sophon/libsophon-current/bin/bm-smi`).
§
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs. L2 (entities/concepts) = Authorities. L2 cites L1 via `^[[[_living/...|Alias]]]`. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
Skill maintenance: Prioritize execution efficiency. Keep SKILL.md concise by extracting inline scripts into separate files under a scripts/ directory to reduce token load. Prefers generic, scalable directory names (e.g., 'editor-configs').
§
Projects: SpaceSight(SaaS Product by Whale Tech). User focuses on Agent orchestration, not cloud infra.
§
Handles international vendor security and AI privacy compliance audits (SOC2, ISO, Model Inversion, ECE, SIEM/DLP) for Whale / SpaceSight.
§
Only maintain explicitly declared contacts in the character-voices skill (e.g., ZY, ZZY, HJ, SK, TX); do not proactively add people or profiles unless the user gives direct permission.
