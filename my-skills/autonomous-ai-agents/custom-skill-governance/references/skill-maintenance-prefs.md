# Custom Skill Maintenance Preferences

When maintaining or refactoring the user's custom skills (`~/.hermes/my-skills/`), strictly adhere to these architectural preferences gathered from the user's workflows.

## Required Approval Gate

Before modifying, moving, merging, renaming, or deleting any skill other than `custom-skill-governance` itself, produce a concrete plan and ask the user to approve it. Do not treat a broad request such as "收敛一下" as approval to immediately rewrite the tree.

The plan should name exact source and target skill directories, explain the reason for each proposed action, and identify any content that will be migrated before deletion.

## Consolidation Criteria

### Remove

Mark a skill as a removal candidate when one or more of these are true:

1. It only explains generic model behavior or common CLI usage that the main model can handle without a skill.
2. It stores a one-off task log, temporary workaround, stale fallback, or historical debugging transcript rather than reusable procedure.
3. Its trigger scope is fully covered by another broader skill and it contains no unique scripts, references, or hard-won pitfalls.
4. Its scripts are broken, unused, trivial, or no better than a short shell command, and there is no reusable domain knowledge around them.
5. It hard-codes volatile model/product facts such as model limits, prices, or UI behavior without a workflow to verify current official sources.

Usage telemetry is supporting evidence only. Do not remove a custom skill solely
because `skills/.usage.json` has no entry or reports zero views/uses: external
skill accounting may be incomplete, and recently added skills have not had time
to accumulate meaningful history. Require corroborating evidence from content,
overlapping triggers, broken resources, or explicit user intent.

### Merge

Mark skills as merge candidates when they share the same user intent, toolchain, credentials, operational risk, or troubleshooting path. Prefer merging narrow skills into the broader, more durable container.

When merging:

1. Preserve unique rules, exact commands, API pitfalls, environment assumptions, and scripts.
2. Move scripts/references into the target skill only when still useful, then update paths and links.
3. Delete duplicated prose after the target skill contains the useful parts.
4. Keep the target `description` broad enough to trigger for the merged use cases.
5. Remove links to non-existent references instead of carrying dead examples forward.

### Keep

Keep a skill separate when it has a clear trigger boundary, non-trivial scripts, private workflow knowledge, high-risk operational constraints, or enough depth that merging would make the target skill noisy.

Keep private or high-risk skills separate even when adjacent to a broader workflow if merging would make them reachable from a wider context. Examples include Feishu people search, private character/persona registries, database credentials, outbound group messaging, and red-team procedures.

## Style Standardization

Do not invent a new style guide. Derive the standard from the current `my-skills` corpus, especially the clearest high-value skills.

Use these observations when extracting the style:

1. Prefer concise YAML frontmatter with only `name` and `description`.
2. Put the most important trigger words and safety boundaries early in `description`; this is the routing surface before `SKILL.md` is loaded.
3. Keep the first heading aligned with the skill name and domain.
4. Put hard constraints and pitfalls near the top when mistakes are costly.
5. Link detailed references from `SKILL.md` instead of embedding long background material.
6. Keep script commands in fenced `bash` blocks and prefer absolute paths when the skill may run from arbitrary working directories.
7. Avoid adding README, changelog, quick reference, or other auxiliary docs unless the skill runtime requires them.
8. Use direct, imperative instructions. Do not add meta-explanations about why every rule exists unless the caution would otherwise be easy to misapply.

## Hermes Model-Oriented Refinement

Treat the current main model as strong at generic reasoning and weak only where it lacks local context, private operational policy, deterministic scripts, or fresh product facts.

1. Keep local facts that matter: paths, config keys, allowlists, script entrypoints, API quirks, rollback rules, and known failure modes.
2. Remove generic coaching: "be concise", "think step by step", "read the file", and similar broad advice rarely earns its token cost inside a skill.
3. Avoid fossilized model facts. If a skill depends on current model, OpenAI product, or Hermes runtime behavior, instruct the agent to check official docs or local config at runtime instead of relying on a remembered number.
4. Prefer small, stable skills with clear boundaries over many micro-skills that fight for the same trigger.
5. When a skill's description becomes long, front-load the trigger and safety boundary before secondary examples.

## Feishu Group Safety

Feishu group contexts are safety-sensitive because group-visible output and group tool surfaces can expose private local state.

1. Before changing group-readable skills, inspect `config.yaml` `skills.platform_allowed.feishu_group`, `platform_toolsets.feishu_group`, and `plugins/sandbox/verify.sh`.
2. Do not add private-only skills to the group allowlist: people search, character voices/persona registries, database credentials, local shell/process workflows, or broad filesystem skills.
3. If adding a group-readable skill that contains scripts, document why group users still cannot execute those scripts unless a controlled sandbox tool intentionally maps a fixed action to them.
4. Preserve verifier comments when the safety argument matters. If changing allowlists or toolsets, update the verifier and docs in the same change.
5. In group-output skills, explicitly forbid leaking local paths, secrets, private rosters, private persona data, and approval/sandbox internals unless the user is deliberately debugging as owner/admin.

## Script and Reference Hygiene

1. **Token Efficiency (Script Extraction)**: Keep `SKILL.md` bodies concise to reduce context overhead. Extract substantial inline Python/Bash into separate files under the skill's `scripts/` directory, and reference those files from the markdown.
2. **Generic Naming Convention**: Prefer broad, scalable directory names over narrow, tool-specific ones. This provides generic containers for future tools (e.g., use `editor-configs` instead of `macvim-ops`, use `mobile-dev-workflows` instead of `flutter-development`).
3. **Atomic Operations**: When authoring new scripts, especially API wrappers like Feishu, ensure operations are atomic. Snapshot existing state before destructive writes, and implement safe rollbacks on connection drops such as `RemoteDisconnected`.
4. **No Orphaned Resources**: Every retained reference or script should be reachable from `SKILL.md` or clearly used by another retained script.
5. **No Generated Cache**: Remove generated caches such as `__pycache__/` when they are inside skill directories and not intentionally tracked. Prefer explicit Python cache cleanup with `pyclean <skill-or-my-skills-path>` when `pyclean` is available. If `pyclean` is not installed, fall back to a narrow `find` command scoped to `~/.hermes/my-skills`, then report that fallback in the summary.

## Self-Evolution Discipline

At the end of each governance run, update `custom-skill-governance` itself only when there is a reusable lesson.

Good self-updates:

1. Add a missing safety class or approval gate discovered during the run.
2. Add a validation check that would have caught a real issue.
3. Add a consolidation criterion that changes future decisions.
4. Tighten a trigger description that caused or could cause misrouting.

Bad self-updates:

1. Logging the whole incident as history.
2. Adding a one-off filename that will not matter again.
3. Repeating rules already present in both `SKILL.md` and this reference.
4. Expanding this skill every time just because it was used.

## Verification

After approved changes:

1. Run `git status --short` and inspect the relevant diff.
2. Run `git diff --check` for whitespace and patch hygiene.
3. Validate YAML frontmatter and skill names. Use the system `quick_validate.py` script when available.
4. For changed scripts, run the cheapest syntax or dry-run check available, such as `python -m py_compile` for Python scripts.
5. Report checks that could not be run and why.
6. Run both the generic skill validator and Hermes' `tools/skill_linter.py` when available, but interpret results through this repository's declared style. Missing `version`, `author`, `license`, or `metadata.hermes` is advisory because local skills intentionally prefer `name` + `description`; overlong descriptions, broken resource links, invalid frontmatter, and executable-script failures remain actionable.
