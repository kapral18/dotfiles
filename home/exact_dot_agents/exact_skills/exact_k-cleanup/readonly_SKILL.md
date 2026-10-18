---
name: k-cleanup
description: "Use before reporting finished work: remove task leftovers, restore your stashes, keep branches and worktrees."
---

# Cleanup

`~/AGENTS.md` §3 step 7 runs this before every change report, and Done includes it.

Handle what the task left on this machine: new or newly exposed files outside the change, stale ignored files at paths the change removed or moved, stashes, branches, worktrees, processes,
and what a feature the task added and then dropped left behind.
Files the request asked for are the change, not leftovers.
Do the cleanup yourself: never hand the user a cleanup step.
A deletion the task needs that these rules do not allow goes under `Decision needed:`, not into the report as a command for the user.

- Delete scratch files (not worktrees) this task created that no later step or turn reads, and stop processes it started that the request does not need.
  Keep a `k-review` Verify baseline until the task ends.
- Apart from the next bullet, delete an exposed or stale file only if a tool regenerates it (build output, caches, virtualenvs) and the change removed or moved the path it belongs to.
- For a feature this task added that the finished change no longer has, remove what it left on this machine:
  deployed copies its deploy step does not remove (chezmoi targets outside `exact_` folders, installed binaries, service files:
  unload a loaded service first),
  state it generated at the paths it wrote to (indexes, caches, logs), including what other sessions wrote there while it existed,
  its `,behavior-map` entries (`,behavior-map remove <id>`), its `,ai-kb` capsules (`,ai-kb remember --supersedes <id>` with a note that the feature is gone),
  and git index entries of its deleted files (`git rm --cached`).
  These are part of removing the feature and need no question under `~/AGENTS.md` §1.
  Content the user wrote through the feature (notes, preferences) goes under `Decision needed:`.
  Nothing that existed before the feature is covered.
- Keep any other file in place. Keep branches and worktrees, including scratch ones.
- Never run `git stash drop`. Restore a stash this task created with `git stash pop stash@{N}`, where N is its index in `git stash list`.
- If the pop fails or conflicts, keep the stash, leave the conflicted files as they are, never run `git reset --hard` to make it apply, and list both under `Open:` (a blocker, not a step for the user).
- List what you removed and kept under `Assumptions:`, except scratch files under `/tmp` or the harness scratch directory.
  Mark each kept file that git would now commit (`git status --porcelain`).
