# Mode: Local Changes Review

Precondition:

- You already loaded `~/.agents/skills/k-review/SKILL.md`.
- `~/.agents/skills/k-review/references/judging_core.md` and `~/.agents/skills/k-review/references/shared_rules.md` are the reviewer worker's mechanics; pass them in the review packet.
  The root does not preload them; when a step below names one of their gates, the root reads only that gate's section.

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

## Fix Authority

Fix authority follows write scope per `~/.agents/skills/k-review/references/authorship.md` (SOP §3.7: only review, refute, research, and audit packets are read-only, by category).
New final findings past the Produce fix pass are reported, per the packet's own final-Verify boundary if one applies.
Local ownership alone does not authorize commit or push — those stay separately gated per SOP §3.2 regardless of write scope on the files themselves.

## Scope Evidence (Root, Read-Only, Start Immediately)

- `git status --porcelain=v1 -b`
- `git diff --stat` and `git diff --staged --stat`
- `git diff --diff-filter=D --stat`
- `git log --oneline --decorate -n 15`
- Write the frozen candidate to a file for the packet (`git diff HEAD > <scratch>/candidate.patch`) and record its hash; do not read it.
- The root read bound in `~/.agents/skills/k-review/SKILL.md` Root moves applies: no diff hunks, changed-file bodies, callers, or blame output in root context before the packet returns.

## Worker Investigation (Passed In The Packet)

The review worker runs these from the packet; the root pastes them and MUST NOT perform them itself:

- `git diff` / `git diff --staged` (or the frozen patch) read in full
- Never review diff hunks in isolation: read full enclosing files and trace callers/consumers to discover blast radius and impact on preexisting surrounding behavior.
- Probe history: in large repos, run targeted line-bounded probes (`git blame -L <start>,<end>` / `git log -n 5 -L`) on modified guards, defensive checks, and error branches to uncover why existing code was written and ensure past bug fixes are preserved.

### Scope selection

If staged/unstaged changes exist:

- Review those first (they are the ground truth).

If the user specified a commit range (e.g. "last 3 commits", "since `<ref>`"):

- Scope with `git diff --stat <ref>...HEAD` and `git log --oneline <ref>..HEAD`; the full `git diff <ref>...HEAD` goes into the packet.
- If the range reference is ambiguous, ask one direct question.

If the working tree is clean (and no commit range specified):

- Resolve base with: `git symbolic-ref --short refs/remotes/origin/HEAD`
- Scope the branch delta with `git diff --stat <base>...HEAD` and `git log --oneline <base>..HEAD`; the full `git diff <base>...HEAD` goes into the packet.
- If base cannot be resolved, ask one direct question for the base target.

If there are no diffs at all:

- Say so plainly and stop (nothing to review).

## Base-Branch Context

Follow the base-branch context gate in `~/.agents/skills/k-review/references/shared_rules.md`. This is mandatory.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.
Launch one strong review subagent using `~/.agents/skills/k-review/references/reviewer-worker.md` before any final judgment, with the frozen diff, copied selected risk questions, and existing evidence.
This mode and the router describe the same required packet, not additive launches.
The root MUST NOT substitute its own inline review for that packet absent an explicit user no-delegation instruction.
If the required lane or tool is unavailable, report blocked; do not silently fall back to an inline review.
Do not launch findings auditors, a verifier of the review, post-review cleanup, or automatic convergence.
Keep discovery context and raw outputs outside the root; retain compact conclusions and pointers.
The router's root read bound governs every read before the packet returns.
Await the terminal packet result before the verdict; no spawning from a child.
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
- Fix authority: see Fix Authority above; under `other`/`unknown` authorship this mode is draft-only (see Authorship Precondition).
- Keep the internal findings queue in the review persistence spec (see ~/.agents/skills/k-review/references/shared_rules.md) so progress survives conversation pruning.
