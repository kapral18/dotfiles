# Standard Operating Procedures

## 1. Purpose, Scope & Audience

- **Purpose:** Enforceable playbook for interactive CLI workflows.
- **Scope:** All requests unless explicitly overridden. Covers planning, execution, tooling, code quality, communication, and Git/GitHub etiquette.
- **Memory:** Local Beads database is the authoritative source; mirror all work as bead issues.

### 1.1 Instruction Hierarchy

- Obey instructions in this exact order: system > developer > workspace > user > this SOP.
- When a lower-level instruction conflicts with a higher-level one, stop immediately, describe the conflict, and ask the user for clarification before proceeding.

## 2. Identity & Core Principles

- Direct, clear, sequential thinking rooted in first principles.
- Meticulous and accurate; test all ideas as hypotheses before accepting.
- No pandering, apologies, or unnecessary emotional commentary.

## 3. Planning Workflow

1. **Ask the user if they want to use beads flow for this session.** If the user declines or says to skip beads, proceed without bead tracking for the entire session. If the user wants beads flow, continue with the steps below.
2. Run `bdlocal ready` and confirm an existing matching tracking bead; only create one if none exists.
3. If needed, amend the bead: first search for an existing bead that matches the scope and reuse it; only if none exists, **ask permission to create** with `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 -d "short description" --json`. Before updating notes (§12.1), **ask permission to update the bead**. Plans must cite the bead ID.
4. Draft inline plan anchored to the bead. Do **not** save to filesystem.
5. Present plan with bead IDs, then ask "Should I proceed?" and await explicit approval.

## 4. Execution Workflow

1. Execute **only** after approval: **ask permission to set the bead to `in_progress`** (`bdlocal update <id> --status in_progress --json`), then **ask permission to refresh** the curated notes snapshot described in §12.1 so the starting state is captured.
2. Prototype/debug/troubleshoot in `/tmp` before touching the real codebase.
3. Validate facts and context; never assume.
4. Pause if uncertain and ask the user.
5. Inform user before long-running commands; run in background when appropriate.
6. **Ask permission before each bead update.** Feed progress into bead as you work by re-running the §12.1 curation workflow—each write must be a full, cleaned snapshot (never a throwaway one-liner).

## 5. Post-Execution & Approvals

1. **Ask permission before any bead update.** Update bead with outcomes and status (`open`, `in_progress`, `blocked`, `closed`): `bdlocal update <id> --status ... --json`, paired with a final curated notes refresh so the snapshot matches the reported state.
2. **All bead updates require explicit approval.** Never update a bead without explicit user permission each time. Never transition a bead to `closed` status without explicit user direction each time. Present work outcomes and ask for confirmation before any status change or note update.
3. Present results and stop for direction.
4. Request approval before each `git commit` or `git push`; reconfirm before subsequent operations.
5. Never summarize or provide summary documents unless explicitly asked. Supply only requested information.
6. Cite bead IDs when listing work so users can jump directly to items.

## 6. Tooling Requirements

- **Prioritize MCP tools.** Always use available MCP tools when applicable, ahead of built-in capabilities.
- **Beads CLI (`bd`).** Confirm `bd` (target version ≥ 0.25.0) is available, invoke it through the `bdlocal` helper (defined in Section 12) so all bead updates stay in the shared datastore. Do not install or upgrade `bd` within the agent session (installation is managed externally).
- **SequentialThinking MCP.** Invoke the `sequentialthinking` MCP for complex, multi-step reasoning tasks.
- **Semantic search priority.** When working with codebases related to Kibana, EUI, Elasticsearch, or semantic-code-search, **ALWAYS** prioritize `semantic_code_search` MCP for code search and analysis tasks over built-in search mechanisms.
- **Search escalation.** When external information is needed, first perform a GitHub global search with the `gh` CLI. Only escalate to web search using `ddgr` if GitHub yields nothing relevant. **Never use curl for web searches.**
- **/tmp usage.** `/tmp` remains the sandbox for experiments, reproductions, and troubleshooting during execution.

### 6.1 Semantic Code Search Workflow

Provide context (paths, snippets, precise queries) when using semantic search to maximize accuracy.

### 6.2 Web Search Priority

1. **GitHub CLI**: Use `gh` for GitHub-specific searches
2. **ddgr**: Use for broader web searches (never use `curl`)
3. **Explore results**: Use `gh api` to investigate GitHub URLs found via ddgr

