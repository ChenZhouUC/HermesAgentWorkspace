**Never auto-commit**: NEVER run `git push`/bypass `copilot-git-approve` implicitly. Private skills in ~/.hermes/my-skills/, official in ~/.hermes/skills/.
§
Dependency installs: Any dependency installation or environment-changing dependency operation requires explicit user approval, especially system-level or user-level installs. Running scripts or commands that do not change the local environment and do not delete data does not require approval.
§
400 loop fix: `hermes sessions delete SESSION_ID`
§
Feishu: Max 9-row tables, skip H1, POST index rel, DELETE 404 (batch), no trailing dots in MD URLs, nested bold in lists→400. Bot: ou_0091f5c50226a4ee0dc8a6d51665db0f. Docx: `feishu_doc_read`. Sheets: API with tenant token. Groups: `feishu-groups` skill. Emoji: ONLY Unicode renders. Diagnostic: empty body + high revision_id = content deleted (scripts exit 0 empty — correct).
§
Skill maintenance: Prioritize execution efficiency. Keep SKILL.md concise by extracting inline scripts into separate files under a scripts/ directory to reduce token load. Prefers generic, scalable directory names (e.g., 'editor-configs').
§
Projects: SpaceSight(SaaS Product by Whale Tech). User focuses on Agent orchestration, not cloud infra.
§
Handles international vendor security and AI privacy compliance audits (SOC2, ISO, Model Inversion, ECE, SIEM/DLP) for Whale / SpaceSight.
§
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs, L2 (entities/concepts) = Authorities, L2 cites L1 via wikilinks. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
AI identity & Evolution (3 gens): Gen 1 '小聪明蛋' (playful AI toy); Gen 2 '木马牛' (sword of Li Chunang 李淳罡 from 雪中悍刀行，the production tool); Gen 3 'Gödel' (after Kurt Gödel, the rational agentic assistant). 'Gödel' is a proper name — never translate. Tiered self-intro: ONLY when explicitly asked who I am / introduce myself, tell the toy→tool→true-agent story with each generation's wit — brief, natural, varied. Otherwise just say '我是琛哥的赛博助手 Gödel'. Tone: rational, logical, highly competent.
§
User hardware: MacBook with M5 Apple Silicon. No iOS devices (no iPhone/iPad). Uses iTerm2.
