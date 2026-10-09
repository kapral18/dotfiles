---
sidebar_position: 5
---

# Memory and Handoffs

Three plain CLIs. Nothing is injected into a session automatically.

## `,handoff` — task progress across sessions and harnesses

Use it when you stop in one harness and continue in another, or before a long break.

```sh
,handoff save auth-fix <<'NOTE'
Goal: …
Decisions: …
State: …
Open: …
Files: …
Verify: …
NOTE
,handoff list            # this repo, newest first (--all for every repo)
,handoff show auth-fix   # --prev for the previous version
```

- Notes live in `~/.local/share/agent-handoffs/<repo>/<topic>.md` (override with `AGENT_HANDOFF_DIR`).
- `<repo>` is the main checkout's directory name, so all worktrees of a repo share one namespace; outside git it is `global`.
- Saving keeps the previous version as `<topic>.prev.md`. Notes over 4 KB save with a warning.
- The `k-handoff` skill tells agents what to write on "handoff X" and how to resume on "continue X": treat the note as a starting point and re-check the files and git state it names.

## `,behavior-map` — critical behaviors per repo

A short map of the behaviors a user or caller relies on, seen from their side. It replaces the old `.mermaids/` file inventories:
entries name at most three code entry points ("anchors"), and agents find internals at runtime.

```sh
,behavior-map show               # status line + index; `show <area>` or `show <id>` for full entries
,behavior-map save <id> < entry  # write; keep the header line that `show <id>` printed
,behavior-map affected [paths]   # entries and areas a planned or finished change touches; unmapped dirs
,behavior-map check              # stale, broken, drifted, conflicting entries; merged or gone overlays
,behavior-map promote <branch>   # merge a merged branch's overlay into the base map
```

Storage: `~/.local/share/k-ai-behavior-map/<repo>/` (override with `AGENT_BEHAVIOR_MAP_DIR`). `<repo>` is the main checkout's directory name; a checkout named `main`, `master`, or `trunk` (`~/work/<repo>/main`) uses its parent's name.

| Layer                       | Path                         | Written from                                |
| --------------------------- | ---------------------------- | ------------------------------------------- |
| Base map                    | `base/<area>/<name>.md`      | the default branch                          |
| Branch overlay              | `branches/<slug>/<area>/...` | that branch, in any worktree                |
| Fork copy of the base entry | `<name>.base.md` in overlay  | the CLI, when a branch first edits an entry |

- One Markdown file per entry: YAML front matter (`id`, `status`, `anchors`, `verify`, `verified_date`, optional `states`, and a `fingerprint` that `save` computes) and a body of `Trigger:`, `Expect:`, `Must not:`, `Gotchas:` lines.
- Concurrent sessions: every write takes a repo lock; `save` also refuses when the entry changed since the session read it.
- `show` on a branch merges base and overlay. `drift` means the base entry changed after the branch started; `stale` means the anchored content changed since the entry was saved; `broken` means an anchor no longer resolves.
- `promote` copies unchanged-base entries, three-way merges the rest with `git merge-file`, and keeps conflicts in `.merge.md` files until `resolve`.
- An area owns the directories its entries claim with `dir/` anchors; a file anchor claims only that file. `affected` lists entries anchored to a changed file, whole areas that own one, and paths in no area.
- The `k-behavior-map` skill owns the lifecycle. Before a code change it runs `affected` on the planned paths and maps an unmapped area first (area init, at most 10 entries, verified with the area's tests; skipped for `/tmp` clones and read-only sessions).
  In Claude Code the `behavior-map-guard` mod refuses the first edit in an unmapped directory and notes mapped entries an edit touches. Bash-only edits rely on the SOP, not the mod ([Claude mods](tool-configs/claude-gemini.md#mods)).
  After the change the skill updates the listed entries. Repo-wide init, add, refresh, promote and resolve are the other modes.

## `,ai-kb` — durable, reusable knowledge

A local knowledge base of short capsules with hybrid (BM25 + vector) search.

```sh
,ai-kb search "<literal identifiers or error text>" --limit 5 --json
,ai-kb remember --title … --body … --kind gotcha --scope project --workspace "$(pwd)" --source … --confidence 0.9 --domain …
,ai-kb get <id> --json
```

- Search when starting on a subsystem you may have touched before, or on an unfamiliar error. Treat hits as leads.
- Remember only verified, reusable gotchas and recipes with literal identifiers and a source; never task progress.
- `remember` refuses title collisions and near-duplicates; `--supersedes <id>` amends a stale capsule in place.
- `,ai-kb curate` dedupes and decays capsules; run it by hand when the store grows noisy.

The `k-ai-kb` skill holds the search and write rules; `~/.agents/skills/k-ai-kb/references/cli.md` holds the flag contract.