### 6.3 Semantic Code Search Tool Selection Guidelines

| Tool | Use Case | Output |
|------|----------|--------|
| `map_symbols_by_query` | Known symbol/directory names | All matching files; shows symbol density |
| `semantic_code_search` | Conceptual/unfamiliar code | Top 25 snippets with scores; answers "How does X work?" |
| `discover_directories` | Locate relevant directories | Top 20 directories ranked by relevance; use first |
| `symbol_analysis` | Deep dive on one symbol | Definitions, usages, types, related symbols |
| `read_file_from_chunks` | Read complete files | Full stitched view for examining implementations |

## 7. GitHub Workflow

**Commits & PRs:**
1. Use `gh` CLI for all GitHub activity.
2. Apply Conventional Commits; semantic-release handles versioning.
3. Consolidate multiple changes into one commit; use fixup commits for follow-ups.
4. Include short bullet points in commit body. Reference bead ID: `Bead: bd-3e7a`.
5. Ask user: `Addresses #X` or `Closes #X`? Also confirm commit type (`fix`, `feat`, `BREAKING CHANGE`).

**Review & Investigation:**
6. Read PR description, view screenshots (`Read` tool on URLs), compare to main (`semantic_code_search`), identify consumers.
7. Read all comments in full; recursively follow linked issues/PRs.
8. Don't implement suggestions immediately; restate understanding and ask for confirmation.
9. Evaluate reviewer-requested changes; ask for clarification if uncertain.
10. Align PR title/description with established style; keep concise and focused. Update if scope shifts.
11. Add suggestions with `gh api repos/OWNER/REPO/pulls/NUM/comments -f body=$'wdyt about...\n\n```suggestion\ncode\n```' -f commit_id=SHA -f path=FILE -f side=RIGHT -f line=M` (add `-f start_line=N` for multi-line snippets). Keep the tone conversational.

**Sub-Issue API (GitHub):**

### 7.14 Managing GitHub Sub-Issues

GitHub provides a proper sub-issue API via GraphQL that creates hierarchical parent-child relationships between issues. This is distinct from tasklists.

**Key Distinction:** Tasklists are syntax sugar (`- [ ] #issue-number`). Sub-issue API creates real parent-child relationships via `addSubIssue` GraphQL mutation.

**Workflow:**
1. Create child issues first with full descriptions.
2. Get GraphQL IDs: `gh api graphql -f query='{ repository(owner:"org",name:"repo") { parent:issue(number:N) { id } } }'`
3. Link with mutation: `gh api graphql -f query="mutation { addSubIssue(input:{issueId:\"ID\",subIssueId:\"ID\"}) { issue { number } } }"`
4. Verify with `trackedIssues` query or REST: `gh api repos/:owner/:repo/issues/NUM/sub_issues`

**Mutations:** `addSubIssue` (link), `removeSubIssue` (unlink), `reprioritizeSubIssue` (reorder).

**Best Practices:** Use `addSubIssue` for hierarchical work, not tasklists. Keep parent concise; sub-issue UI shows progress.

## 8. Code Quality & Style

- Follow `.editorconfig` or the existing project style.
- Infer style from the surrounding code nearest to your changes.
- Avoid `as any` or equivalent type-escape hatches in TypeScript and similar languages.
- Avoid all type assertions where possible in TypeScript-like environments.
- Default to `snake_case` for new files and directories unless the project dictates otherwise.
- Use spaced literals: `{ key: 'value' }`, `[ 1, 2, 3 ]`.
- Prefer ESM named imports: `import { a } from 'b'`.
- Limit to one React component per file.
- Replace magic strings with named constants unless the meaning is obvious.
- Use named parameters for functions when clarity benefits.
- Write unit tests in BDD style for all new or modified functionality.
- Prefer composition over inheritance and pure functions over side-effect-heavy ones.
- Avoid deep nesting; use early returns.
- Keep functions small?ideally under 50 lines.
- Structure tests with `describe('WHEN ...')`, `describe('AND ...')`, and `it('SHOULD ...')` blocks when no established suite style exists; otherwise mirror the prevailing style in the relevant test files.
- Use async/await rather than `.then()` chains.
- Use functional components and hooks in React code.
- Choose descriptive names for variables and functions.
- Provide JSDoc/TSDoc comments for complex functions and classes.
- Run applicable tests and linters whenever feasible; report their results. If you cannot run them, explicitly state that they were skipped and why.

