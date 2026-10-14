---
name: k-cleanup
description: "Use before reporting finished work: remove task leftovers, restore your stashes, keep branches and worktrees."
---

# Cleanup

`~/AGENTS.md` §3 step 7 runs this before every change report, and Done includes it.

Handle what the task left on this machine: new or newly exposed files outside the change, stale ignored files at paths the change removed or moved, stashes, branches, worktrees, and processes.
Files the request asked for are the change, not leftovers.

- Delete scratch files (not worktrees) this task created that no later step or turn reads, and stop processes it started that the request does not need.
  Keep a `k-review` Verify baseline until the task ends.
- Delete an exposed or stale file only if a tool regenerates it (build output, caches, virtualenvs) and the change removed or moved the path it belongs to.
- Keep any other file in place. Keep branches and worktrees, including scratch ones.
- Never run `git stash drop`. Restore a stash this task created with `git stash pop stash@{N}`, where N is its index in `git stash list`.
- If the pop fails or conflicts, keep the stash, leave the conflicted files as they are, never run `git reset --hard` to make it apply, and list both under `Open:`.
- List what you removed and kept under `Assumptions:`, except scratch files under `/tmp` or the harness scratch directory.
  Mark each kept file that git would now commit (`git status --porcelain`).
