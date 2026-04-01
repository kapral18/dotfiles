---
name: beads
description: |-
  Persist work in the beads DB (inspect/create/claim/update/close/export).
  Use when beads / bdlocal / BEADS_DIR is explicitly mentioned.
---

# Beads Skill

This is mandatory: always check context and offer to persist at ~10% remaining.

Golden rule: always ask user permission before any bead operation (create,
update, status change, close). No exceptions.

Use when:

- the user explicitly wants beads/bdlocal/`BEADS_DIR` work
- the user wants to inspect, create, claim, update, close, export, or otherwise
  manage tasks in the beads DB

Do not use:

- The user is asking for generic planning/task tracking not in Beads.
- The user is asking for git or GitHub operations:
  - git: `~/.agents/skills/git/SKILL.md`
  - GitHub/gh: `~/.agents/skills/github/SKILL.md`

First actions:

1. Confirm `BEADS_DIR` and use `bdlocal` only.
2. Run the read-only intake sequence: `bdlocal prime`, `bdlocal ready --json`,
   `bdlocal blocked --json`.
3. If a mutation is needed, ask permission before naming the exact bead action.

Local policy:

- Run all commands through `bdlocal` (sets
  `BEADS_DB="$BEADS_DIR/.beads/beads.db"` and passes `--sandbox`). Never use
  bare `bd` — it will discover the wrong project or create artifacts in the
  working repo.
- `$BEADS_DIR` resolves dynamically per git repo to `~/beads-data/<repo-name>`.
  Confirm: `echo $BEADS_DIR`.
- Backend is Dolt (server mode). `bd` auto-starts a `dolt sql-server` on first
  use; the server may restart on a different port between sessions.
- Data layout: `$BEADS_DIR/dolt/` (Dolt data), `$BEADS_DIR/metadata.json`
  (backend config), `$BEADS_DIR/dolt-server.port` (current port).
  `$BEADS_DIR/.beads/beads.db` is the discovery anchor directory (not a file).
- Git-free beads mode: do not use beads' internal git sync or remotes. All beads
  data management is local-only. Use `bdlocal export` for backups.
- Installation managed externally (Brewfile: `bd` + `dolt`). Do not
  install/upgrade in session.

Session workflow:

Start:

1. AI context: `bdlocal prime` (outputs optimized workflow context).
2. Run `bdlocal ready --json` to find available work.
3. Run `bdlocal blocked --json` to see what is waiting on other tasks.
4. If claiming existing bead: ask permission, then
   `bdlocal update <id> --claim --json`.
5. If creating new bead: ask permission, then
   `bdlocal create "title" -t <type> -p <priority> -d "context" --estimate 30 --json`.

During work:

6. Review bead: `bdlocal show <id> --json`.
7. On material progress: ask permission, then update notes per Note Curation
   below.
8. On discovering new scope: ask permission to create with
   `--deps discovered-from:<parent-id>`.

End:

9. Ask permission to close: `bdlocal close <id> --reason "Completed" --json`.
10. Local backup:
    `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`

Commands:

Core views:

- `bdlocal ready --json` - find unblocked work
- `bdlocal ready --gated --json` - find molecules waiting on gates for resume
- `bdlocal blocked --json` - find blocked work
- `bdlocal blocked --parent <epic-id> --json` - blocked descendants of epic
- `bdlocal show <id> --json` - view details (supports multiple IDs)
- `bdlocal show <id> --long` - extended metadata (agent identity, gate fields)
- `bdlocal show --current` - show currently active issue
  (in-progress/hooked/last touched)
- `bdlocal prime` - AI-optimized context (auto-detects MCP vs CLI)
- `bdlocal prime --full` - force full CLI output
- `bdlocal info --json` - database path, prefix, server status
- `bdlocal info --schema --json` - schema, tables, config, sample IDs
- `bdlocal count --json` - count and group issues
- `bdlocal status --no-activity --json` - database overview
- `bdlocal stats --json` - alias for status
- `bdlocal stale --days 30 --json` - issues not updated recently
- `bdlocal graph <id>` - ASCII dependency graph (box format)
- `bdlocal graph <id> --compact` - tree format, one line per issue
- `bdlocal graph --all` - all open issues grouped by component
- `bdlocal statuses --json` - list all statuses (built-in and custom)

Issue management:

- `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 -d "..." --estimate 60 --json`
- `bdlocal create "title" --defer "+2d" --due "+1w" --json` (defer/due dates)
- `bdlocal create "title" --parent <id> --json` (create as child of parent)
- `bdlocal create "title" --external-ref "https://github.com/..." --json` (link
  external issue)
