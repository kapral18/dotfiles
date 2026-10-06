# Mode: Local Changes Review

Use when the user asks to review local work, a diff, a commit range, or a branch with no PR.

## Authorship

Resolve authorship per `~/.agents/skills/k-review/references/authorship.md`. Do not assume `self` because the change is checked out locally:
a branch tracking another person's fork is `other`, and commits by someone else are `other`.
For `other` or `unknown`, report findings with proposed fixes and stop.

## Scope

Start with read-only scope evidence:

- `git status --porcelain=v1 -b`
- `git diff --stat`, `git diff --staged --stat`, `git diff --diff-filter=D --stat`
- `git log --oneline --decorate -n 15`

Select the scope:

- Staged or unstaged changes exist: review those first; they are the ground truth.
- The user named a commit range ("last 3 commits", "since `<ref>`"): `git diff <ref>...HEAD` and `git log --oneline <ref>..HEAD`.
  Ask one question if the ref is ambiguous.
- Clean tree and no range: resolve base with `git symbolic-ref --short refs/remotes/origin/HEAD`, then review `git diff <base>...HEAD`.
  Ask for the base if it cannot be resolved.
- No diff at all: say so and stop.

## Review

- Read the full diff, then the full enclosing files, callers, and consumers.
- Run the Base-Branch Context Gate in `~/.agents/skills/k-review/references/shared_rules.md`, including line-bounded history probes on modified guards and error branches.
- Judge per `~/.agents/skills/k-review/SKILL.md` How to review.

## Fixes

With `self` write scope, fix supported findings in the same pass inside `~/.agents/skills/k-review/references/review_fixes.md` Fix Scope, then run the affected checks once.
Local ownership never authorizes commit or push.

## Output

Scope and base identity, anchored findings, fixes applied (if any) with check results, and unresolved evidence gaps.

When the user asks for one finding at a time, present one per turn from the queue (`shared_rules.md` Review Queue);
do not rerun review or checks to present the next one.
