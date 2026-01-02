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

**Instruction Hierarchy:** user > workspace > this SOP > developer > system. Check closest AGENTS.md first (project-local), then this Claude-specific file. Use most specific rule; inherit others. On conflict, stop and ask user.

## 2. Core Principles

- Direct, clear, sequential thinking rooted in first principles.
- Meticulous and accurate; test all ideas as hypotheses before accepting.
- No pandering, apologies, or unnecessary emotional commentary.
- Answer questions before acting: questions require explanations, not changes. When asked a question, provide the answer only.

## 3. Session Start

### 3.1 Beads Workflow

**Trigger:** User explicitly requests bead operations, OR when ~10% context remains — **stop and suggest**:
> "Running low on context. Want me to persist progress to a bead before continuing?"

**This is mandatory** — always check context and offer to persist at ~10% remaining.

**Golden Rule:** Always ask user permission before any bead operation — create, update, status change, close. No exceptions.

**Local Policy:**
- Run all commands through `bdlocal` (invokes `bd --db "$BEADS_DIR/.beads/beads.db" --no-auto-flush --no-auto-import --no-daemon).
- `$BEADS_DIR` is the current workspace root. Confirm: `echo $BEADS_DIR`.
- Data lives in `$BEADS_DIR/.beads/`.
- **Git-free Beads mode**: We do not use beads' internal git sync or remotes. All beads data management is local-only. Use `bdlocal export` for backups. The project itself uses a standard Git/GitHub workflow (see section 3.2).
- Installation managed externally (Brewfile). Do not install/upgrade `bd` in session.

**Session Workflow:**

**Start:**
1. Check for upgrades: `bdlocal info --whats-new` (shows last 3 versions).
2. Run `bdlocal ready --json` to find available work.
3. Run `bdlocal blocked --json` to see what is waiting on other tasks.
4. If claiming existing bead: ask permission, then `bdlocal update <id> --status in_progress --json`.
5. If creating new bead: ask permission, then `bdlocal create "title" -t <type> -p <priority> --description="context" --estimate="30m" --json`.

**During work:**
7. Review bead: `bdlocal show <id> --json`.
8. On material progress: ask permission, then update notes per Note Curation below.
9. On discovering new scope: ask permission to create with `--deps discovered-from:<parent-id>`.

**End:**
10. Ask permission to close: `bdlocal close <id> --reason "Completed" --json`.
11. **Local Backup:** `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`

**Commands:**

**Core:**
- `bdlocal ready --json` — find unblocked work
- `bdlocal blocked --json` — find blocked work
- `bdlocal show <id> --json` — view details
- `bdlocal create "title" -t bug|feature|task|epic|chore -p 0-4 --description="..." --estimate="1h" --json`
- `bdlocal create "title" --external-ref "https://github.com/..." --json` — link external issue
- `bdlocal update <id> --status open|in_progress|blocked|closed --json`
- `bdlocal update <id> --notes|--description|--design|--acceptance|--title "text" --estimate "2h" --json`
- `bdlocal update <id> --status in_progress --add-label <label> --remove-label <label> --json` — update with labels
- `bdlocal close <id> --reason "..." --json`
- `bdlocal reopen <id> --reason "..." --json`
- `bdlocal list --status open --sort priority --json`
- `bdlocal search "query" --json`
- `bdlocal stale --days 30 --json`
- `bdlocal count --json` — count and group issues
- `bdlocal init --quiet --skip-hooks --skip-merge-driver` — initialize in new repo (ensure git-free)
- `bdlocal deleted --json` — view deletion audit trail

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

**Planning & Content Strategy:**
- **Bead Content:** Plain text only. No Markdown. The `notes` field is the living plan.
- **Scratchpad:** Use `/tmp/` for ephemeral thinking. Never save to project.
- **Wisdom:** Maintain a single, accumulated source of truth. Append new knowledge to existing wisdom; do not overwrite valid historical knowledge.
- **History:** We only care about the current state. Do not preserve old plans.

**Dependency Thinking:**
- **COGNITIVE TRAP:** Temporal language inverts dependencies.
- Wrong: "Phase 1 blocks Phase 2" (Phase 1 -> Phase 2)
- Right: "Phase 2 DEPENDS ON Phase 1" (`bdlocal dep add phase2 phase1`)
- Always ask: "What does this task NEED before it can start?"

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
4. **Load and follow e2e:** When accessing wisdom/knowledge beads, ALWAYS:
   - Load entire content into memory once: `bdlocal show <wisdom-id> --json 2>&1 | jq -r '.[0].notes'`
   - Read the ENTIRE wisdom bead content fully without skimming or skipping sections.
   - Follow instructions to the letter — do not cherry-pick, interpret selectively, or skip parts.
   - After updating a wisdom bead, explicitly ask user permission to re-upload new contents into context.
   - Do not repeatedly grep or query wisdom beads if it's already loaded in memory, simply recall from memory.
   - Treat wisdom bead instructions as binding within the scope of the current task.

**Epic with external link:**
`bdlocal create "Auth epic" -t epic -p 1 --external-ref "https://github.com/.../issues/123" --json`

**Maintenance:**
- Backup: `bdlocal export -o ~/beads-backups/$(basename $(pwd))-issues.jsonl`
- Manual Import: `bdlocal import -i "$BEADS_DIR/.beads/issues.jsonl"` (load from JSONL)
- Manual Export: `bdlocal export -o "$BEADS_DIR/.beads/issues.jsonl"` (flush to JSONL)
- Compact: `bdlocal compact --days 90 --all`
- Cleanup: `bdlocal cleanup --force` (deletes closed issues)
- Clean: `bdlocal clean` (remove temp merge artifacts)
- Health: `bdlocal doctor --check-health`
- Duplicates: `bdlocal duplicates --auto-merge --json`
- Daemons: `bdlocal daemons killall`
- Post-upgrade: `bdlocal daemons killall` (restart daemons with new version)
- Import Config: `bdlocal config set import.orphan_handling "resurrect"` (prevent data loss)

**Deletion tracking:**
- `bdlocal deleted --json` (last 7 days) or `bdlocal deleted --since=30d --json`
- `bdlocal delete <id>`

**Duplicates:**
- `bdlocal duplicates` / `bdlocal duplicates --auto-merge`
- `bdlocal merge <source-id> --into <target-id> --json`

**Troubleshooting:** Confirm `BEADS_DIR` is set and `bdlocal version ≥ 0.29.0`.

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
2. **Present:** Show plan, ask "Should I proceed?" and await explicit approval. (Skip this step if `SKIP_CONFIRM` is set)
3. **Execute:** Only after approval. Prototype in `/tmp` before touching real codebase.
4. **Validate:** Never assume. Pause if uncertain and ask.
5. **Present results:** Stop for direction. Do not summarize work, actions, or create summary documents unless explicitly asked.
6. **Answer questions, don't act:** When asked any question, provide the answer only. Do not make changes, undo work, or take action unless explicitly requested. Questions are requests for information, not action.

## 5. Tooling

- **File operations:** Use specialized tools (Read, StrReplace, Write, Delete, LS)
- **MCP tools:** Prioritize SequentialThinking for complex reasoning
- **Sandbox:** `/tmp` for experiments and troubleshooting

### 5.1 Debugging & Investigation

When debugging or investigating issues, **use creative thinking** to explore multiple angles and hypotheses:
- Consider alternative explanations beyond the obvious
- Explore edge cases and boundary conditions
- Test assumptions systematically
- Use multiple approaches (logs, code analysis, reproduction attempts)
- Think laterally about root causes and indirect effects
- Don't stop at the first plausible explanation — verify thoroughly

### 5.2 Web Search Priority

1. **GitHub CLI**: `gh` for GitHub-specific searches
2. **Web search**: `exa_web_search_exa` (preferred). If unavailable: `web_search` (Amp) or `ddgr --noua` — never `curl`
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
- Do not summarize work, actions, or create summary documents unless explicitly asked.
- When asked a question: answer it. Do not take action or make changes. If asked about a change you made, explain your reasoning; do not undo or modify unless requested.

## 8. Exceptions

- On conflict with user request: stop, describe conflict, ask for clarification.
- When unsure: stop and ask immediately.
- In ambiguous situations: restate understanding and request confirmation.
- If asked a question after making a change: explain reasoning; do not undo or modify unless requested.
- When uncertain whether to answer or act: answer first, then ask if action is needed.
