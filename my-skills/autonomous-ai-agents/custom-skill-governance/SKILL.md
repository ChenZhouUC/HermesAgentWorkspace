---
name: custom-skill-governance
description: "Use when auditing, maintaining, consolidating, pruning, merging, renaming, or standardizing the user's custom skills under ~/.hermes/my-skills. Use for requests to remove redundant skills, merge overlapping skills, derive a shared SKILL.md/scripts/reference style from the existing corpus, or plan broad my-skills cleanup. Always exclude this skill itself unless the user explicitly asks to modify it."
---

# Custom Skill Governance

Use this skill to maintain and consolidate the user's custom skills under `~/.hermes/my-skills/`.

**Scope boundary**: Only operate on `~/.hermes/my-skills/`. Never edit official preset skills under `~/.hermes/skills/`, which is an upstream rsync mirror. During broad `my-skills` consolidation, exclude this skill itself unless the user explicitly asks to modify it.

## Required Approval Gate

Before any operation that deletes, moves, merges, renames, or broadly rewrites skill files, first output an executable plan and wait for the user's approval. Until the user clearly approves, only read files, classify skills, and make recommendations.

The plan must include:

1. **Scope**: Directories to scan or modify, and explicit exclusions.
2. **Inventory**: Skill list, domain groups, and obvious redundant/overlapping/overly narrow candidates.
3. **Actions**: The exact keep, merge, remove, rename, script extraction, and style-standardization actions proposed.
4. **Rationale**: Which existing files or patterns support each judgment.
5. **Risk and rollback**: How valuable content will be preserved, how `git diff` will be reviewed, and which operations need special caution.
6. **Verification**: The cheapest reliable checks to run after implementation, such as `git diff --check`, frontmatter/name checks, script syntax checks, or skill quick validation.

Ask whether the user approves the plan or wants changes to the keep/merge/remove direction. Execute only after approval.

## Operating Principles

1. **Aggregate over fragment**: Merge narrow same-domain skills into broader durable skills to reduce trigger noise and token overhead.
2. **Remove true redundancy**: Delete candidates that are simple enough for Codex natively, one-off task records, stale fallbacks, or fully covered by stronger skills.
3. **Merge overlapping capability**: Combine skills with similar triggers, shared tools, shared credentials, or the same user workflow.
4. **Derive style from the corpus**: Standardize `SKILL.md`, `scripts/`, and `references/` by observing the current highest-quality patterns. Do not invent and append a new style system.
5. **Migrate before deleting**: Preserve unique rules, scripts, pitfalls, and references in the target skill before deleting the source.
6. **Keep diffs reviewable**: Prefer small grouped changes, then show `git status` and a concise diff summary.

## Audit Workflow

1. Build the inventory with `rg --files ~/.hermes/my-skills -g 'SKILL.md'`, excluding this skill.
2. Read each `SKILL.md` frontmatter and heading, then group by directory, tool, domain, and trigger description.
3. Inspect each skill's `scripts/`, `references/`, and `assets/` for orphaned resources, generated caches, missing links, or scripts that are not referenced.
4. Classify each skill as:
   - **remove**: no unique process knowledge, too small, stale, or fully covered elsewhere.
   - **merge**: adjacent domain, similar triggers, shared tools, or same workflow.
   - **standardize**: valuable but inconsistent with the corpus style.
   - **keep**: clear boundary, useful scripts, private workflow knowledge, or high-risk operational constraints.
5. Extract the style consensus from retained skills: frontmatter shape, heading depth, Critical Rules placement, reference links, script command format, verification notes, and language style.
6. Output the plan and wait for user approval.

Detailed preferences and criteria are in [`references/skill-maintenance-prefs.md`](references/skill-maintenance-prefs.md). Read that file before proposing broad changes.
