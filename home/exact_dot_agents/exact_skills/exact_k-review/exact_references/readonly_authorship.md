# Authorship Resolution

Resolve `authorship` before selecting a mode. This file is loaded once by the router; mode files reuse it.

Allowed values:

- `self`
- `other`
- `unknown`

Exception: plan review mode has no code target. Record `authorship: n/a`, skip the git/`gh` probes below, and produce feedback only.

This input gates whether the review may edit code. Resolve it in the local/branch path too.
Resolve `self` only from verified evidence; a locally checked-out change alone still needs the probes below.

When a PR is involved:

- Run: `gh pr view <number> --json author --jq '.author.login'`
- Compare against: `gh api user --jq '.login'`
- Match -> `self`; mismatch -> `other`; cannot resolve -> `unknown`.
- For `authorship: other` or `unknown`, also classify `author_relation` for the review verdict:
  - `immediate_team`: verified from a loaded domain overlay, repo/team evidence, or explicit user-provided context.
  - `outside_or_unknown_team`: any author not verified as immediate team.
  - Do not infer immediate-team membership from org membership, CODEOWNERS, username familiarity, or prior memory alone.

When there is no PR (local changes / branch-delta / commit-range review):

- Identify the current user: `gh api user --jq '.login'` (fall back to `git config user.email` if `gh` is unavailable).
- Check the branch's tracked remote with bounded read-only git probes in large repositories:
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false rev-parse --abbrev-ref --symbolic-full-name @{u}`
  - `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false remote -v` for that remote's URL/owner
- A branch tracking another person's fork is `other` (e.g. `someoneelse/<branch>`).
- Check authorship of the commits under review: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD`.
  Commits authored by someone other than the current user make it `other`.
- Only uncommitted/staged working-tree changes, or commits/branch owned by the current user, resolve to `self`.
  If it cannot be verified, it is `unknown`.

This affects mode behavior:

- **`self` (user owns the change):**
  - find issues and fix them in the working tree
  - draft review comments only if the user plans to post self-review notes
- **`other` / `unknown`:**
  - produce draft comments/suggestions only
  - keep code unchanged
  - editing requires the user to explicitly say to fix it (e.g. "fix these" or "take over this branch")
