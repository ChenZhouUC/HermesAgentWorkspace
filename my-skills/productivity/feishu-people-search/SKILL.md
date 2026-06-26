---
name: feishu-people-search
category: productivity
description: Search for Feishu employee info (Name, Address/称谓, Role, Department) by keyword, strictly protecting other PII.
---

# Feishu People Search

This skill looks up employee information from `~/.hermes/people.yaml` based on a name or keyword.

**Search targets**: name, aliases, address (称谓), role (岗位), department (团队)  
**Returned fields**: 姓名、称谓、岗位、团队（仅这四项，其他敏感信息如工号/司龄/下属等不展示）

Uses a relevance scoring system:

- Exact name/alias match → returns single best result
- Partial/fuzzy match → may return multiple candidates with scores for you to pick

## Usage

When you need to look up an employee's context, run the included search script via the terminal:

```bash
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/my-skills/productivity/feishu-people-search/scripts/search_people.py "keyword"
```

_(If installed globally, adjust `my-skills` to `skills`.)_

The script requires `pyyaml` (already in the Hermes venv). It searches across name, aliases, address (称谓), role, and department, and returns **only** these four: 姓名、称谓、岗位、团队（其他敏感信息如工号/司龄/下属/上级等一律不展示）.
