# Mode: Local Changes Review

Precondition:

- You already loaded `~/.agents/skills/review/SKILL.md`.
- Follow `~/.agents/skills/review/references/shared_rules.md` (loaded once by the router; do not re-load).

Use when:

- the user asks to review local work ("review local changes", "review this diff", "check what changed")
- or the repo has staged/unstaged changes
- or there is no PR for the current branch and the user still wants a review
- or the user asks to review a specific commit range ("review the last 3 commits", "review commits since <ref>")

## Core Principle: Verify and Fix

This mode is not about drafting comments for someone else. Local changes are the user's own work. The goal is to **verify everything, find issues, and fix them in the working tree immediately**. Treat every finding as something to resolve right now, not something to note for later.

- If something is wrong: fix it.
- If something is missing (tests, docs, error handling): add it.
- If something needs improvement: improve it.
- Report what you found and what you did — do not ask permission for each fix unless the change is large or ambiguous.
- All fixes are edits to working-tree files only. Do not commit or push unless explicitly asked.

## Investigation (Read-Only, Start Immediately)

- `git status --porcelain=v1 -b`
- `git diff --stat`
- `git diff`
- `git diff --staged`
- `git log --oneline --decorate -n 15`

### Scope selection

If staged/unstaged changes exist:

- Review those first (they are the ground truth).

If the user specified a commit range (e.g. "last 3 commits", "since <ref>"):

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

## Verify-and-Fix Workflow

1. **Build findings queue**: walk the entire diff against the coverage checklist (shared_rules.md). Order by severity (CRITICAL first).

2. **For each finding** (highest severity first): a. State what's wrong and why it matters (1-2 lines). b. Verify the issue is real (base-context comparison, `/tmp` reproduction, or test run — do not assert without evidence). c. Fix it. Apply the smallest correct change. d. If the fix is non-trivial or ambiguous (multiple valid approaches, significant scope): state the options and your recommended default, then proceed with the default unless the user intervenes.

3. **Quality gates** (after all fixes in a batch):
   - Run lint + type_check + tests (discover correct commands from the repo; do not guess).
   - If checks fail, diagnose and fix. Repeat until green or report what remains broken and why.

4. **Summary**: after all findings are processed, output a concise summary:
   - `Base context:` line (see shared_rules.md)
   - Findings: what was found, what was fixed, what was verified
   - Remaining: anything that could not be fixed (and why)
   - Quality gates: what was run, pass/fail

### Iterative mode (when the user asks for one-at-a-time)

If the user says "one at a time" or "step by step":

- Process exactly one finding per turn: state it, verify it, fix it, run quality gates.
- Stop and wait for the user before the next finding.

## Extra Constraints

- Do not commit/push unless explicitly asked.
- Code changes are expected and encouraged — this is the user's own work being improved.
- Keep the internal findings queue in the review persistence spec (see shared_rules.md) so progress survives conversation pruning.