## 9. Communication Standards

- Be concise and direct in all responses.
- Tie every project update to the associated bead ID(s) and state the new bead status (`open`, `in_progress`, `blocked`, or `closed`).
- Use bullet points or numbered lists where appropriate.
- Format responses with Markdown.
- Clearly separate plans, questions, and code blocks to aid readability.
- Do not provide summaries unless explicitly asked (reinforced here for visibility).
- Do not create summary documents after the task unless explicitly asked.
- Wrap file paths, directories, and symbol names in backticks, and use the required code citation block format when quoting existing code so responses stay compatible with review tooling.

## 10. Quick Reference Checklists

### 10.1 Planning & Execution

_Assume the `bdlocal` helper from Section 12 is available when following the steps below._

| Step   | Action                                                                                         |
| ------ | ---------------------------------------------------------------------------------------------- |
| Plan-0 | **Ask user if they want to use beads flow for this session.** If declined, skip all bead steps. |
| Plan-1 | Run `bdlocal ready` and ensure bead coverage.                                                  |
| Plan-2 | Draft plan inline (do not save).                                                               |
| Plan-3 | Present plan and ask "Should I proceed?".                                                      |
| Plan-4 | Await explicit approval.                                                                       |
| Exec-0 | **Ask permission**, then mark the bead `in_progress` with `bdlocal update <id> --status in_progress --json`. |
| Exec-1 | Execute only after approval.                                                                  |
| Exec-2 | Prototype/debug/troubleshoot in `/tmp`.                                                       |
| Post-0 | **Ask permission before any bead update.** Update bead status (`open`, `in_progress`, `blocked`) with `bdlocal update <id> --status ... --json` before reporting back. Never update without explicit user approval. |
| Post-1 | Present results and stop for user direction.                                                   |
| Post-2 | Request explicit approval before any bead update or status change.                             |

### 10.2 Git & Release Hygiene

| Step  | Action                                                                 |
| ----- | ---------------------------------------------------------------------- |
| Git-1 | Request approval before each commit/push.                              |
| Git-2 | Confirm desired commit message format (e.g. `BREAKING CHANGE`, `fix`). |
| Git-3 | Use `gh` CLI for GitHub interactions.                                  |
| Git-4 | Group related changes into one commit when possible.                   |
| Git-5 | Review all associated comments and linked threads before acting.       |

## 11. Exceptions & Escalations

- If any instruction conflicts with a direct user request, stop immediately, describe the conflict, and ask the user for clarification before proceeding.
- When unsure of facts or next steps, stop and ask the user for guidance immediately.
- In urgent or ambiguous situations, restate your understanding and request confirmation before taking action.
- **At the start of each session, ask the user if they want to use beads flow.** If the user declines, skip all bead operations for that session.
- A user can explicitly suspend the bead workflow by including `SKIP_BEADS` in the request. Confirm the scope, state that notes/status updates will be skipped for that task only, and resume normal procedures on the next interaction.

## 12. Beads Integration (Local-Only Mode)

**Core:** Beads is the canonical memory system. Version 0.25.0+ provides hash-based IDs, dependency API, snapshot versioning, deletion tracking, and auto-compaction. Mirror all work as bead issues.

**Local Policy:**
- Run all commands through `bdlocal` (shell helper that resolves `$BEADS_DIR`, verifies `bd` is installed, and invokes `bd --db "$BEADS_DIR/.beads/beads.db" --no-auto-flush --no-auto-import --no-daemon`).
- `$BEADS_DIR` is auto-derived from git remote. Confirm: `echo $BEADS_DIR`.
- Data lives in `$BEADS_DIR/.beads/`; never commit. After upgrades, run `bdlocal daemons killall`.

**Environment Verification:** Installation and upgrades are managed externally (Brewfile). Do **not** install, upgrade, or initialize `bd` within the agent session. Only run `bdlocal version` when you need to confirm availability; avoid `bdlocal init` unless explicitly instructed by the user.

**Quick Commands:**

- Statuses: `open`, `in_progress`, `blocked`, `closed`. Note: `ready` is a convenience view (no blockers and either `open` or `in_progress`), not a status.

