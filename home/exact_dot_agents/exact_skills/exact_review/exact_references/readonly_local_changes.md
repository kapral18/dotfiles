# Mode: Local Changes Review

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).

Use when:

- the user asks to review local work ("review local changes", "review this diff", "check what changed")
- or the repo has staged/unstaged changes
- or there is no PR for the current branch and the user still wants a review

## Investigation (Read-Only, Start Immediately)

- `git status --porcelain=v1 -b`
- `git diff --stat`
- `git diff`
- `git diff --staged`
- `git log --oneline --decorate -n 15`

If staged/unstaged changes exist:

- Review those first (they are the ground truth).

If the working tree is clean:

- Resolve base with: `git symbolic-ref --short refs/remotes/origin/HEAD`
- Review branch delta using:
  - `git diff <base>...HEAD`
  - `git log --oneline <base>..HEAD`
- If base cannot be resolved, ask one direct question for the base target.

If there are no diffs at all:

- Say so plainly and stop (nothing to review).

## Base-Branch Context

Follow the base-branch context gate in `shared_rules.md`. This is mandatory.

## Output

- Default: batch `Pending review draft` with:
  - `Base context:` line (see shared_rules.md)
  - `inline_comments`: where, issue, why, verification, smallest fix
  - optional `summary_comment`
- Use a collaborative close only when it fits naturally.
- If the user asks for one-at-a-time, output exactly one finding and stop.

## Extra Constraints

- Do not commit/push unless explicitly asked.
- Keep an internal findings queue ordered by severity; draft highest-risk items first.
