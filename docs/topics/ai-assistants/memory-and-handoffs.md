---
sidebar_position: 5
---

# Memory and Handoffs

Two plain CLIs, both on demand. Nothing is injected into a session automatically.

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
