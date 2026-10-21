---
name: k-behavior-map
description: "Use before and after changing code in a git repo: collects the change's impact list (what it can break, and what new behavior must fit), checks it against the per-repo behavior map with ,behavior-map, maps unmapped areas, and maintains entries (area init, update, add, refresh, promote, resolve)."
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
status: verified # or unverified, when you could not verify it statically; say why in Gotchas
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
  If `save` refuses because the entry changed, run `show <id>` again and merge. A new entry needs no header.
  Use `--force` only to overwrite an entry you did not read.

## Modes

- **before a change**: collect its impact list from the source before the first edit. Two sides:
  - **What it can break.** For each symbol, file, key, or behavior you will change, find every place that depends on it:
    direct and instance callers (`obj.name(`), importers, subclasses and implementations, string keys (config keys, event names, routes, CLI flags, env vars),
    serialized or persisted forms, the tests that cover it, the docs and completions that describe it,
    and the files that historically change with it (`git log --no-follow --full-diff --format= --name-only -- <file> | grep -v '^$' | sort | uniq -c | sort -rn`;
    `--full-diff` lists the commits' other files, and `--no-follow` keeps a `log.follow` config from rejecting it).
  - **What it must fit.** For new or changed behavior, name every domain and scope it has to work in:
    sibling implementations of the same concern (other harnesses, platforms, languages, entry points), config and install paths,
    auth and permissions, persisted data and migrations, error and empty states, docs, completions, tests;
    read how the existing pieces do it, so the new piece follows their pattern and lands everywhere it must.
  - Write the result as a short list before editing (file or scope → why it is on the list → what you will do), read each file on it where it touches the change,
    and add what you learn while editing. Nothing on it is "probably fine" until you read it.
    Then run `,behavior-map affected <the repo paths on that list>`; read every listed entry, and every listed area with `show <area>`.
    Keep those behaviors, or change them on purpose. An `unmapped` directory needs area init only when you will edit or create a file in it.
- **area init**, without asking: when a code path you will edit or create is in an `unmapped` directory, map that area before you edit.
  Skip `/tmp` clones, and sessions that only read or review. Docs-only and test-only changes do not need an area.
  Name the area after the subsystem. Find its behaviors in its entry points, tests, docs, and recent `fix:` commits;
  for a directory the change creates, save the behaviors the change plans (the must-fit side of its impact list).
  Keep at most 10, ranked by user impact. Save each as `status: unverified`; update mode verifies it after the change.
  Claim each directory the area owns with a `dir/` anchor. Never claim a shared directory such as `bin/` or the repo root (`.`).
  A file in a shared directory that belongs to an existing area: add it as a file anchor to that area's closest entry.
  If no area exists yet, map the subsystem the file serves, then anchor the file to that area's closest entry.
  Start a new area only for a new subsystem. Before you start one, run `show --ids` so you do not duplicate an area.
- **repo init**, when the user asks: area init for each main subsystem, at most 30 entries in total. Report what you left out.
- **update**, after the change: run `,behavior-map affected` (`--since <rev>` after a commit).
  Re-verify each listed entry statically (`~/AGENTS.md` §3 step 4) and save it, changed or not, to refresh its fingerprint.
  When an entry's `verify:` names a live check (`~/AGENTS.md` §3 step 4), check it statically instead, set `verify: judgment: <what to read>` or a unit or static command, and keep `status: verified` only if that settles it; otherwise save it `status: unverified`.
  Do the same in refresh mode; in area init and add, write only a unit or static command or `judgment:` as `verify:`.
- **add**: save one verified entry for a behavior you learned the hard way.
- **refresh**: run `,behavior-map check --offline`; re-verify the flagged entries statically; `remove <id>` a behavior that is gone.
- **promote**: when `check` reports a merged overlay, run `,behavior-map promote <branch>`.
  For each conflict, read its `.merge.md`, check the merged code on the default branch, and pipe the result to `,behavior-map resolve <branch> <id>`.
- **drift**: the base entry changed after the branch started. Reconcile with the current base, then `save <id> --rebased`.

Run `,behavior-map drop <branch>` only when the user abandons that branch.
