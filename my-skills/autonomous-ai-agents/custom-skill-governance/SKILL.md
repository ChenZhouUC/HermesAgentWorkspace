---
name: custom-skill-governance
description: Audit, consolidate, and safely evolve custom Hermes skills.
---

# Custom Skill Governance

Use this skill to maintain and consolidate the user's custom skills under `~/.hermes/my-skills/`.

## When to Use

Use it to audit, standardize, consolidate, prune, or safely evolve the
`my-skills` tree. For a single narrow skill edit, apply only the relevant
authoring and validation rules; for broad changes, follow the approval gate
below before modifying other skills.

**Scope boundary**: Only operate on `~/.hermes/my-skills/`. Never edit official preset skills under `~/.hermes/skills/`, which is upstream-managed runtime state. During broad `my-skills` consolidation, exclude this skill itself unless the user explicitly asks to modify it or the Self-Evolution Closeout below calls for a narrow update.

## Required Approval Gate

Before any operation that deletes, moves, merges, renames, or broadly rewrites skill files, first output an executable plan and wait for the user's approval. Until the user clearly approves, only read files, classify skills, and make recommendations.

This gate does not block narrow edits to `custom-skill-governance` itself when the user asked for this skill to self-evolve or when the Self-Evolution Closeout identifies a reusable governance improvement. Do not delete, rename, or radically restructure this skill itself without explicit user approval.

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
2. **Remove true redundancy**: Delete candidates that are simple enough for the main model natively, one-off task records, stale fallbacks, or fully covered by stronger skills.
3. **Merge overlapping capability**: Combine skills with similar triggers, shared tools, shared credentials, or the same user workflow.
4. **Derive style from the corpus**: Standardize `SKILL.md`, `scripts/`, and `references/` by observing the current highest-quality patterns. Do not invent and append a new style system.
5. **Migrate before deleting**: Preserve unique rules, scripts, pitfalls, and references in the target skill before deleting the source.
6. **Keep diffs reviewable**: Prefer small grouped changes, then show `git status` and a concise diff summary.
7. **Optimize for the current Hermes model**: Keep trigger descriptions specific and front-loaded, assume the main model already knows generic engineering practice, and store only reusable procedure, local paths, private policy, scripts, or hard-won pitfalls. Do not bake a model version into durable governance rules.
8. **Fail closed for Feishu groups**: Treat any skill reachable from Feishu group chats as safety-sensitive. Do not broaden group allowlists or executable tool paths unless the user explicitly approves the capability expansion and the sandbox/verifier contract is updated.

## Audit Workflow

1. Build the inventory with `rg --files ~/.hermes/my-skills -g 'SKILL.md'`, excluding this skill.
2. Read each `SKILL.md` frontmatter and heading, then group by directory, tool, domain, and trigger description.
3. Inspect each skill's `scripts/`, `references/`, and `assets/` for orphaned resources, generated caches, missing links, or scripts that are not referenced.
4. Classify each skill as:
   - **remove**: no unique process knowledge, too small, stale, or fully covered elsewhere.
   - **merge**: adjacent domain, similar triggers, shared tools, or same workflow.
   - **standardize**: valuable but inconsistent with the corpus style.
   - **safety-sensitive**: touches Feishu group chat, private people data, credentials, databases, outbound messaging, red-team workflows, or destructive operations.
   - **keep**: clear boundary, useful scripts, private workflow knowledge, or high-risk operational constraints.
5. Extract the style consensus from retained skills: frontmatter shape, heading depth, Critical Rules placement, reference links, script command format, verification notes, and language style.
6. Output the plan and wait for user approval.
7. After approval, migrate useful content before deleting sources, then run the cheapest reliable validation.
8. Finish with the Self-Evolution Closeout.

Detailed preferences and criteria are in [`references/skill-maintenance-prefs.md`](references/skill-maintenance-prefs.md). Read that file before proposing broad changes.

## Hermes Model Refinement Rules

1. **Make `description` carry trigger semantics.** The description is the pre-load routing surface, so include the core user intents, domain, high-risk boundaries, and main tool context there. Avoid vague descriptions like "Use for docs" when the skill only handles a narrow kind of document.
2. **Remove generic model advice.** Do not keep skills that only say things a strong coding model already knows, such as "read files first" or "be careful with tokens", unless tied to a local workflow or non-obvious path.
3. **Avoid stale model/product facts.** Do not hard-code volatile model names, prices, context sizes, limits, or product behavior unless the skill also instructs the agent to verify current official sources or local Hermes config before relying on them.
4. **Move detail down, not out of reach.** Keep `SKILL.md` concise, but preserve real commands, local paths, API quirks, and long explanations in directly linked `references/` or scripts.
5. **Prefer one durable skill over many narrow twins.** Merge overlapping skills when their triggers compete for the same user request and the merged skill remains readable.

## Feishu Group Caution

When a skill affects Feishu group chat behavior:

1. Check `config.yaml` `skills.platform_allowed.feishu_group`, `platform_toolsets.feishu_group`, and `plugins/sandbox/verify.sh` before changing availability.
2. Keep private-only skills out of group allowlists, especially people search, character/persona registries, credentials, broad filesystem access, and shell/process workflows.
3. If adding a group-readable skill that has scripts, explicitly verify the group has no path to execute those scripts unless that exact execution path is intentionally exposed through a sandboxed tool.
4. Do not expose local file paths, private rosters, group persona internals, approval internals, or secrets in group-visible output.

## Self-Evolution Closeout

At the end of every run that uses this skill:

1. Assess whether the run revealed a reusable governance lesson, missing caution, validation gap, or trigger problem.
2. If yes, make the smallest update to this skill or its direct reference file. Prefer adding one concise rule over narrating the whole incident.
3. If no, leave this skill unchanged and say no self-update was needed.
4. Validate the updated skill after self-editing.
