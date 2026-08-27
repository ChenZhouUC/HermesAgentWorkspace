---
applyTo: "**"
---

# Hermes Patch Maintenance Checklist

When working in this repo and the task involves creating, modifying, or removing any local patch, treat the following as a mandatory checklist. The goal is **zero stale text** — every artifact that references a patch must stay in sync.

## 1. Patch content verification

- After editing patched source in `hermes-agent/`, regenerate the diff and verify it applies cleanly to a fresh HEAD:
  ```bash
  cd ~/.hermes/hermes-agent
  git stash
  git apply --check ~/.hermes/patches/local-patches.diff
  git stash pop
  ```
- Run the **behavioral verification** that `hermes-update.sh` defines for the affected patch. Each patch has a corresponding verification block in the script — find it by searching for the `_*_PATCH_OK` flag variables. Confirm the check passes.
- Run `bash ~/.hermes/hermes-update.sh --self-test-patch-gates`. It must prove every active `_*_PATCH_OK` and archived `_ARCHIVED_*_OK` declaration has a success assignment and is consumed by the Step 8c aggregate gate. A sentinel block that exists but is omitted from the aggregate condition is a release-blocking defect.
- Run `python3 ~/.hermes/scripts/test_patch_evidence.py --report-json <path>`. Each active engineering PATCH validation function must resolve to one full pytest node ID from a test file declared by that PATCH, produce a clean passed JUnit outcome, and collectively execute every owned Python production file; shared nodes, undeclared test files, partial implementation coverage, ambiguous names, missing collection, skip, xfail, error, or failure are release-blocking. Archive prose or a stale historical test name is not evidence: upstream-absorbed behavior runs its retained test/CLI/behavior probe, while a requirement-retired PATCH executes a secret-safe, provider/model-independent negative capability audit.
- If adding a **new** patch: assign a stable semantic ID in the form `PATCH-<DOMAIN>-<INVARIANT>` (IDs are not sequential), add the target file(s) to the `PATCHED_FILES` array in `hermes-update.sh`, add a corresponding behavioral verification block with a new `_*_PATCH_OK` flag, and gate that flag into the diff-refresh condition alongside the existing flags.

## 2. Documentation updates

Every patch change must be reflected in **all** of these locations — check each one by searching for existing patch references and updating them:

| File                 | What to look for and update                                                                                                                                                                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `patches/PATCHES.md` | The `### [PATCH-<DOMAIN>-<INVARIANT>]` entry for the affected patch (problem, fix, verification, status, upstream absorption condition). Also update lifecycle and `PATCHED_FILES` sections if their contracts changed. |
| `README.md`          | The update steps table row that summarizes patch re-application, and the local-patches paragraph that lists which patches are auto-managed. Find these by searching for "patch" or the semantic PATCH identifier.       |
| `hermes-update.sh`   | The numbered step list in the header comment block at the top of the script — keep it in sync if steps were added, removed, or renumbered.                                                                              |

When **retiring** a patch: move its single definition block under the appropriate Archive section and record whether it is `✅ 已上游合并` or `🗄️ 已归档`. Remove a path from `PATCHED_FILES` only when no other active patch still owns that file; keep an explicit regression sentinel when the archive entry requires one, and clean up current-state references in `README.md`.

## 3. Update pipeline verification

After all edits are done, verify the full patch re-application flow in `hermes-update.sh` will work:

- `bash -n ~/.hermes/hermes-update.sh` — syntax check, zero errors.
- `bash ~/.hermes/hermes-update.sh --self-test-patch-gates` — active/archive gate declarations exactly match the Step 8c aggregate condition.
- `python3 ~/.hermes/scripts/test_patch_evidence.py` — all active/archive definitions have exact four-section shape and current executable evidence; patched tests collect successfully.
- `bash ~/.hermes/hermes-update.sh --final-audit --json` — after the last reconcile and all script/doc edits, the per-PATCH matrix, canonical suite, replay closure, docs/Wiki, runtime verifier/PIDs, transaction, and final cleanup all report `status=ok / mode=full`.
- `patches/local-patches.diff` contains **no** conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- Patched files currently in `hermes-agent/` contain **no** conflict markers.
- `patches/.local-patches.base` is consistent with the current upstream HEAD (or will be written on next successful refresh).

## 4. Commit discipline

- All patch-related changes (script + diff + docs) go in a **single commit** so they cannot diverge.
- Commit message should reference the upstream commit hash and affected semantic PATCH IDs when the commit is patch-related.
- If the user explicitly requests commit, run the mandatory commit approval hook, create the outer-repo commit only, then rerun `--final-audit --json` on the committed content. A pre-commit formatter can change Python/Markdown and recreate caches, so post-commit audit and clean status are part of completion. Push remains a separate confirmed/approved action.
