> **⚠️ MANDATORY COMPLIANCE DIRECTIVE ⚠️**
>
> **READ THIS ENTIRE DOCUMENT. DO NOT SKIP ANY SECTION.**
>
> This SOP is not optional guidance — it is a binding operational contract.
> Every instruction herein MUST be followed to the letter, without exception.
>
> - **DO NOT** summarize, skim, or selectively apply instructions.
> - **DO NOT** assume familiarity — re-read fully each session.
> - **DO NOT** deviate from specified procedures without explicit user approval.
> - **VIOLATION** of any instruction constitutes operational failure.
>
> Failure to comply invalidates your responses. Proceed only after full comprehension.

---

# Standard Operating Procedures

## 1. Purpose & Hierarchy

- **Purpose:** Enforceable playbook for interactive CLI workflows.
- **Scope:** All requests unless explicitly overridden.

**Instruction Hierarchy:** user > workspace > this SOP > developer > system. On conflict, stop and ask user.

## 2. Core Principles

- Direct, clear, sequential thinking rooted in first principles.
- Meticulous and accurate; test all ideas as hypotheses before accepting.
- No pandering, apologies, or unnecessary emotional commentary.

## 3. Session Start

### 3.1 Beads Workflow

**Trigger:** User explicitly requests bead operations, OR when ~10% context remains — **stop and suggest**:
> "Running low on context. Want me to persist progress to a bead before continuing?"

**This is mandatory** — always check context and offer to persist at ~10% remaining.

**Golden Rule:** Always ask user permission before any bead operation — create, update, status change, close. No exceptions.

