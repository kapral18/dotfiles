# Authorship Resolution

Resolve `authorship` before selecting a mode. This file is loaded once by the router; mode files reuse it.

Allowed values:

- `self`
- `other`
- `unknown`

Exception: plan review mode has no code target. Record `authorship: n/a`, skip the git/`gh` probes below, and produce feedback only.

This input feeds write scope (below); it is not edit authority by itself. Resolve it in the local/branch path too.
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
  - Resolve repository/owner metadata through `gh repo view`; never print credential-bearing remote URLs.
- A branch tracking another person's fork is `other` (e.g. `someoneelse/<branch>`).
- Check authorship of the commits under review: `GIT_OPTIONAL_LOCKS=0 git -c core.fsmonitor=false log --format='%an <%ae>' <base>..HEAD`.
  Commits authored by someone other than the current user make it `other`.
- Only uncommitted/staged working-tree changes, or commits/branch owned by the current user, resolve to `self`.
  If it cannot be verified, it is `unknown`.

Authorship is one input to write scope, not the gate itself. Resolve write scope from authorship plus packet category:

- **`self`, executing inline as root (not inside a review/research/audit-category packet):**
  - the root's default packet already holds full local write scope; a finding is fixed in the same pass, no separate authorization step —
    find and fix are one pass, not two
  - draft review comments only if the user plans to post self-review notes; posting itself stays under SOP §3.8
- **`self`, executing inside a review/research/audit-category final-Verify packet** (e.g. `k-deep-review`, a final adversarial/criteria/findings-audit packet): read-only by its own category, independent of authorship — report findings; the root applies SOP §3.5 to any repair when existing authority covers it
- **`self`, executing as a child whose packet already grants write/implement scope over this path** (the flow's point is to make the change, or the packet declares disjoint ownership of this file per SOP §3.7): fix in the same pass and return the diff; the packet already answered the write-scope question when it was assigned, so no separate re-ask is needed
- **`self`, executing as a child whose packet does not grant write scope over this path** (unscoped exploration, a review/research-category packet, or ownership not provably disjoint from a sibling's): report findings to the orchestrator; the orchestrator holds write scope and sequences the fix
- **`other` / `unknown`:**
  - produce draft comments/suggestions only; keep code unchanged
  - the artifact is not yours to write regardless of packet category — no packet can grant scope over someone else's branch;
    editing requires the user to explicitly say to fix it (e.g. "fix these" or "take over this branch")

Known fixes belong to Produce before final Verify whenever write scope covers them;
a final-Verify-stage packet never gains fix authority from its own findings regardless of authorship —
that packet's category is read-only by design.
NEVER infer commit, push, or publication authority from write scope on a file; those stay separately gated per SOP §3.2/§3.8.
