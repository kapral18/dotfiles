# Shared Review Rules

All review modes load this file. Mode files reference these rules instead of duplicating them.

The surface-agnostic judging engine lives in `~/.agents/skills/k-review/references/judging_core.md`.

It covers:

- Truth Validation
- State-Machine Gate
- Deletion-Safety
- Replacement/Migration Parity
- Historical-Rationale
- Product-Flow Lens
- Signal-Quality Gate
- Systemic-Risk Checks
- Coverage Checklist
- Severity
- Post-Review Lens + Stage

Load it alongside this file.

This file carries only the PR/SCSI/GitHub-delivery rules layered on top of that core.

## Read-Only Probes

- Start read-only investigation immediately; read-only `git`/`gh` checks need no confirmation.
- In large repositories, make first-pass git probes bounded: use `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff names, upstream, and log probes.
  If a plain git probe produces no output after one short wait, stop it and rerun the bounded form.
- Keep searches narrow by default: include path scopes, file globs, or exact symbols.
  When the harness provides native search/listing tools, prefer those for first-pass broad searches.
  Use shell `rg` only after narrowing by path, glob, or exact symbol; never run bare repo-root `rg <pattern>` in a large repository.
  When a file list, count, or targeted lines answer the question, return those instead of broad repo-wide searches or full command output dumps.
- When command output is saved/truncated, recover only the exact lines needed for the current decision unless the decision depends on every item.

## Hard Constraints

- External truth applies: verify behavior under review (tests, repros, `/tmp` simulations) before asserting when practical.
- Code changes:
  - **Read-only delegated workers**: their full contract is `~/.agents/skills/k-review/references/reviewer-worker.md`;
    reference it there instead of restating it here. Controller-side obligations it creates:
    - run repo-wide suites, full builds, and whole-suite test runs **once** in the controller and pass the result into every lane's scope packet; lanes are told not to repeat them
    - resolve each returned `verification_needed` serially, or record why it stayed open
    - lanes return proposed fixes only; the controller owns every edit and side effect
  - **Local changes mode with `authorship: self`** and **PR fix mode when edits are permitted**:
    - find issues and fix them in the working tree immediately
    - code changes are expected as part of the workflow
    - no extra permission needed
    - commit or push only when explicitly asked
  - **Local changes mode with `authorship: other` or `unknown`**: draft-only unless the user explicitly asks to fix/take over.
  - **PR review mode (self-review)**: same — find and fix in the working tree.
  - **PR review mode (reviewing others or unknown authorship):** stay draft-only;
    change code only when the user explicitly asks to fix/take over and the flow switches to PR fix mode.
- Post to GitHub, submit reviews, apply labels, or resolve threads only when explicitly asked.
- Exception per the Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - a **verified bot-authored** thread may be auto-replied/auto-resolved inside an explicitly-invoked flow
  - any human-visible target stays supervised: draft -> show payload -> wait
  - ambiguous/mixed threads fail safe to human
- Assume the user started the agent inside the intended repo/worktree/session:
  - stay in the current worktree; create/switch worktrees only on explicit request
  - if the user explicitly asks to create/switch a worktree:
    - use `~/.agents/skills/k-worktrees/SKILL.md`
    - for GitHub issue worktrees in agent contexts, prefer `,gh-worktree issue ... --branch ...`

## Base-Branch Context Gate (Mandatory)

Goal: compare the diff against how base (usually `main`) works today.

### Preflight (blocking, do first)

- You MUST run `list_indices` before selecting/using an index:
  - try both `scsi-main` and `scsi-local`
  - if both fail or neither exists, treat semantic search as unavailable
- If the user provided an index name:
  - verify it exists in the `list_indices` output
  - if it does not exist, stop and ask which index to use (default: the best evidence-based match for the current repo)
- If the user did not provide an index name:
  - use the single obvious repo-matching index from `list_indices`
  - if multiple equally plausible repo-matching indices remain, ask the user which one represents the base branch
  - if no repo-matching index exists, treat semantic search as unavailable and fall back to local sources
- Complete this preflight before moving on to base-context reasoning or comment drafting.

### If the repo is indexed

- Semantic code search is required for base-branch context.
  - Load and follow: `~/.agents/skills/k-semantic-code-search/SKILL.md`
  - You MUST invoke at least one SCSI tool to establish base invariants.
  - Example SCSI tools:
    - `discover_directories`
    - `semantic_code_search`
    - `map_symbols_by_query`
    - `symbol_analysis`
    - `read_file_from_chunks`
- **SCSI reflects the latest main branch, not the current branch or PR.**
  - All code returned by SCSI represents the base (pre-change) state.
  - Use SCSI strictly as comparison/background context.
  - Use it to understand the codebase the changes are targeting.
  - The PR/local diff is the ground truth for what is actually changing.
  - When SCSI results conflict with the diff, the diff wins.
  - That conflict is expected; it simply means the PR modifies that code.
- Query strategy — cast a multi-angle semantic net from the diff:
  1. Read the diff to map modified domain concepts, entities, functions, and state transitions.
  2. Generate a diverse cluster of semantic queries exploring how changed functionality affects preexisting surrounding behavior and discovering impact blast radius:
     - **Sibling & Co-located Consumers:** how do other callers/consumers in the codebase consume, sort, filter, format, or serialize the same domain concept?
     - **Downstream Call Chains & Workflows:** what upstream entry points, background tasks, or downstream consumers depend on modified contracts?
     - **Invariants & Conventions:** what validation rules, error handling, or fallback patterns are enforced elsewhere in the repository for similar constructs?
     - **Cross-Subsystem Interactions:** what other plugins, packages, or modules share or reference these data structures?
  3. Query each angle via SCSI tools against the repo index, expanding to surrounding files when initial results reveal interconnected components.
  4. Carry the gathered answers as base-branch context into the review to evaluate whether the diff breaks invariants or introduces behavioral drift against surrounding code.
- Use SCSI to learn base-branch implementation and invariants, then compare against the PR/local diff (ground truth).

### If the repo is not indexed / tools unavailable

- Cast the same multi-angle impact net using local tools to discover blast radius and surrounding impact:
  - read full enclosing files and modules beyond immediate diff hunks
  - trace callers, sibling consumers, and imports via scoped `rg` and symbol lookups
  - compare base-branch implementation via `git show <base>:<path>` against `git diff <base>...HEAD`
  - audit sibling consumers, downstream workflows, and error fallbacks for behavioral drift or broken invariants

### Historical Archaeology & Provenance (History Dimension)

History encodes invariants, past bug fixes, edge cases, and architectural context invisible to static code search:

- In massive repositories (e.g. multi-gigabyte git histories like Kibana), archaeology must be **targeted and line-bounded**, never run as whole-file blame or unconstrained recursive log traversals:
  - Probe only high-uncertainty or non-obvious modified guards, conditionals, fallback branches, or legacy helpers where origin intent is ambiguous.
  - Always bound line ranges and commit depth: `git blame -L <start>,<end> <base> -- <path>` or `git log -n 5 -L <start>,<end>:<path>`.
  - Use `git log -n 5 -p -- <path>` only when scoped to the immediate modified file.
  - Look up context from the identified commit via `gh pr view <pr>` or `gh issue view <issue>`.
- Check whether the diff inadvertently removes or weakens a guard previously added to fix a past defect or CVE.
- Classify changes that unknowingly resurrect historical bugs as HIGH regression findings.

### Base context reporting (required in every review output)

- Include exactly one line near the top of the output:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<scope>`
  - `<reason>` MUST be one of:
    - `SCSI used`
    - `not indexed`
    - `tools unavailable`
    - `user-selected none`
  - `<scope>` MUST name the actual diff under review, for example:
    - `<base>...HEAD`
    - `<ref>...HEAD`
    - `--cached`
    - `working-tree`
    - `--cached + working-tree`
    - the explicit diff command from the scope packet
