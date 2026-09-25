---
name: k-review
description: "Use for standard-rigor review of local changes, PRs, review threads, PR fixes, or plans."
---

# Review Router

Subagent dispatch: review — one reviewer-worker packet per mode; the light path uses one change-auditor packet via k-light-review.

Goal: route standard-rigor review requests to the correct mode while keeping shared rules loaded once.

Contract:

- This router is the entrypoint. If another skill points you here for shared rules, you may skip routing and jump to the relevant section.
- After selecting a mode, open exactly one primary mode file and follow it:
  - `~/.agents/skills/k-review/references/local_changes.md`
  - `~/.agents/skills/k-review/references/pr_review.md`
  - `~/.agents/skills/k-review/references/pr_fix.md`
  - `~/.agents/skills/k-review/references/plan_review.md`
- Before entering any mode, load once, in one read: `~/.agents/skills/k-review/references/authorship.md`.
- Root read budget: the root loads this router, `authorship.md`, `lanes.md`, and exactly one mode file.
  `judging_core.md`, `judging_pipeline.md`, and `shared_rules.md` are reviewer-worker mechanics (`reviewer-worker.md` loads `judging_core.md` itself); the root MUST NOT preload them.
  When a mode file names a specific gate from one of those files (for example the Base-Branch Context Gate in `shared_rules.md`), the root reads only that gate's section, not the whole file.
  The root MUST NOT open `runtime-harnesses.md` or `context-pack.md`; those are pointers passed in the packet, and a launch failure is reported with its exact error rather than diagnosed by reading harness docs.
- Mode files reference those files but do not re-load them while in context.
- Follow required phase references; ledger phase, references, completed evidence, and open gates. Blocked gates stay blocking.
- PR modes load `~/.agents/skills/k-review/references/pr_common.md` and `~/.agents/skills/k-review/references/pr_snapshot.md` once, from the mode file, when the mode reaches the gate that needs them.
- Every reference stays under 20 KB so one read returns it whole (`~/.local/share/chezmoi/scripts/verify_agent_file_sizes.py`);
  a concatenated bundle would be truncated by the strictest harness view tool, so there is none.
- Load `~/.agents/skills/k-review/references/pr_context_audits.md` only when `~/.agents/skills/k-review/references/pr_common.md`'s conditional Ambient Topic Exploration or PR Necessity + Correctly-Open Audit gate triggers.
- Reference and open skill files under `~/.agents/skills/` only.
  `~/.cursor/skills` is a symlink to the same tree; opening a file under both paths is a duplicate read of the same bytes.
- After a context summary, re-open only the files the active mode needs; the summary is not a substitute for them.
  Do not re-open a reference to re-check a rule the summary already records as satisfied;
  re-open it only when a pending gate still depends on its wording.
  Resume from Review Persistence; apply PR Drift. Report invalidated evidence; never replay completed phases or relaunch outstanding lanes.
- Do not load `k-git`, `k-compose-pr`, `k-communication`, or a CI skill at intake.
  Load `~/.agents/skills/k-github/SKILL.md` only for read-only Targeting and GitHub Context Intake + Reference Resolution required by shared assessment; NEVER route that intake into posting or mutation.
  When SOP §3.1 makes release/backport relevance applicable, establish targets from verified policy or the domain overlay.
  Label, release-note, and version metadata classification otherwise runs only when the user asks for labels or a PR body, and MUST NOT mutate metadata automatically.
  Load `k-buildkite` only when the CI Coverage Gate needs a job's contents.
- Keep read-only PR inspection/review inside this router.
  Invoke the `k-github` skill via the Skill tool for posting only when the user explicitly asks to post/submit anything to GitHub.
