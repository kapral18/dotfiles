# Mode: Local Changes Review

Precondition:

- You already loaded `~/.agents/skills/k-review/SKILL.md`.
- Follow `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/shared_rules.md` (loaded once by the router; do not re-load).

Use when:

- the user asks to review local work ("review local changes", "review this diff", "check what changed")
- or the repo has staged/unstaged changes
- or there is no PR for the current branch and the user still wants a review
- or the user asks to review a specific commit range ("review the last 3 commits", "review commits since `<ref>`")

## Authorship Precondition

This mode's verify-and-fix behavior assumes `authorship: self`.

Resolve authorship via the router's Role Detection / Authorship section.

Do not assume `self` just because the change is checked out locally:

- a branch tracking another person's fork is `other`
- commits authored by someone else are `other`

If authorship is `other` or `unknown`:

- follow `shared_rules.md` Hard Constraints
- surface findings with proposed fixes and stop

## Delegated Worker Override

When this mode is loaded inside any read-only review worker, that worker's role contract takes precedence over this file's fix directives.

## Core Principle: Verify and Fix (when `authorship: self`)

In a direct local-changes review, local changes you own are the user's own work.

Goal:

- verify everything
- find issues
- fix them in the working tree immediately

Treat every finding as something to resolve right now, not something to note for later.

- If something is wrong: fix it.
- If something is missing (tests, docs, error handling): add it.
- If something needs improvement: improve it.
- Report what you found and what you did — proceed with each fix directly, asking permission only when the change is large or ambiguous.
- All fixes are edits to working-tree files only. Commit or push only when explicitly asked.

## Investigation (Read-Only, Start Immediately)

- `git status --porcelain=v1 -b`
- `git diff --stat`
- `git diff`
- `git diff --staged`
- `git log --oneline --decorate -n 15`
- Never review diff hunks in isolation: read full enclosing files and trace callers/consumers to discover blast radius and impact on preexisting surrounding behavior.
- Probe history: in large repos, run targeted line-bounded probes (`git blame -L <start>,<end>` / `git log -n 5 -L`) on modified guards, defensive checks, and error branches to uncover why existing code was written and ensure past bug fixes are preserved.

### Scope selection

If staged/unstaged changes exist:

- Review those first (they are the ground truth).

If the user specified a commit range (e.g. "last 3 commits", "since `<ref>`"):

- Use `git diff <ref>...HEAD` and `git log --oneline <ref>..HEAD` to scope the review.
- If the range reference is ambiguous, ask one direct question.

If the working tree is clean (and no commit range specified):

- Resolve base with: `git symbolic-ref --short refs/remotes/origin/HEAD`
- Review branch delta using:
  - `git diff <base>...HEAD`
  - `git log --oneline <base>..HEAD`
- If base cannot be resolved, ask one direct question for the base target.

If there are no diffs at all:

- Say so plainly and stop (nothing to review).

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## Agent-Assisted Verify-and-Fix Workflow

Launch one `reviewer`/`review-worker` `correctness-regressions` lane for the scoped diff when the harness supports subagents;
add one extra lane only for an independently evidenced risk class.
Select both from `lanes.md` and paste the chosen lane's `Lens skill` line and `Checks` list into the worker's scope packet;
workers never load `lanes.md`.
Run any repo-wide suite or full build once here and pass the result into every scope packet — lanes are told not to repeat shared work.
If the harness cannot delegate, run the finder pass inline and report `agent_lane=inline-degraded`.
Run live UI only when UI/runtime evidence is needed for a candidate and a startable runtime is available;
use `k-deep-review` for the full live-UI target-packet/controller graph.
Run the Findings-Set Audit from `judging_core.md` in the controller over the candidate set before adversarial verification.
If the audited candidate set is empty, skip adversarial work and report `Adversarial verification: skipped (no candidates after findings audit)`.
Otherwise, run `adversarial-verifier` over the audited candidate set before fixing;
if no verifier lane is available, run the Candidate Refutation Ladder inline and report `adversarial=inline-degraded`.
Then apply the Verify-and-Fix Loop's fix, quality-gate, and Post-Review Stage steps from `judging_core.md` over surviving findings.
Then output a concise **summary**:

- `Base context:` line (see shared_rules.md)
- Findings: what was found, what was fixed, what was verified
- Remaining: anything that could not be fixed (and why)
- Quality gates: what was run, pass/fail
- Post-review: hygiene findings on the fix diff and how they were resolved

### Iterative mode (when the user asks for one-at-a-time)

If the user says "one at a time" or "step by step":

- Process exactly one finding per turn through the loop: state it, verify and refute it, fix it, run quality gates.
- Stop and wait for the user before the next finding.
- Run the Post-Review Stage after the last finding is resolved, following its fixed-point repeat rule until clean or blocked.

## Extra Constraints

- Do not commit/push unless explicitly asked.
- Code changes are expected and encouraged when `authorship: self`.
- Under `other`/`unknown` authorship, this mode is draft-only (see Authorship Precondition).
- Keep the internal findings queue in the review persistence spec (see shared_rules.md) so progress survives conversation pruning.