- `bdlocal create "title" --deps discovered-from:<parent-id> --json` (create +
  link in one command)
- `bdlocal create "title" -l bug,critical --json` (with labels)
- `bdlocal create "title" --id worker1-100 --json` (explicit ID for parallel
  workers)
- `bdlocal create "title" --dry-run --json` (preview without side effects)
- `bdlocal create "title" --body-file=description.md --json` (description from
  file)
- `echo 'text with backticks' | bdlocal create "title" --stdin --json` (from
  stdin, avoids shell escaping)
- `bdlocal create -f plan.md --json` (multiple issues from markdown file)
- `bdlocal q "quick title"` - quick capture, outputs only the ID (for scripting)
- `bdlocal q "title" -t task -p 1 -l label` - quick capture with options
- `bdlocal update <id> --status open|in_progress|blocked|deferred|closed --json`
- `bdlocal update <id> --claim --json` (atomic: sets assignee +
  status=in_progress; fails if already claimed)
- `bdlocal update <id> --notes|--description|--design|--acceptance|--title "text" --estimate 120 --json`
- `bdlocal update <id> --append-notes "new info" --json` (appends instead of
  replacing)
- `bdlocal update <id> --defer "+2d" --json` (hide from `ready` until date)
- `bdlocal update <id> --due "+1w" --json` (set due date)
- `bdlocal update <id> --add-label <label> --remove-label <label> --json`
- `bdlocal update <id> --external-ref "gh-456" --json`
- `echo 'text' | bdlocal update <id> --description=- --json` (from stdin)
- `bdlocal close <id> --reason "..." --json`
- `bdlocal close <id> --reason "..." --suggest-next --json` (show newly
  unblocked issues)
- `bdlocal close <id> --reason "..." --claim-next --json` (auto-claim next
  highest priority)
- `bdlocal reopen <id> --reason "..." --json`
- `bdlocal edit <id>` - edit in $EDITOR (humans only, not for agents)

Batch operations:

- `bdlocal update <id1> <id2> --status in_progress --json`
- `bdlocal close <id1> <id2> --reason "Done" --json`
- `bdlocal label add <id1> <id2> <label> --json`

List and search:

- `bdlocal list --status open --sort priority --json`
- `bdlocal list --ready --json` (same as `bd ready`, integrated into list)
- `bdlocal list --assignee alice --json`
- `bdlocal list --type bug --json`
- `bdlocal list --parent <epic-id> --json`
- `bdlocal list --title-contains "auth" --json` (case-insensitive substring)
- `bdlocal list --desc-contains "implement" --json`
- `bdlocal list --notes-contains "TODO" --json`
- `bdlocal list --created-after 2025-01-01 --json` (date range filters)
- `bdlocal list --updated-after 2025-06-01 --json`
- `bdlocal list --empty-description --json` (null checks)
- `bdlocal list --no-assignee --json`
- `bdlocal list --no-labels --json`
- `bdlocal list --priority-min 0 --priority-max 1 --json` (priority range)
- `bdlocal list --label auth,backend --json` (AND)
- `bdlocal list --label-any urgent,blocked --json` (OR)
- `bdlocal search "query" --json`
- `bdlocal search "query" --status open --sort priority --long --json`

Comments:

- `bdlocal comments <id> --json` (list comments)
- `bdlocal comments add <id> "text" --json` (add a comment)
- `bdlocal comments add <id> -f notes.txt --json` (from file)

Dependencies:

- `bdlocal dep add <id> <dep-id> --type blocks|related|parent-child|discovered-from --json`
- `bdlocal dep relate <id1> <id2> --json` (bidirectional relates-to link)
- `bdlocal dep unrelate <id1> <id2> --json` (remove relates-to link)
- `bdlocal dep tree <id>`
- `bdlocal dep cycles` (detect circular dependencies)

Labels:

- `bdlocal label add <id> <label> --json`
- `bdlocal label remove <id> <label> --json`
- `bdlocal label list <id> --json`
- `bdlocal label list-all --json` (all unique labels in DB)
- `bdlocal label propagate <parent-id> --json` (propagate label to children)
- Useful: `needs-human-review`, `context-stale`, `blocked-on-external`,
  `ai-generated`

State (labels as cache for operational state):

- `bdlocal state <id> <dimension>` - query current state value
- `bdlocal state list <id> --json` - list all state dimensions on an issue
- `bdlocal set-state <id> <dimension>=<value> --reason "explanation" --json`
  (creates event + updates label atomically)