- This line is reviewer metadata for the assistant's output. Keep it out of GitHub comment bodies.

## Draft Style (Public-Ready)

- Tone, concision, and response triage are centralized in `~/.agents/skills/k-communication/SKILL.md`.
- Follow it for all:
  - comment wording
  - reply wording
  - description wording
- The rules below are review-specific additions only.
- No headline summaries or category prefixes (exception: `nit:` allowed only for true nits).
- Keep explanations simple; prefer tiny examples, pseudocode, or ASCII sketches.
- Skip redundant "Ref:" links when the comment is already attached to the exact line.
- Keep anchoring/tooling limitations out of the comment body ("can't anchor inline", "not in diff hunks").
- For UI-related comments, replies, or PR-level feedback drafted after `/k-deep-review` or `live-ui-review`, keep the screenshot handoff outside the body as UI evidence attachments.
  If screenshot evidence is missing without a valid blocker or non-applicability result, block/rerun instead of drafting text-only UI feedback.
  Keep local screenshot paths out of GitHub comment, reply, review, or PR-level bodies; use UI evidence attachments instead.
- In review comment bodies, whenever you reference code, use a clickable source link to the exact location on the PR head SHA.
- Code references include:
  - file path
  - function
  - symbol
  - line/range
  - snippet location
- Link every code/file reference; plain unlinked references are incomplete.
- **Commit references must be clickable links, never bare hashes or inline code.**
- Use the full GitHub URL:
  - `https://github.com/OWNER/REPO/commit/FULL_SHA`
  - or `/pull/NUM/commits/FULL_SHA` when referencing a PR commit
