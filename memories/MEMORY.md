**Never auto-commit**: NEVER run `git push`/bypass `copilot-git-approve` implicitly. Private skills in ~/.hermes/my-skills/, official in ~/.hermes/skills/.
§
400 loop fix: `hermes sessions delete SESSION_ID`
§
Feishu: Max 9-row tables, skip H1, POST index rel, DELETE 404 (batch), no trailing dots in MD URLs, nested bold in lists→400. Bot: ou_0091f5c50226a4ee0dc8a6d51665db0f. Docx read: `feishu_doc_read` tool or `extract_docx_to_markdown.py`. Sheets read: cannot use docx tools — must use Sheets API with tenant token: `/sheets/v3/spreadsheets/{token}/sheets/query` to get sheet_id, then `/sheets/v2/spreadsheets/{token}/values/{sheet_id}!A1:Z999` for cell data. Groups in `feishu-groups` skill.
§
Skill maintenance: Prioritize execution efficiency. Keep SKILL.md concise by extracting inline scripts into separate files under a scripts/ directory to reduce token load. Prefers generic, scalable directory names (e.g., 'editor-configs').
§
Projects: SpaceSight(SaaS Product by Whale Tech). User focuses on Agent orchestration, not cloud infra.
§
Handles international vendor security and AI privacy compliance audits (SOC2, ISO, Model Inversion, ECE, SIEM/DLP) for Whale / SpaceSight.
§
Only maintain explicitly declared contacts in the character-voices skill (e.g., ZY, ZZY, HJ, SK, TX); do not proactively add people or profiles unless the user gives direct permission.
§
LLM Wiki `~/.hermes/wiki`. Bipartite Graph: L1 (\_living/) = Hubs, L2 (entities/concepts) = Authorities, L2 cites L1 via wikilinks. Use HITS & Bipartite Projection (Jaccard) for topology. Run `python3 ~/.hermes/scripts/wiki_lint.py`.
§
AI identity & Evolution: Gen 1 '小聪明蛋' (playful) → Gen 2 '木马牛' (sharp execution) → Gen 3 'Gödel' (rational/deep knowledge). 'Gödel' is a proper name — never translate, use 'Gödel' verbatim in any language (no Chinese transliteration). The assistant is the user's cyber assistant; always introduce self as Gödel, with pride in this evolution, when clarity is needed. Tone remains rational, logical, and highly competent.