- Common dimensions: `patrol` (active/muted/suspended), `mode`
  (normal/degraded/maintenance), `health` (healthy/warning/failing)

Gates (async wait conditions):

- `bdlocal gate list` / `bdlocal gate list --all`
- `bdlocal gate show <gate-id>`
- `bdlocal gate check` - evaluate all gates, close resolved ones
- `bdlocal gate check --type=gh:pr|gh:run|timer|bead` - check specific type
- `bdlocal gate check --dry-run` - preview without changes
- `bdlocal gate resolve <gate-id> --reason "Approved"`
- `bdlocal gate discover` - auto-discover CI run IDs for gh:run gates

Molecular chemistry (template-based workflows):

- `bdlocal formula list --json` - list available templates (protos)
- `bdlocal mol show <proto-id> --json` - show template structure and variables
- `bdlocal mol spawn <proto> --var key=value --json` - create wisp (ephemeral,
  default)
- `bdlocal mol pour <proto> --var key=value --json` - create mol (persistent)
- `bdlocal mol run <proto> --var key=value` - spawn + assign + pin (durable
  execution)
- `bdlocal mol bond <A> <B> --type sequential|parallel|conditional --json` -
  combine protos or molecules
- `bdlocal mol distill <epic-id> --as "Template Name" --json` - extract proto
  from ad-hoc work
- `bdlocal mol squash <wisp-id> --summary "summary" --json` - compress wisp to
  permanent digest
- `bdlocal mol burn <wisp-id> --json` - delete wisp without trace
- `bdlocal mol wisp list --json` - list all wisps
- `bdlocal mol wisp gc --json` - garbage collect orphaned wisps
- `bdlocal mol wisp gc --closed --force` - purge all closed wisps
- `bdlocal ship <capability>` - publish capability for cross-project deps

Key-value store (persistent user-defined pairs):

- `bdlocal kv set <key> <value>`
- `bdlocal kv get <key>`
- `bdlocal kv clear <key>`
- `bdlocal kv list --json`

Database:

- `bdlocal export -o issues.jsonl`
- `bdlocal init --server --quiet --skip-hooks --skip-agents` - initialize new
  project (Dolt server mode, git-free)
- `bdlocal import backup.jsonl` - import/upsert from JSONL export

Dolt remote sync (not used in local-only flow):

- `bdlocal dolt push` - push changes to Dolt remote
- `bdlocal dolt pull` - pull from Dolt remote
- `bdlocal dolt commit` - commit pending changes
- `bdlocal dolt show` - check connection status
- `bdlocal backup init /path/to/backup` - register backup destination
- `bdlocal backup sync` - push to backup destination
- `bdlocal backup restore [path]` - restore from backup
- `bdlocal backup status` - show backup status

Maintenance:

- `bdlocal doctor` - basic health check
- `bdlocal doctor --fix` - auto-fix issues
- `bdlocal doctor --fix --yes` - auto-fix without confirmation
- `bdlocal doctor --deep` - full graph integrity validation
- `bdlocal doctor --perf` - performance diagnostics
- `bdlocal doctor --check=pollution --clean` - detect/delete test issues
- `bdlocal admin cleanup --force` (delete all closed issues)
- `bdlocal admin cleanup --older-than 30 --force` (closed 30+ days)
- `bdlocal admin compact --analyze --json` (get candidates for agent review)
- `bdlocal admin compact --apply --id <id> --summary summary.txt`
- `bdlocal admin reset --force` - remove all local beads data
- `bdlocal duplicates --auto-merge --json`
- `bdlocal merge <source-id> --into <target-id> --json`
- `bdlocal rename-prefix <new-prefix> --dry-run`

Deletion:

- `bdlocal delete <id>` (preview mode by default; add `--force` to actually
  delete)
- `bdlocal delete <id> --cascade --force` (recursively delete dependents)

Setup & hooks:

- `bdlocal setup claude|cursor|codex|factory|mux|gemini|aider` - editor
  integration
- `bdlocal setup claude --check` - check if integration is current/stale/missing
- `bdlocal hooks list` - list registered hooks
- `bdlocal hooks install|uninstall` - manage hooks
- `bdlocal hooks run <event>` - run hooks for an event
- `bdlocal human list|respond|dismiss|stats` - human interaction management

Note curation:

1. Read: `bdlocal show <id> --json`
2. Curate: drop stale items, keep only what future agent needs. Use
   COMPLETED/IN_PROGRESS/NEXT structure.
3. Update: `bdlocal update <id> --notes "full refreshed snapshot" --json`
   (replaces entire field)