- Resolve `OWNER/REPO` from the current repo.
- Expand short hashes to full SHA before linking.
- Use `suggestion` blocks only when confident the replacement matches the exact anchored line(s).

## Pending Review Semantics (Definition + Content Boundary)

Terminology used in these skills:

- "pending review" means a GitHub PR review whose API `state` is `PENDING` (draft):
  - it is visible only to the reviewer who created it until they submit it (COMMENT/APPROVE/REQUEST_CHANGES)
  - it is _not_ visible to the PR author or other reviewers while pending
  - assume everything in it may become public once submitted; draft accordingly

Content boundary:

- A pending review must contain only public-ready review content: objective, presentable, and directly related to the code under review.
- Exclude always:
  - agent internal reasoning
  - excerpts of internal conversation
  - tool outputs
  - meta-justifications
- The PR author should remain unaware that internal discussion exists.
- Prefer concrete fixes:
  - best: GitHub `suggestion` blocks with exact replacement code
  - otherwise: small code snippets or precise, actionable steps (concrete over vague descriptions).

## Existing Pending Review Awareness (Before Drafting or Posting)

For PR modes, run Pending Review Intake and Existing Pending Review Reconciliation from `pr_common.md`.

Keep this boundary here: draft/post/submit review feedback only after reconciliation is resolved when it is locally/API-verifiable.
Every PR-review output that may become GitHub review feedback must include the `Pending review reconciliation:` line from `pr_common.md`.

## Review Verdict (PR Review Mode Only)

After all findings are drafted, recommend an overall verdict:

- **Approve**: no CRITICAL/HIGH findings remain; all findings are LOW/MEDIUM nits or suggestions.
- **Request changes**: at least one CRITICAL or HIGH finding that must be addressed before merge.
- **Comment only**: findings exist but are informational/advisory; merge is not blocked.

State the recommendation and the reason.

Example:

- `Verdict: request changes — the unchecked error on line 42 can cause silent data loss`

The user decides whether to actually submit the verdict.

## Review Persistence

The internal findings queue and review progress are ephemeral by default.

Survive conversation pruning by reusing the existing hook-managed memory system.

Use only the existing store below; a parallel store would fragment state:

- Convention: `/tmp/specs/<pwd>/` from the parent SOP. Topic key: `review-<pr-number>` for PR modes (else `k-review`).
- The agent-owned intent file is `<topic>.txt`.
- The hook system additionally maintains `<topic>.worklog.jsonl`.
- Inspect review state only with a topic- or session-bound `,agent-memory status`;
  sessionless status can resolve a different topic in parallel sessions.
- If Agent Hook Context names the active topic, inspect that exact bucket with `,agent-memory status --topic <active-topic>`.
- If Topic Buckets supplies a session ID, bind the review bucket with `,agent-memory select <topic> --session-id <id> [--create]`, then inspect it with `,agent-memory status --session-id <id>`.
- On the first turn of a PR flow, check for the spec file and resume from it.
  After each thread/finding, append to `<topic>.txt` so the loop is resumable:
  - findings/threads: `comment_id`, author-type (`human`|`bot`), severity, file:line, one-line description, status (`open`|`fixed`|`dismissed`|`resolved`|`awaiting-approval`)
  - decision + evidence per thread (what base does, what changed, what was tested)
  - validation runs: commands + pass/fail + head SHA pushed
  - PR body obligations still open (sections to update, deletions to disclose)
  - open audit questions (e.g. unresolved `,kbn-pr-audit` findings)
  - current position in the queue (for iterative/Drain Mode) and base-context metadata
- On subsequent turns, check for the spec file first and resume from it if present.

## Posting Boundary

- Draft in chat first.
- If the user asks to post/submit/apply anything to GitHub:
  - keep the draft content from the review mode
  - then invoke the `k-github` skill via the Skill tool
  - get explicit approval for the GitHub side effect
- Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - explicit approval is absolute for any human-visible target
  - the only automation carve-out is a verified bot-authored thread
  - see `pr_fix.md` Drain Mode
  - bot-authored threads may be auto-replied/auto-resolved only inside a flow the user already invoked
