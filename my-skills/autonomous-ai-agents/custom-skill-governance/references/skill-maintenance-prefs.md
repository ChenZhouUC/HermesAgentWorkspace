# Custom Skill Maintenance Preferences

When maintaining or refactoring the user's custom skills (`~/.hermes/my-skills/`), strictly adhere to these architectural preferences gathered from the user's workflows.

## Required Approval Gate

Before modifying, moving, merging, renaming, or deleting any skill other than `custom-skill-governance` itself, produce a concrete plan and ask the user to approve it. Do not treat a broad request such as "收敛一下" as approval to immediately rewrite the tree.

The plan should name exact source and target skill directories, explain the reason for each proposed action, and identify any content that will be migrated before deletion.

## Consolidation Criteria

### Remove

Mark a skill as a removal candidate when one or more of these are true:

1. It only explains generic model behavior or common CLI usage that Codex can handle without a skill.
2. It stores a one-off task log, temporary workaround, stale fallback, or historical debugging transcript rather than reusable procedure.
3. Its trigger scope is fully covered by another broader skill and it contains no unique scripts, references, or hard-won pitfalls.
4. Its scripts are broken, unused, trivial, or no better than a short shell command, and there is no reusable domain knowledge around them.

### Merge

Mark skills as merge candidates when they share the same user intent, toolchain, credentials, operational risk, or troubleshooting path. Prefer merging narrow skills into the broader, more durable container.

When merging:

1. Preserve unique rules, exact commands, API pitfalls, environment assumptions, and scripts.
2. Move scripts/references into the target skill only when still useful, then update paths and links.
3. Delete duplicated prose after the target skill contains the useful parts.
4. Keep the target `description` broad enough to trigger for the merged use cases.

### Keep

Keep a skill separate when it has a clear trigger boundary, non-trivial scripts, private workflow knowledge, high-risk operational constraints, or enough depth that merging would make the target skill noisy.

## Style Standardization

Do not invent a new style guide. Derive the standard from the current `my-skills` corpus, especially the clearest high-value skills.

Use these observations when extracting the style:

1. Prefer concise YAML frontmatter with only `name` and `description`.
2. Keep the first heading aligned with the skill name and domain.
3. Put hard constraints and pitfalls near the top when mistakes are costly.
4. Link detailed references from `SKILL.md` instead of embedding long background material.
5. Keep script commands in fenced `bash` blocks and prefer absolute paths when the skill may run from arbitrary working directories.
6. Avoid adding README, changelog, quick reference, or other auxiliary docs unless the skill runtime requires them.

## Script and Reference Hygiene

1. **Token Efficiency (Script Extraction)**: Keep `SKILL.md` bodies concise to reduce context overhead. Extract substantial inline Python/Bash into separate files under the skill's `scripts/` directory, and reference those files from the markdown.
2. **Generic Naming Convention**: Prefer broad, scalable directory names over narrow, tool-specific ones. This provides generic containers for future tools (e.g., use `editor-configs` instead of `macvim-ops`, use `mobile-dev-workflows` instead of `flutter-development`).
3. **Atomic Operations**: When authoring new scripts, especially API wrappers like Feishu, ensure operations are atomic. Snapshot existing state before destructive writes, and implement safe rollbacks on connection drops such as `RemoteDisconnected`.
4. **No Orphaned Resources**: Every retained reference or script should be reachable from `SKILL.md` or clearly used by another retained script.
5. **No Generated Cache**: Remove generated caches such as `__pycache__/` when they are inside skill directories and not intentionally tracked. Prefer explicit Python cache cleanup with `pyclean <skill-or-my-skills-path>` when `pyclean` is available. If `pyclean` is not installed, fall back to a narrow `find` command scoped to `~/.hermes/my-skills`, then report that fallback in the summary.

## Verification

After approved changes:

1. Run `git status --short` and inspect the relevant diff.
2. Run `git diff --check` for whitespace and patch hygiene.
3. Validate YAML frontmatter and skill names. Use the system `quick_validate.py` script when available.
4. For changed scripts, run the cheapest syntax or dry-run check available, such as `python -m py_compile` for Python scripts.
5. Report checks that could not be run and why.
