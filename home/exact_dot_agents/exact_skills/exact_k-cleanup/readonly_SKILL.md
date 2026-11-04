---
name: k-cleanup
description: "Use during work and before reporting finished work: remove unused task support files, restore your stashes, keep branches and worktrees."
---

# Cleanup

Apply `~/AGENTS.md` §3's temporary-file rule throughout work; step 7 is the final cleanup sweep, and Done includes it.

Handle what the task left on this machine: new or newly exposed files outside the change, stale ignored files at paths the change removed or moved, stashes, branches, worktrees, processes,
and what a feature the task added and then dropped left behind.
Files the request asked for are the change, not leftovers.
Do the cleanup yourself: never hand the user a cleanup step you can take.
A deletion the task needs that these rules do not allow goes under `Decision needed:`, not into the report as a command for the user.

- Put temporary support files under `/tmp`, including drafts, probes, logs, review packets, disposable copies and source clones.
  Delete files this session owns as soon as no remaining task step, review or agreed handoff needs them; stop its unneeded processes too.
  This includes superseded fix copies and Verify baselines once their dependent reviews finish.
  Hypothetical future reuse or a claim linking to a file is not a reason to retain it.
  Do not delete another session's active files or infer ownership from location or age;
  preserve unrelated user files, branches and worktrees.
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
- If the pop fails or conflicts, keep the stash, leave the conflicted files as they are, never run `git reset --hard` to make it apply, and list both under `Open:`, naming the conflicted files and the stash for the user to resolve.
- List what you removed and kept under `Assumptions:`, except temporary support files under `/tmp`.
  Mark each kept file that git would now commit (`git status --porcelain`).
