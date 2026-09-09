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

Authorship is an input to write scope (see `~/.agents/skills/k-review/references/authorship.md`), not edit authority by itself.

Resolve authorship via the router's Role Detection / Authorship section.

Do not assume `self` just because the change is checked out locally:

- a branch tracking another person's fork is `other`
- commits authored by someone else are `other`

If authorship is `other` or `unknown`:

- follow `~/.agents/skills/k-review/references/shared_rules.md` Hard Constraints
- surface findings with proposed fixes and stop

## Read-Only Role Override

When this mode is loaded inside any read-only review worker, that worker's role contract and packet scope take precedence.

## Core Principle: Fix Authority Follows Write Scope

For `self` authorship, executing inline (not inside a read-only review worker per the override above): find and fix are one pass, not two —
a finding is fixed as soon as it's found, no separate request needed.
New final findings past that pass are reported, per the packet's own final-Verify boundary if one applies.
For `other`/`unknown` authorship, or when loaded inside a read-only review worker: read-only final judgment —
known authorized fixes are produced before the final Verify stage; review alone grants no repair authority, and the root applies SOP §3.5 when existing authority covers recovery.
Local ownership alone does not authorize commit or push — those stay separately gated per SOP §3.2 regardless of write scope on the files themselves.

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

Follow the base-branch context gate in `~/.agents/skills/k-review/references/shared_rules.md`. This is mandatory.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Use a substantial strong final review/refute packet when isolation is useful, with the frozen diff, selected risk questions, and existing evidence.
Do not launch findings auditors, a verifier of the review, post-review cleanup, or automatic convergence.
Keep discovery context and raw outputs outside the root; retain compact conclusions and pointers.
Honor explicit no-delegation instructions inline.

## Output

Return scope/base identity, anchored findings, final check results, and unresolved evidence gaps.
If earlier authorized production changed files, report those changes and compatibility impact separately from the review verdict.

## Iterative mode (when the user asks for one-at-a-time)

Present one finding per user turn when requested; retain the completed review evidence and queue.
Do not rerun review/checks merely to present the next finding.
A requested repair follows existing task authority when it covers the finding; otherwise it is a new authorized attempt.

## Extra Constraints

- Do not commit/push unless explicitly asked.
- For `self` authorship executing inline, write scope on the local working tree is the fix authority — no separate fix request is needed.
  For `other`/`unknown` authorship, or inside a read-only review worker, an explicit fix request is required regardless of authorship (see Authorship Precondition and the Read-Only Role Override above).
- Under `other`/`unknown` authorship, this mode is draft-only (see Authorship Precondition).
- Keep the internal findings queue in the review persistence spec (see ~/.agents/skills/k-review/references/shared_rules.md) so progress survives conversation pruning.
