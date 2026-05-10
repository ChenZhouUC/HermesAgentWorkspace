---
name: custom-skill-organizer
description: Standard operating procedure for auditing, consolidating, and organizing the user's custom Hermes skills, strictly limited to ~/.hermes/my-skills/.
category: productivity
---

# Custom Skill Organizer

**WHEN TO USE:**
Use this skill when the user asks to "整理一下 skill", "清理技能", or requests an audit of their custom skills.

**STRICT SCOPE:**
You must **ONLY** audit and modify skills located in `~/.hermes/my-skills/` (the user's custom skills). Do **NOT** attempt to modify, patch, or delete official/pinned Hermes skills.

## Core Principles

1. **Single Responsibility Principle (SRP):** Each skill should have a clear, singular focus. If two skills handle overlapping domains (e.g., two different skills handling downloads), their overlapping parts should be merged or separated into clear boundaries.
2. **Cross-Referencing over Duplication:** If Skill A needs a capability that Skill B excels at, Skill A should instruct the agent to "load Skill B", rather than duplicating the instructions in Skill A.
3. **Clean Up Orphans:** When merging or modifying skills, ensure that no orphaned files (e.g., outdated `references/` or `scripts/` under the skill's directory) are left behind.

## Execution Workflow

### 1. Audit Current State

Start by listing all custom skills and their structures:

```bash
tree ~/.hermes/my-skills/
```

Identify potential overlaps based on the directory names, skill names, and your current context. If needed, use `cat` or `skill_view` to read the `SKILL.md` of specific skills that seem redundant.

### 2. Analyze & Plan

Look for:

- **Redundancies:** Two skills solving the same problem.
- **Bloat:** A skill that does too many things (needs splitting) or contains outdated fallback logic that is now handled better by a newer skill.
- **Miscategorization:** A skill placed in the wrong category folder.

### 3. Execute Consolidation

Use the `skill_manage` tool to perform the cleanup:

- **Merge/Refactor:** Use `skill_manage(action='patch')` to remove redundant sections from a broader skill and point it to a specialized skill.
- **Delete Obsolete Skills:** If a skill is 100% superseded, use `skill_manage(action='delete', name='<skill_name>')` to remove it.
- **Clean Orphaned Files:** If you remove references from a `SKILL.md`, use `skill_manage(action='remove_file')` or terminal `rm` to delete the actual physical files in the `references/` or `scripts/` directories.

### 4. Report to User

Present a highly concise, bulleted summary of the actions taken:

- Which skills were merged/patched.
- Which redundant skills or files were deleted.
- How the new boundaries are defined.