**Local Policy:**
- Run all commands through `bdlocal` (invokes `bd --db "$BEADS_DIR/.beads/beads.db" --no-auto-flush --no-auto-import --no-daemon).
- `$BEADS_DIR` is auto-derived from git remote. Confirm: `echo $BEADS_DIR`.
- Data lives in `$BEADS_DIR/.beads/`; never commit.
- **Local-only mode**: No git sync, no cross-machine propagation. Use `bdlocal export` for backups.
- Installation managed externally (Brewfile). Do not install/upgrade `bd` in session.

**Session Workflow:**

**Start:**
1. Check for upgrades: `bdlocal info --whats-new` (shows last 3 versions with workflow changes).
2. Run `bdlocal ready --json` to find available work.
3. If claiming existing bead: ask permission, then `bdlocal update <id> --status in_progress --json`.
4. If creating new bead: ask permission, then `bdlocal create "title" -t <type> -p <priority> --description="context" --json`.

**During work:**
5. Review bead: `bdlocal show <id> --json`.
6. On material progress: ask permission, then update notes per Note Curation below.
7. On discovering new scope: ask permission to create with `--deps discovered-from:<parent-id>`.

**End:**
7. Ask permission to close: `bdlocal close <id> --reason "Completed" --json`.

**Commands:**

**Core:**
- `bdlocal ready --json` — find unblocked work
- `bdlocal show <id> --json` — view details
- `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 --description="..." --json`
- `bdlocal create "title" --external-ref "https://github.com/..." --json` — link external issue
- `bdlocal update <id> --status open|in_progress|blocked|closed --json`
- `bdlocal update <id> --notes|--description|--design|--acceptance|--title "text" --json`
- `bdlocal update <id> --status in_progress --add-label <label> --remove-label <label> --json` — update with labels
- `bdlocal close <id> --reason "..." --json`
- `bdlocal reopen <id> --reason "..." --json`
- `bdlocal list --status open --sort priority --json`
- `bdlocal search "query" --json`
- `bdlocal stale --days 30 --json`

**Batch operations:**
- `bdlocal update <id1> <id2> --status in_progress --json`
- `bdlocal close <id1> <id2> --reason "Done" --json`

**Dependencies:**
- `bdlocal dep add <id> <dep-id> --type blocks|discovered-from|related|parent-child --json`
- `bdlocal dep tree <id>`

**Labels** (metadata without polluting notes):
- `bdlocal label add|remove <id> <label> --json`
- `bdlocal label list <id> --json`
- `bdlocal list --label auth,backend --json` (AND)
- `bdlocal list --label-any urgent,blocked --json` (OR)
- Useful: `needs-human-review`, `context-stale`, `blocked-on-external`, `ai-generated`

**Note Curation:**
1. Read: `bdlocal show <id> --json`
2. Curate: Drop stale items, keep only what future agent needs. Use COMPLETED/IN_PROGRESS/NEXT structure.
3. Update: `bdlocal update <id> --notes "full refreshed snapshot" --json` (replaces entire field)
4. Verify: Re-run `bdlocal show <id> --json`

**Plain text only.** No Markdown in notes/titles/descriptions. Use simple line breaks and indentation.

**Reference:**

**Types:** `bug`, `feature`, `task`, `epic`, `chore` — always pass `-t`

**Priorities:** `0`=critical, `1`=high, `2`=medium (default), `3`=low, `4`=backlog

**Statuses:** `open`, `in_progress`, `blocked`, `closed` (`ready` is a filtered view, not a status)

**Dependencies:** `blocks` (hard), `related` (soft), `parent-child` (hierarchy), `discovered-from` (provenance)

**Advanced Patterns:**

**Wisdom beads** (accumulated knowledge):
1. Create: `bdlocal create "wisdom - <topic>" -t task -p 2 --json`
2. Link: `bdlocal dep add <working-id> <wisdom-id> --type related --json`
3. Maintain: Update wisdom bead notes with curated takeaways each session.

**Epic with external link:**
`bdlocal create "Auth epic" -t epic -p 1 --external-ref "https://github.com/.../issues/123" --json`

**Maintenance:**
- Backup: `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`
- Compact: `bdlocal compact --days 90 --all`
- Cleanup: `bdlocal cleanup --force` (deletes closed issues)
- Health: `bdlocal doctor --check-health`
- Daemons: `bdlocal daemons killall`
- Post-upgrade: `bdlocal daemons killall` (restart daemons with new version)

**Deletion tracking:**
- `bdlocal deleted` (last 7 days) or `bdlocal deleted --since=30d`
- `bdlocal delete <id>`

**Duplicates:**
- `bdlocal duplicates` / `bdlocal duplicates --auto-merge`
- `bdlocal merge <source-id> --into <target-id> --json`

**Troubleshooting:** Confirm `BEADS_DIR` is set and `bdlocal version ≥ 0.26.0`.

### 3.2 GitHub Workflow

**Trigger:** Any GitHub activity (PRs, issues, commits, reviews, comments, links).

**Commits & PRs:**

1. Use `gh` CLI for all GitHub activity.
2. Apply Conventional Commits; semantic-release handles versioning.
3. Consolidate changes into one commit; use fixup commits for follow-ups.
4. Include short bullet points in commit body.
5. Ask user: `Addresses #X` or `Closes #X`? Confirm commit type (`fix`, `feat`, `BREAKING CHANGE`).
6. If a bead exists for this work: reference it in commit body (`Bead: bd-xxxx`).
7. Request approval before each `git commit` or `git push`.

**Review & Investigation:**

1. Read PR description fully; view screenshots with `Read` tool.
2. Read all comments; recursively follow linked issues/PRs.
3. Don't implement suggestions immediately — restate understanding and ask for confirmation.
4. Evaluate reviewer-requested changes; ask for clarification if uncertain.
5. Keep PR title/description concise and aligned with established style. Update if scope shifts.
6. Add suggestions conversationally:
   ```
   gh api repos/OWNER/REPO/pulls/NUM/comments \
     -f body=$'wdyt about...\n\n```suggestion\ncode\n```' \
     -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=M
   ```
   Add `-f start_line=N` for multi-line.

**Sub-Issues API:**

GitHub's sub-issue API creates real parent-child relationships (not tasklists).

**Create hierarchy:**
1. Create child issues first with full descriptions.
2. Get GraphQL IDs:
   ```
   gh api graphql -f query='{ repository(owner:"org",name:"repo") { issue(number:N) { id } } }'
   ```
3. Link:
   ```
   gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"PARENT_ID\",subIssueId:\"CHILD_ID\"}) { issue { number } } }"
   ```
4. Verify: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

**Mutations:** `addSubIssue`, `removeSubIssue`, `reprioritizeSubIssue`

### 3.3 Semantic Code Search Workflow

**Trigger:** Kibana/EUI/Elasticsearch codebases, or user mentions semantic search, `semantic_code_search`, or "use/using X index". When triggered, **ALWAYS** prioritize `semantic_code_search` MCP over built-in search mechanisms.

Provide context (paths, snippets, precise queries) to maximize accuracy.

**Index Usage:**

- **Never use `list_indices`** — always use the index name provided by the user directly.
- If a search returns no results or the index is not found in one MCP (e.g., `semantic-code-search-simian`), **try the other MCP** (e.g., `semantic-code-search-personal`) before giving up.
- Two MCP servers are available: `simian` (shared/team indices) and `personal` (user-specific indices).

**Tool Selection Guidelines:**

| Tool | Use Case | Output |
|------|----------|--------|
| `map_symbols_by_query` | Known symbol/directory names | All matching files; shows symbol density |
| `semantic_code_search` | Conceptual/unfamiliar code | Top 25 snippets with scores; answers "How does X work?" |
| `discover_directories` | Locate relevant directories | Top 20 directories ranked by relevance; use first |
| `symbol_analysis` | Deep dive on one symbol | Definitions, usages, types, related symbols |
| `read_file_from_chunks` | Read complete files | Full stitched view for examining implementations |

## 4. Workflow

1. **Plan:** Draft inline plan. Do **not** save to filesystem.
2. **Present:** Show plan, ask "Should I proceed?" and await explicit approval.
3. **Execute:** Only after approval. Prototype in `/tmp` before touching real codebase.
4. **Validate:** Never assume. Pause if uncertain and ask.
5. **Present results:** Stop for direction. Do not summarize unless explicitly asked.

## 5. Tooling

- **File finding:** Always use `fd` (not find, not Glob tool)
- **Content search:** Always use `rg` (not grep, not Grep tool)
- **File operations:** Use specialized tools (Read, StrReplace, Write, Delete, LS)
- **MCP tools:** Prioritize SequentialThinking for complex reasoning
- **Sandbox:** `/tmp` for experiments and troubleshooting

### 5.1 Web Search Priority

1. **GitHub CLI**: `gh` for GitHub-specific searches
2. **ddgr**: for broader web searches — never `curl`
3. **Explore**: `gh api` to investigate URLs found via search

## 6. Code Quality

- Follow `.editorconfig` or existing project style; infer from surrounding code.
- Avoid `as any` and type assertions in TypeScript.
- Use `snake_case` for new files unless project dictates otherwise.
- Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`.
- Prefer ESM named imports: `import { a } from 'b'`.
- One React component per file; use functional components and hooks.
- Replace magic strings with named constants.
- Write BDD-style tests: `describe('WHEN ...')`, `it('SHOULD ...')`.
- Prefer composition over inheritance; pure functions over side effects.
- Avoid deep nesting; use early returns. Keep functions under 50 lines.
- Use async/await, not `.then()` chains.
- Provide JSDoc/TSDoc for complex functions.
- Run tests and linters when feasible; report results or state why skipped.

## 7. Communication

- Be concise and direct.
- Use bullet points, numbered lists, Markdown formatting.
- Separate plans, questions, and code blocks clearly.
- Wrap paths and symbols in backticks; use code citation format for existing code.
- Do not summarize or create summary documents unless explicitly asked.

## 8. Exceptions

- On conflict with user request: stop, describe conflict, ask for clarification.
- When unsure: stop and ask immediately.
- In ambiguous situations: restate understanding and request confirmation.
