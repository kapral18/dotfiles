# Mode: Local Changes Review

Precondition:

- You already loaded `~/.agents/playbooks/review/router.md` and are following
  its shared rules.

Use when:

- the user asks to review local work ("review local changes", "review this diff",
  "check what changed")
- or the repo has staged/unstaged changes
- or there is no PR for the current branch and the user still wants a review

Investigation (read-only, start immediately):

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

Base-branch context gate (mandatory):

- For any review that compares against base-branch behavior/invariants:
  - Follow the router's base-branch context rule.
  - If the user did not provide an index name: run `list_indices` (try both
    `scsi-main` and `scsi-local`) to determine whether the repo is indexed.
  - If the repo is indexed, semantic code search is required for base context:
    - `~/.agents/playbooks/code_search/semantic_code_search.md`
    - Select and record the index.
    - Invoke at least one SCSI tool to establish base behavior/invariants.
- If the repo is not indexed / tools unavailable, use local base context via
  `git show <base>:<path>` + `rg`.

Output:

- Default: batch `Pending review draft` with:
  - `inline_comments`: where, issue, why, verification, smallest fix
  - optional `summary_comment`
- End each drafted comment with `Wdyt`.
- If the user asks for one-at-a-time, output exactly one finding and stop.

- Always include one line near the top:
  - `Base context: SCSI=<index>|none (list_indices checked; <reason>), base=<branch>, diff=<base>...HEAD`
  - This is reviewer metadata; do not paste it into GitHub.

Extra constraints:

- Do not commit/push unless explicitly asked.
- Keep an internal findings queue ordered by severity; draft highest-risk items
  first.
- Follow the router's mandatory base-branch context step when applicable
  (semantic code search if indexed; otherwise `git show`/`rg`).