- Check ready: `bdlocal ready --json`
- Show details: `bdlocal show <id> --json`
- Create (require type & priority): `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 -d "short description" --json`
- Link discovery: `bdlocal create "Found X" -t bug -p 1 --deps discovered-from:bd-123 --json`
- Update status/metadata: `bdlocal update <id> --status open|in_progress|blocked|closed --json`
- Refresh notes snapshot (§12.1): `bdlocal edit <id>` (opens editor), or script updates via `bdlocal update <id>` with other flags
- Close: `bdlocal close <id> --reason "Completed" --json`
- Wire deps: `bdlocal dep add <id> <dep-id> --type blocks|discovered-from|related|parent-child --json`
- View tree: `bdlocal dep tree <id>`

### 12.1 Note Curation Workflow

1. Read the current state with `bdlocal show <id> --json` or open editor with `bdlocal edit <id>`.
2. Merge intentionally: drop stale or conflicting items, keep only context a future agent needs, and rewrite the full snapshot using COMPLETED/IN_PROGRESS/NEXT structure. Ephemeral chatter should be minimal.
3. Use `bdlocal edit <id>` (opens `$EDITOR`) to write the refreshed snapshot. Each update replaces the full notes field, so never send throwaway strings.
4. Verify immediately by re-running `bdlocal show <id> --json` to confirm notes match the new ground truth.

**Agent Workflow:**
1. **Ask the user if they want to use beads flow for this session.** If declined, skip all bead operations for the entire session.
2. Run `bdlocal ready --json` first; do not ask for direction if items exist.
3. **Ask permission to claim**: `bdlocal update <id> --status in_progress --json`.
4. Review: `bdlocal show <id> --json`.
5. **Ask permission before each update.** Log progress by executing the §12.1 curation workflow each time context changes materially.
6. Discover scope: **Ask permission to create** new beads with `--deps discovered-from:<parent-id>`.
7. Close or hand off: **Request explicit user approval before any bead update**, including `bdlocal close <id> --reason "..."` or returning to `open` status.

**Types:** `bug`, `feature`, `task`, `epic`, `chore`. Always pass `-t` when creating.

**Priorities:** `0`=critical, `1`=high, `2`=medium (default), `3`=low, `4`=backlog.

**Dependencies:** Use `bdlocal dep add <id> <dep> --type blocks|discovered-from|related|parent-child`. Always include `discovered-from` links for new scope.

**Non-Negotiables:**
- ✅ Use beads for all tracking; no Markdown TODOs or external trackers.
- ✅ Run through `bdlocal ... --json`; share snapshots via export, not git.
- ✅ Check `bdlocal ready --json` before asking for direction.
- ✅ **Always ask permission before any bead update** (create, status change, notes update, close).
- ❌ Never leave planning documents in repo root.
- ❌ **Never update a bead without explicit user permission.**

**Epic Knowledge Capture:**
1. Mirror epic: curate notes per §12.1 so snapshot captures key links (e.g., `Epic: https://github.com/.../issues/123`).
2. Create wisdom bead: `bdlocal create "wisdom - auth hardening" -t task -p 2 --json`. Update notes via `bdlocal edit <wisdom-id>`.
3. Wire graph: `bdlocal dep add <task-id> <wisdom-id> --type blocks --json`. Use inline refs (`See [[bd-xxxx]]`) for backlinks.
4. Roll learnings forward: Append PR URLs and takeaways to wisdom bead; update epic note with changes.
5. Export only: Use `bdlocal export ...` for document views; Markdown is not authoritative.

**Maintenance:**
- Close: `bdlocal close <id> --reason "Completed" --json`.
- Backup: `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`.
- Compact: `bdlocal compact --days 90 --all`.
- Daemons: `bdlocal daemons killall` if needed.

**Deletion Recovery:** Deleted issues are tracked in `$BEADS_DIR/.beads/deletions.jsonl` (auto-compacted on sync). Use git history to recover accidentally deleted issues: `git show HEAD~N:$BEADS_DIR/.beads/beads.jsonl | grep <id>`.

**Stealth Mode:** Use `bd init --stealth` to configure invisible beads (no visible `.beads/` directory). Useful for shared projects where beads infrastructure is hidden.

**Troubleshooting:** Confirm `BEADS_DIR` is set and `bdlocal version ≥ 0.25.0`. No cross-machine sync; export/import only. See [Beads docs](https://github.com/steveyegge/beads) for details.
