# Commit And Push Procedure

Approval scope (mandatory; `~/AGENTS.md` §5 points here):

- Once the user asks for a commit or push, later local git work in that repo for the rest of the task needs no further approval:
  commits, merges into the working branch, and rebases of commits that are not pushed.
  Without such a request, leave the change uncommitted. Unless the user names other changes, commit only this task's changes.
- Push only when the user asks for a push. That request covers later fast-forward pushes of the same branch for the rest of the task.
  A commit request alone never covers a push.
  A push that rewrites pushed history, merging a PR, and publishing each need their own request.
- A task is defined in `~/AGENTS.md` §5.

Push policy (mandatory):

- A push request approves plain `git push <remote> <branch>` for that branch, and later fast-forward pushes of it in the same task (Approval scope above).
  Use `--force-with-lease` only under a request that covers rewriting pushed history ("force push", "amend and push").
- A user-invoked `k-pr-fix-loop` approval packet approves only that batch's plain push of the current PR branch;
  it is not a standing push request and never a force push. If that push is rejected, stop and report.
- Prefer an explicit remote and branch (example: `git push origin <branch>`).
- If upstream is missing, `git push -u <remote> <branch>` is allowed.
- Do not run `git pull`, `git rebase <remote>/<branch>`, or `git merge <remote>/<branch>` of the branch you push before a first push attempt.
- If a plain push under a push request (not a `k-pr-fix-loop` packet) is rejected because someone else pushed to that branch:
  fetch, rebase only your unpushed commits onto the remote branch, rerun the affected checks, push without force, and report their commits.
  When your unpushed commits include a merge commit, run `git merge <remote>/<branch>` instead of a rebase.
  Stop and ask when the rebase or merge conflicts, or your own pushed commits are no longer on the remote branch.
- When a force-with-lease push is rejected, stop and ask.
- Merging the base branch into a PR branch (for example `upstream/main`) is local git work under the Approval scope above.
  Rebasing pushed commits rewrites pushed history and needs its own request.

Amend policy (mandatory):

- when the user explicitly says "amend", use `git commit --amend`
- do not second-guess amend requests by inspecting the commit author; the git author field reflects git config, not whether the agent created the commit
- if the amended commit was already pushed, pushing it rewrites pushed history:
  that push needs its own request, such as "amend and push" (Approval scope above)

Commit quality:

- commit subjects and bodies are human-visible: load `~/.agents/skills/k-communication/SKILL.md` before composing them
- keep agentic-session artifacts (SOP references, skill/agent/packet names, spec paths, `Compatibility impact:` lines) out of the message;
  an attribution trailer required by a verified domain overlay is the only agent-identifying content allowed
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
