---
name: k-behavior-map
description: "Use before and after changing code in a git repo: checks the change against the per-repo behavior map with ,behavior-map, maps unmapped areas, and maintains entries (area init, update, add, refresh, promote, resolve)."
---

# Behavior map

`,behavior-map` keeps one map per repo; all worktrees share the base map and each branch writes only its own overlay.
Run `,behavior-map --help` for the interface.

## Entry

One behavior a user or caller relies on, where a break hurts and the code does not make it obvious.
No file lists or internals: the anchors are entry points, and you find the rest at runtime.

```markdown
---
id: <area>/<name>
status: verified # or unverified, when you could not run verify; say why in Gotchas
anchors: # 1-3 repo-relative entry points; `dir/` claims a directory for the area
  - path/to/file.py::symbol
  - path/to/
verify: <command, or `judgment: <what to inspect>`>
verified_date: YYYY-MM-DD
states: # optional, only for a real state machine
  - idle --enter--> preview
---

Trigger: how a user or caller starts it.
Expect: the observable result.
Must not: what must never happen.
Gotchas: the trap that cost time.
```

`save` adds a `fingerprint` of the anchored content; the entry is `stale` once that content changes.
`Trigger:` and `Expect:` are required. A continuation line starts with two spaces, or with a dash and a space.
The body is at most 1200 bytes.

## Read and write

- `show` prints a status line and an index; `show <area>` or `show <id>` prints full entries.
- Entries are leads. Check flagged ones (`invalid`, `broken`, `stale`, `drift`, `conflict`, `unverified`) against the code first.
- To write, edit the `show <id>` output, keep its `<!-- behavior-map ... -->` line, and pipe it to `,behavior-map save <id>`.
  If `save` refuses because the entry changed, run `show <id>` again and merge. Use `--force` only for a new entry nobody else edits.

## Modes

- **before a change**: run `,behavior-map affected <paths you plan to edit>`.
  Read every listed entry, and every listed area with `show <area>`. Keep those behaviors, or change them on purpose.
- **area init**, without asking: when `affected` reports a planned code path as `unmapped`, map that area before you edit.
  Skip `/tmp` clones, and sessions that only read or review. Docs-only and test-only changes do not need an area.
  Name the area after the subsystem. Find its behaviors in its entry points, tests, docs, and recent `fix:` commits.
  Keep at most 10, ranked by user impact. Verify each with the area's existing tests, then save.
  Claim each directory the area owns with a `dir/` anchor. Never claim a shared directory such as `bin/` or the repo root (`.`).
  A file in a shared directory that belongs to an existing area: add it as a file anchor to that area's closest entry.
  Start a new area only for a new subsystem. Before you start one, run `show --ids` so you do not duplicate an area.
- **repo init**, when the user asks: area init for each main subsystem, at most 30 entries in total. Report what you left out.
- **update**, after the change: run `,behavior-map affected` (`--since <rev>` after a commit).
  Re-verify each listed entry and save it, changed or not, to refresh its fingerprint.
- **add**: save one verified entry for a behavior you learned the hard way.
- **refresh**: run `,behavior-map check --offline`; re-verify the flagged entries; `remove <id>` a behavior that is gone.
- **promote**: when `check` reports a merged overlay, run `,behavior-map promote <branch>`.
  For each conflict, read its `.merge.md`, check the merged code on the default branch, and pipe the result to `,behavior-map resolve <branch> <id>`.
- **drift**: the base entry changed after the branch started. Reconcile with the current base, then `save <id> --rebased`.

Run `,behavior-map drop <branch>` only when the user abandons that branch.
