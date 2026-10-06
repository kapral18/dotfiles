# Authorship Resolution

Resolve `authorship` before selecting a mode. Allowed values: `self`, `other`, `unknown`.
Plan review has no code target: record `authorship: n/a`, skip the probes below, and give feedback only.

Resolve `self` only from verified evidence; a locally checked-out change alone is not proof.

When a PR is involved:

- Run `gh pr view <number> --json author --jq '.author.login'` and compare with `gh api user --jq '.login'`.
- Match → `self`; mismatch → `other`; cannot resolve → `unknown`.
- For `other` or `unknown`, also classify `author_relation` for the verdict:
  - `immediate_team`: verified from a loaded domain overlay, repo/team evidence, or explicit user context.
  - `outside_or_unknown_team`: anyone not verified as immediate team.
  - Do not infer team membership from org membership, CODEOWNERS, username familiarity, or memory.

When there is no PR (local changes, branch delta, commit range):

- Identify the current user: `gh api user --jq '.login'` (fallback `git config user.email`).
- Check the tracked remote: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false rev-parse --abbrev-ref --symbolic-full-name @{u}`.
  Resolve owner metadata through `gh repo view`; never print credential-bearing remote URLs.
- A branch tracking another person's fork is `other`.
- Check commit authors: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD`.
  Commits by someone else make it `other`.
- Only uncommitted changes or commits and branches owned by the current user are `self`. Unverifiable is `unknown`.

## Write scope

- `self`: fix supported findings in the same pass when the user asked for a review of their own work or for fixes.
  Find and fix are one pass.
- `other` or `unknown`: draft comments and suggestions only; keep code unchanged.
  Edit only when the user explicitly says so ("fix these", "take over this branch").
- A reviewer subagent is read-only regardless of authorship; it reports findings and never edits.

Write scope on a file never grants commit, push, reply, resolve, or publication authority; those need their own explicit request.
