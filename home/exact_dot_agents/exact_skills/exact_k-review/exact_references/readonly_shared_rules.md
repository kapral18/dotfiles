# Shared Review Rules

All review modes load this file. Do not duplicate these rules in mode files.

The surface-agnostic judging engine lives in two files under `~/.agents/skills/k-review/references/`:

- `judging_core.md` covers Truth Validation, the Candidate Refutation Ladder, the gates (State-Machine, Async-Derived State, Context-Divergence, Scale-Behavior, Deletion-Safety, Replacement/Migration Parity, Historical-Rationale, Semantic-Projection, Product-Flow, Signal-Quality, Systemic-Risk), and Severity.
- `judging_pipeline.md` covers the Coverage Checklist, Post-Review Lens + Stage, Findings-Set Audit, and Verify-and-Fix Loop.

Load both alongside this file.

This file carries the shared intake, base-context, and persistence rules layered on top of that core.
Before drafting review comments/replies/descriptions or recommending a PR verdict, load `~/.agents/skills/k-review/references/review_delivery.md`.
Before any GitHub posting step, load that same reference and apply its Posting Boundary.
Do not load delivery mechanics for a local/plan report that contains no public-ready review draft.

## Read-Only Probes

- Start read-only investigation immediately. Do not ask for confirmation before read-only `git`/`gh` checks.
- In large repositories, make first-pass git probes bounded: use `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false` for status, diff names, upstream, and log probes.
  If a plain git probe produces no output after one short wait, stop it and rerun the bounded form.
- Keep searches narrow by default: include path scopes, file globs, or exact symbols.
  When the harness provides native search/listing tools, prefer those for first-pass broad searches.
  Use shell `rg` only after narrowing by path, glob, or exact symbol; never run bare repo-root `rg <pattern>` in a large repository.
  Do not run broad repo-wide searches or dump full command output when a file list, count, or targeted lines answer the question.
- When command output is saved/truncated, recover only the exact lines needed for the current decision unless the decision depends on every item.

## Hard Constraints

- External truth applies: verify behavior under review (tests, repros, `/tmp` simulations) before asserting when practical.
- Code changes:
  - **Read-only delegated workers**: their full contract is `~/.agents/skills/k-review/references/reviewer-worker.md`;
    do not restate it here. Controller-side obligations it creates:
    - run repo-wide suites, full builds, and whole-suite test runs **once** in the controller and pass the result into every lane's scope packet; lanes are told not to repeat them
    - resolve each returned `verification_needed` serially, or record why it stayed open
    - lanes return proposed fixes only; the controller owns every edit and side effect
  - **Local changes mode with `authorship: self`** and **PR fix mode when edits are permitted**:
    - find issues and fix them in the working tree immediately
    - code changes are expected as part of the workflow
    - no extra permission needed
    - do not commit or push unless explicitly asked
  - **Local changes mode with `authorship: other` or `unknown`**: draft-only unless the user explicitly asks to fix/take over.
  - **PR review mode (self-review)**: same — find and fix in the working tree.
  - **PR review mode (reviewing others or unknown authorship):** stay draft-only;
    change code only when the user explicitly asks to fix/take over and the flow switches to PR fix mode.
- Post to GitHub, submit reviews, apply labels, or resolve threads only when explicitly asked.
- Exception per the Human-Visible Publication Gate (SOP, `~/AGENTS.md`):
  - a **verified bot-authored** thread may be auto-replied/auto-resolved inside an explicitly-invoked flow
  - a bounded SOP approval packet may apply only through its owning skill or reference
  - every other human-visible target stays supervised: draft -> show payload -> wait
  - ambiguous/mixed threads fail safe to human
- Assume the user started the agent inside the intended repo/worktree/session:
  - do not create/switch worktrees proactively
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
- Do not move on to base-context reasoning or comment drafting until this preflight is complete.

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
- This line is reviewer metadata for the assistant's output. Do not include it in GitHub comment bodies.

## Draft Style (Public-Ready)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Pending Review Semantics (Definition + Content Boundary)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Existing Pending Review Awareness (Before Drafting or Posting)

For PR modes, run Pending Review Intake and Existing Pending Review Reconciliation from `pr_common.md`.

Keep this boundary here: if reconciliation is unknown and locally/API-verifiable, do not draft/post/submit review feedback.
Every PR-review output that may become GitHub review feedback must include the `Pending review reconciliation:` line from `pr_common.md`.

## Review Verdict (PR Review Mode Only)

Before drafting or a PR verdict: load `review_delivery.md` (matching heading).

## Review Persistence

The internal findings queue and review progress are ephemeral by default.

Survive conversation pruning by reusing the existing hook-managed memory system.

Do not invent a parallel store:

- Convention: `/tmp/specs/<pwd>/` from the parent SOP. Topic key: `review-<pr-number>` for PR modes (else `k-review`).
  Take `<pr-number>` from the `,gh-prw --number` output of this session, never from memory or a context summary;
  a summarized context has produced a wrong number before, and the wrong bucket then carries every later turn.
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
- Review identity and lane ledger (write before the first lane launch, update on every launch and return):
  - `pr: <owner/repo>#<n>` (or `local: <base>..<head>`), `pack: <root>`, `base_sha`, `head_sha`, `snapshot_at`, `discussion_at`
  - `lane: <id or description> angle=<lane> model=<value> launch_wait=<blocking|background> state=launched|returned|discarded`
  - the adversarial verifier and any memory judge/scribe spawn are lanes too; record them the same way
- Verified-fact and media ledger:
  - `fact: <claim> — <anchor> — <verified_at>` for every fact this session verified
  - `media: <file> — <caption> — viewed` for every image viewed; view each image once
  - `round: <n> fixed=<files> gates=<result>` after every fix round
- After a context summary, a `fact:` or `media:` line this session wrote with an anchor is trusted.
  Re-verify it only when a new finding depends on it or Drift reports its artifact changed.
  Re-reading the pack, re-viewing media, or re-running a gate to confirm a ledgered fact is a defect, not diligence.
  SOP §2.8 skepticism applies to other agents' reports, not to this session's anchored ledger.
- Before launching any lane, re-read `<topic>.txt`.
  A lane in `state=launched` is awaited or collected, never relaunched: a second launch of the same angle is a bug, not diversity.
  After a context summary, the ledger is the only record of what is already running; trust it over recall.
- Do not present a verdict, a findings summary, or a draft while any lane is `state=launched`;
  collect it first, or mark it `discarded` with a reason and say so in the output.
- On subsequent turns, check for the spec file first and resume from it if present.

## Posting Boundary

Before any GitHub posting step: load `review_delivery.md` → "Posting Boundary".
