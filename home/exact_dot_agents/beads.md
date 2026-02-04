# Beads Workflow

This is mandatory: always check context and offer to persist at ~10% remaining.

Golden rule: always ask user permission before any bead operation (create, update, status change, close). No exceptions.

Local policy:
- Run all commands through `bdlocal` (invokes `bd --db "$BEADS_DIR/.beads/beads.db" --no-auto-flush --no-auto-import --no-daemon).
- `$BEADS_DIR` is the current workspace root. Confirm: `echo $BEADS_DIR`.
- Data lives in `$BEADS_DIR/.beads/`.
- Git-free beads mode: do not use beads' internal git sync or remotes. All beads data management is local-only. Use `bdlocal export` for backups.
- Installation managed externally (Brewfile). Do not install/upgrade `bd` in session.

Session workflow:

Start:
1. Check for upgrades: `bdlocal info --whats-new` (shows last 3 versions).
2. Run `bdlocal ready --json` to find available work.
3. Run `bdlocal blocked --json` to see what is waiting on other tasks.
4. If claiming existing bead: ask permission, then `bdlocal update <id> --status in_progress --json`.
5. If creating new bead: ask permission, then `bdlocal create "title" -t <type> -p <priority> --description="context" --estimate 30 --json`.

During work:
7. Review bead: `bdlocal show <id> --json`.
8. On material progress: ask permission, then update notes per Note Curation below.
9. On discovering new scope: ask permission to create with `--deps discovered-from:<parent-id>`.

End:
10. Ask permission to close: `bdlocal close <id> --reason "Completed" --json`.
11. Local backup: `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`

Commands:

Core:
- `bdlocal ready --json` — find unblocked work
- `bdlocal blocked --json` — find blocked work
- `bdlocal show <id> --json` — view details
- `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 --description="..." --estimate 60 --json`
- `bdlocal create "title" --external-ref "https://github.com/..." --json` — link external issue
- `bdlocal update <id> --status open|in_progress|blocked|closed --json`
- `bdlocal update <id> --notes|--description|--design|--acceptance|--title "text" --estimate 120 --json`
- `bdlocal update <id> --status in_progress --add-label <label>[,<label>...] --remove-label <label>[,<label>...] --json` — update with labels (repeatable; accepts comma-separated lists)
- `bdlocal close <id> --reason "..." --json`
- `bdlocal reopen <id> --reason "..." --json`
- `bdlocal list --status open --sort priority --json`
- `bdlocal search "query" --json`
- `bdlocal stale --days 30 --json`
- `bdlocal count --json` — count and group issues
- `bdlocal status --no-activity --json` — database overview (skip git activity parsing)
- `bdlocal init --quiet --skip-hooks --skip-merge-driver` — initialize in new repo (ensure git-free)
- `bdlocal deleted --json` — view deletion audit trail

Batch operations:
- `bdlocal update <id1> <id2> --status in_progress --json`
- `bdlocal close <id1> <id2> --reason "Done" --json`

Dependencies:
- `bdlocal dep add <id> <dep-id> --type blocks|discovered-from|related|parent-child --json`
- `bdlocal dep tree <id>`

Labels (metadata without polluting notes):
- `bdlocal label add|remove <id> <label> --json`
- `bdlocal label list <id> --json`
- `bdlocal list --label auth,backend --json` (AND)
- `bdlocal list --label-any urgent,blocked --json` (OR)
- Useful: `needs-human-review`, `context-stale`, `blocked-on-external`, `ai-generated`

Note curation:
1. Read: `bdlocal show <id> --json`
2. Curate: drop stale items, keep only what future agent needs. Use COMPLETED/IN_PROGRESS/NEXT structure.
3. Update: `bdlocal update <id> --notes "full refreshed snapshot" --json` (replaces entire field)
4. Verify: re-run `bdlocal show <id> --json`

Planning & content strategy:
- Bead content: plain text only. No Markdown. The notes field is the living plan.
- Scratchpad: use `/tmp/` for ephemeral thinking. Never save to project.
- Wisdom: maintain a single, accumulated source of truth. Append new knowledge to existing wisdom; do not overwrite valid historical knowledge.
- History: only current state matters. Do not preserve old plans.

Dependency thinking:
- Cognitive trap: temporal language inverts dependencies.
- Wrong: "Phase 1 blocks Phase 2" (Phase 1 -> Phase 2)
- Right: "Phase 2 DEPENDS ON Phase 1" (`bdlocal dep add phase2 phase1`)
- Always ask: "What does this task NEED before it can start?"

Reference:

Types: `bug`, `feature`, `task`, `epic`, `chore` — always pass `-t`

Priorities: `0`=critical, `1`=high, `2`=medium (default), `3`=low, `4`=backlog

Statuses: `open`, `in_progress`, `blocked`, `closed` (`ready` is a filtered view, not a status)

Dependencies: `blocks` (hard), `related` (soft), `parent-child` (hierarchy), `discovered-from` (provenance)

Advanced patterns:

Wisdom beads (accumulated knowledge):
1. Create: `bdlocal create "wisdom - <topic>" -t task -p 2 --json`
2. Link: `bdlocal dep add <working-id> <wisdom-id> --type related --json`
3. Maintain: update wisdom bead notes with curated takeaways each session.
4. Load and follow e2e when accessing wisdom/knowledge beads:
   - Load entire content into memory once: `bdlocal show <wisdom-id> --json 2>&1 | jq -r '.[0].notes'`
   - Read the entire wisdom bead content fully without skimming or skipping sections.
   - Follow instructions to the letter; do not cherry-pick or skip parts.
   - After updating a wisdom bead, ask user permission to re-upload new contents into context.
   - Do not repeatedly grep/query wisdom beads if it's already loaded in memory; recall from memory.
   - Treat wisdom bead instructions as binding within the scope of the current task.

Epic with external link:
`bdlocal create "Auth epic" -t epic -p 1 --external-ref "https://github.com/.../issues/123" --json`

Maintenance:
- Backup: `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`
- Compact: `bdlocal admin compact --days 90`
- Cleanup: `bdlocal admin cleanup --force` (deletes closed issues; prunes expired tombstones)
- Clean: `bdlocal clean` (remove temp merge artifacts)
- Health: `bdlocal doctor --check-health`
- Duplicates: `bdlocal duplicates --auto-merge --json`
- Import config: `bdlocal config set import.orphan_handling "resurrect"` (prevent data loss)

Deletion tracking:
- `bdlocal deleted --json` (last 7 days) or `bdlocal deleted --since=30d --json`
- `bdlocal delete <id>`

Duplicates:
- `bdlocal duplicates` / `bdlocal duplicates --auto-merge`
- `bdlocal merge <source-id> --into <target-id> --json`

Troubleshooting: confirm `BEADS_DIR` is set and `bdlocal version >= 0.29.0`.