- If the user wants review analysis and GitHub posting in the same request:
  - keep the review router primary
  - draft/verify through review mode first
  - read-only Targeting and GitHub Context Intake + Reference Resolution follow the rule above;
    invoke the `k-github` skill via the Skill tool for the posting step only after draft/verify

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Review runs once in the session's final Verify stage.
Read `~/.agents/skills/k-review/references/lanes.md` to select applicable criteria and pass their named mechanics to any final packet.
Preserve requested review and adversarial lenses; for deep or high-risk work, assign them distinct questions against the same frozen candidate.
Low-risk work needs only its applicable judgment. Specialists consume shared evidence, not one another's verdicts.
Do not chain finder, audit, adversarial, fresh-eyes, or post-review passes. Do not invoke convergence automatically.
Collect scope-level evidence in Understand; produce known fixes within the current packet's write scope (`~/.agents/skills/k-review/references/authorship.md`) before entering Verify.
Research packets return compact evidence, not transcripts. Direct deterministic checks require no mechanical agent.
Launch one strong review subagent using `~/.agents/skills/k-review/references/reviewer-worker.md` (the `k-agent-review-worker` or `k-agent-reviewer` profile as exposed by the active harness, or the active harness's generic review-category type carrying that contract where neither named profile exists) before any final judgment, in every `k-review` mode; the light path routed to `k-light-review` uses its own change-auditor packet instead. Pass the copied selected criteria and mode lens, not a router or roster. Per-harness profile names live in `~/.config/ai/agent-bands.v1.json` → `harnesses.<h>.agents`.
This router and the selected mode file describe the same required packet, not additive launches.
The root MUST NOT substitute its own inline review for that packet absent an explicit user no-delegation instruction.
If the required lane or tool is unavailable, report blocked; do not silently fall back to an inline review.
The root still owns scope, scope-level evidence, deterministic checks, integration, and terminal synthesis; the substantive review judgment executes in the worker.
Root read bound: until the review packet returns, the root reads only scope-level evidence: `git status`, `git diff --stat` / `--name-only` / `--diff-filter=D --stat`, `git log --oneline`, authorship probes, check receipts, PR discussion and referenced artifacts needed for named material questions, and the patch it writes to a file for the packet.
The root MUST NOT read diff hunks, changed-file bodies, callers, or blame output before that packet returns; those reads are the worker's mechanics and travel in the packet, not in root context.
After the packet returns, root reads stay bounded to synthesis of the returned findings or an evidence-backed repair under SOP §3.5.
Await the terminal packet result before the verdict; no spawning from a child.
After dispatching an async packet, end the turn; do not fill the wait with reference reads or speculative scope work.
Consume the returned artifact once: when the completion notice carries only a saved-output pointer, read that file; when it carries the body inline, do not re-read the file.
Harness-specific invocation caveats live in `~/.agents/skills/k-review/references/runtime-harnesses.md` (and, for Pi/OMP, `~/.agents/skills/k-review/references/runtime-harnesses-pi-omp.md`) as a packet pointer only; the root does not open them (Contract above). A dispatch rejected before execution (schema or guard) is an invalid call: correct it, never retry it unchanged, never re-ask permission. Retry an identical packet once only when the tool executed and reported a host, bootstrap, or runner failure; then report the exact error. A child that timed out or exhausted its budget is re-sized (split, or ship materialized inputs), never relaunched identical.

## Secondary Skill Escalation

Do not load secondary skills until read/diff evidence proves the surface is in scope.

- Load semantic code search only for base context after the selected mode requires base-branch context.

## Draft-PR Policy

- Never review someone else's draft PR unless the user explicitly asks.
- If a PR is in draft state and the user did not explicitly request a review, stop and note: "This PR is a draft —
  skipping review unless you explicitly ask."
- When a draft PR is reviewed (because explicitly asked), apply the same mode, criteria, and depth as for a ready PR.

## PR Detection (Do First When PR Is Involved)

If the user mentions or strongly implies a PR (PR/pull request, PR review, threads, "check my PR comment", "recheck this fix from the PR", etc.):

- First step is PR discovery via `,gh-prw` (read-only):
  - `,gh-prw --number` returns the current branch's PR number when one exists.
  - `,gh-prw --number <n>` resolves a specific number, URL, branch, or commit SHA against the upstream repo.
- If `,gh-prw` cannot resolve the user's claim, run the k-github `Targeting` fallback chain (`gh pr view [--repo OWNER/REPO] <n>` → `gh pr view` (no args) → `gh pr view <branch> --repo <owner>/<repo>` → `gh issue view <n>`).
  Treat the first `could not resolve` as a hint, not an answer.
- Step `gh auth status` once up front so the authenticated principal is known before any of the above.
  Identity mismatches between `gh api user` and the branch's tracked remote are facts, not hypotheses.
- Last resort: ask for the URL/number.

Continuity rule:

- If the conversation is already clearly in a specific mode, stay in that mode when the user says "continue" / "next" unless they explicitly switch targets.

## Verdict Gate (PR Mode Only)

See `~/.agents/skills/k-review/references/pr_common.md` → "Verdict Gate" before claiming `Verdict: merge-ready` on the first response of a PR review.

## Role Detection / Authorship (Mandatory In Every Mode)

See `~/.agents/skills/k-review/references/authorship.md` (loaded once by the router).

## Mode Selection (Intent + Evidence)

Pick exactly one mode. If ambiguous, ask one fork-closing question and state a default.

### Mode: PR fix (address reviewer feedback)

- Use when the user asks to reply to reviewer comments, address conversations, resolve review threads, or apply requested changes with verification.
- Then open: `~/.agents/skills/k-review/references/pr_fix.md`

### Mode: PR review (initial or continued)

- Use when the user wants an initial PR review, continued review, or verification that a PR fix resolves a bug.
- Role modifies behavior: see Role Detection above and `~/.agents/skills/k-review/references/pr_review.md`.
- Then open: `~/.agents/skills/k-review/references/pr_review.md`

### Mode: Local changes review (working tree, branch delta, or commit range)

- Use when: the user asks to review local changes/diff, a commit range, or a no-PR branch delta.
- If no PR is involved, apply the Light-Eligibility Predicate before opening `~/.agents/skills/k-review/references/local_changes.md`: all of local-only diff, verified self-authorship, reversible change, focused observable check, and semantically simple behavior must hold; unknown is not eligible; PR context, explicit full/deep review, security/auth/crypto, persisted data, public API, deletion/replacement, stateful/parser/workflow behavior, or required base/runtime investigation excludes the light path.
  When self-authored and trigger-free, route to `k-light-review` unless the user explicitly requested full/deep review;
  it is cheaper, not weaker. Otherwise open `~/.agents/skills/k-review/references/local_changes.md`.

### Mode: Plan review (before implementation)

- Use when the user asks to review a plan, design doc, implementation proposal, RFC, issue body, or pasted text rather than a diff.
- Then open: `~/.agents/skills/k-review/references/plan_review.md`

## Disambiguation (If Still Unclear)

If the user's intent is still unclear, resolve via local context (do not guess):

- If the subject is a document, issue body, or pasted text rather than a code target: plan review mode.
- If not in a git repo:
  - Ask: "Is this a GitHub PR review (send URL/number), a local repo changes review, or a plan/design document review?"
- If in a git repo:
  - Run `git status --porcelain=v1 -b` (read-only, do not ask to proceed).
  - Independently check both:
    - whether staged/unstaged changes exist
    - whether `,gh-prw --number` resolves a PR for the current branch
  - If both are true: default to local changes mode (review the working tree; do not infer fix authority).
    Note the PR exists in output so the user can switch if needed.
  - If only local changes exist: local changes mode.
  - If only a PR exists: PR review mode.
  - If neither exists: local changes mode (branch delta).
  - Downward routing: when local changes mode applies with no PR, apply the Light-Eligibility Predicate above.
