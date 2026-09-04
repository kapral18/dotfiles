# Commit And Push Procedure

Push policy (mandatory):

- Interpret a user request to "push" as explicit approval for `git push --force-with-lease`.
- A user-invoked `k-pr-fix-loop` approval packet is an explicit force-with-lease push request for the current PR branch only.
- Prefer explicit remote/branch in the restated command (example: `git push --force-with-lease origin <branch>`).
- If upstream is missing, `git push --force-with-lease -u <remote> <branch>` is allowed.
- Never run `git pull`, `git pull --rebase`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` automatically before pushing.
- If push is rejected for divergence, non-fast-forward, lease failure, or diverged history, stop and ask how to proceed.
- Do not reconcile branch history unless the user explicitly asks for that exact action.

Amend policy (mandatory):

- when the user explicitly says "amend", use `git commit --amend`
- do not second-guess amend requests by inspecting the commit author; the git author field reflects git config, not whether the agent created the commit
- if the amended commit was already pushed, the subsequent push will need `--force-with-lease` (covered by push policy above)

Commit quality:

- use Conventional Commits when the repo already uses them; otherwise match the repo's existing commit style
- commit-message style does not transfer to PR titles.
  PR titles are owned by `k-github` plus any verified domain overlay, not by this commit-quality rule.
- infer `scope` from change surface (best effort)
- each commit must be minimal and atomic, independently reviewable
- commit body bullets are optional; include only when they add signal
- use only verified issue numbers
- put `Closes #X` / `Addresses #X` in the PR description for issue linking, keeping commit messages free of them
- if the repo uses semantic-release, leave version bumps to it unless the repo requires manual bumps

Repo/org-specific commit attribution:

- A domain overlay is a repo/org-specific skill selected from the verified repo/org, not guessed from wording.
  It layers repo-specific policy onto this generic git workflow skill.
- If the verified repo/org has an overlay, load that overlay before committing and apply its commit-attribution rules.
- For Elastic org repos, load `~/.agents/skills/k-elastic-domain/SKILL.md` and append the overlay's required `Co-authored-by` trailer with `git commit --trailer=...`.
