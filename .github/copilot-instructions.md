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
- If adding a **new** patch: assign the next PATCH-N number, add the target file(s) to the `PATCHED_FILES` array in `hermes-update.sh`, add a corresponding behavioral verification block with a new `_*_PATCH_OK` flag, and gate that flag into the diff-refresh condition alongside the existing flags.

## 2. Documentation updates

Every patch change must be reflected in **all** of these locations — check each one by searching for existing patch references and updating them:

| File                 | What to look for and update                                                                                                                                                                                                       |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `patches/PATCHES.md` | The `### [PATCH-N]` entry for the affected patch (problem, fix, status, version). Also the management mechanism sections (lifecycle tree, safety mechanisms, known limitations, `PATCHED_FILES` listing) if any of those changed. |
| `README.md`          | The update steps table row that summarizes patch re-application, and the local-patches paragraph that lists which patches are auto-managed. Find these by searching for "patch" or the PATCH-N identifier.                        |
| `hermes-update.sh`   | The numbered step list in the header comment block at the top of the script — keep it in sync if steps were added, removed, or renumbered.                                                                                        |

When **retiring** a patch (upstream merged it): change its status in `PATCHES.md` to `✅ 已上游合并`, remove the file from `PATCHED_FILES`, remove its verification block and `_*_PATCH_OK` flag from the script, and clean up references in `README.md`.

## 3. Update pipeline verification

After all edits are done, verify the full patch re-application flow in `hermes-update.sh` will work:

- `bash -n ~/.hermes/hermes-update.sh` — syntax check, zero errors.
- `patches/local-patches.diff` contains **no** conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
- Patched files currently in `hermes-agent/` contain **no** conflict markers.
- `patches/.local-patches.base` is consistent with the current upstream HEAD (or will be written on next successful refresh).

## 4. Commit discipline

- All patch-related changes (script + diff + docs) go in a **single commit** so they cannot diverge.
- Commit message should reference the upstream commit hash and affected PATCH-N numbers.