4. Verify: re-run `bdlocal show <id> --json`

Planning & content strategy:

- Bead content: plain text only. No Markdown. The notes field is the living
  plan.
- Scratchpad: use `/tmp/` for ephemeral thinking. Never save to project.
- Wisdom: maintain a single, accumulated source of truth. Append new knowledge
  to existing wisdom; do not overwrite valid historical knowledge.
- History: only current state matters. Do not preserve old plans.

Dependency thinking:

- Cognitive trap: temporal language inverts dependencies.
- Wrong: "Phase 1 blocks Phase 2" (Phase 1 -> Phase 2)
- Right: "Phase 2 DEPENDS ON Phase 1" (`bdlocal dep add phase2 phase1`)
- Always ask: "What does this task NEED before it can start?"
- Only `blocks` dependencies affect the ready queue. `related`, `parent-child`,
  and `discovered-from` are informational/structural only.

Reference:

Types: `bug`, `feature`, `task`, `epic`, `chore` — always pass `-t` (aliases:
`enhancement`/`feat`→`feature`)

Priorities: `0`=critical, `1`=high, `2`=medium (default), `3`=low, `4`=backlog

Statuses: `open`, `in_progress`, `blocked`, `deferred`, `closed`, `tombstone`
(deleted issue, suppresses resurrections), `pinned` (stays open indefinitely,
for hooks/anchors). Custom statuses can be defined via
`bd config set status.custom "in_review:active,qa_testing:wip"` with categories:
`active` (included in ready), `wip`, `done`, `frozen`.

Dependencies: `blocks` (hard — affects ready queue), `related` (soft),
`parent-child` (hierarchy), `discovered-from` (provenance)

Advanced patterns:

Wisdom beads (accumulated knowledge):

1. Create: `bdlocal create "wisdom - <topic>" -t task -p 2 --json`
2. Link: `bdlocal dep add <working-id> <wisdom-id> --type related --json`
3. Maintain: update wisdom bead notes with curated takeaways each session.
4. Load and follow e2e when accessing wisdom/knowledge beads:
   - Load entire content into memory once:
     `bdlocal show <wisdom-id> --json 2>&1 | jq -r '.[0].notes'`
   - Read the entire wisdom bead content fully without skimming or skipping
     sections.
   - Follow instructions to the letter; do not cherry-pick or skip parts.
   - After updating a wisdom bead, ask user permission to re-upload new contents
     into context.
   - Do not repeatedly grep/query wisdom beads if it's already loaded in memory;
     recall from memory.
   - Treat wisdom bead instructions as binding within the scope of the current
     task.

Epic with external link:

- `bdlocal create "Auth epic" -t epic -p 1 --external-ref "https://github.com/.../issues/123" --json`

Molecular chemistry patterns:

- Proto = reusable template (epic with `template` label)
- Mol = persistent instance (real issues from template)
- Wisp = ephemeral instance (operational work, no audit trail; stored with
  Ephemeral=true, not exported)
- Use wisps for patrol cycles, diagnostics, one-shot orchestration
- Use mols for repeatable workflows needing audit trail
- `bd mol run` for durable work that should survive crashes (spawn + assign +
  pin)

Troubleshooting:

- Confirm `BEADS_DIR` is set: `echo $BEADS_DIR`.
- Version: `bdlocal version` (expect >= 0.63).
- Health: `bdlocal doctor` / `bdlocal doctor --fix`.
- "database not found on Dolt server": a stale or wrong dolt server is running.
  `doctor --fix` often cannot recover this. Reliable fix:
  1. `pkill -f 'dolt sql-server'` (kill ALL dolt servers)
  2. Retry any `bdlocal` command — it auto-starts a fresh server from the
     correct data directory (`$BEADS_DIR/dolt/`). Root cause: multiple dolt
     servers from different projects can run concurrently on different ports; bd
     may connect to the wrong one.
- "embedded Dolt requires CGO": `metadata.json` is missing
  `"dolt_mode": "server"`. Check `$BEADS_DIR/metadata.json` — it must contain
  `"backend": "dolt"` and `"dolt_mode": "server"`.
- Data recovery: `$BEADS_DIR/.beads/issues.jsonl` contains the last JSONL
  backup. If the Dolt server is unrecoverable, re-import:
  `pkill -f 'dolt sql-server' && bdlocal import $BEADS_DIR/.beads/issues.jsonl`.

Output:

- Summarize the bead(s) involved, the exact mutation proposed or performed, and
  the verification result.
- Keep generic planning advice outside this skill unless the user explicitly
  wants it persisted in Beads.
