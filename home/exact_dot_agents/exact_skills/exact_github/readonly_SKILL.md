---
name: github
description: "Use when the user wants a GitHub side effect via gh/API or provides a gist URL: PRs, issues, comments, reviews, labels, releases, merges, or gists."
---

# GitHub + gh Skill

Use when:

- the user explicitly wants a GitHub side effect via `gh` or GitHub APIs
- the user wants to create/edit/post/apply/merge something on GitHub, not just draft text
- the user provides a GitHub gist URL (`gist.github.com/...` or `gist.githubusercontent.com/...`) or asks to create/update/list a gist

Defaults & constraints:

- Use `gh` CLI for GitHub activity.
- Follow repository merge settings (squash/rebase/merge); do not enforce a merge strategy.
- Never merge into the base branch via CLI; merges happen via the GitHub UI.
- For non-interactive reliability, set `GH_PAGER=cat` for all `gh` calls.
- GitHub gists: use `gh gist` (or `gh api`) for all gist interactions; do not fetch gist URLs directly (HTML wrappers, auth/rate limits, non-canonical).

PR targeting (avoid searching):

- If the user uses implicit-current phrasing ("this PR", "current PR", "PR for this branch") and does not specify a PR URL/number, resolve the PR for the current branch in the current repo.
- Resolve the PR number/URL with:
  - `,gh-prw --number`
  - `,gh-prw --url`
- If `,gh-prw` fails once, stop and ask for the PR URL (or use `-R OWNER/REPO` if the user clearly intends a different repo).
- Do not assume an unspecified GitHub task targets the current branch PR unless the wording clearly implies the current PR.

Issue targeting:

- If the user refers to the current issue implicitly ("this issue", "current issue"), resolve the issue number first:
  - `,gh-issuew --number`
  - `,gh-issuew --url`
- If `,gh-issuew` fails once, stop and ask for the issue URL.

Do not use:

- The user wants to draft PR/issue text only (draft-only): use the compose skills.
  - PR: `~/.agents/skills/compose-pr/SKILL.md`
  - Issue: `~/.agents/skills/compose-issue/SKILL.md`
- The user wants PR review feedback, PR-fix verification, thread-by-thread handling, or review-comment drafting:
  - Use: `~/.agents/skills/review/SKILL.md`
  - It routes between local vs PR review, and PR modes (start/iterative/replies).
- The user wants local git operations (status/diff/commit/rebase): `~/.agents/skills/git/SKILL.md`.
- The user wants worktree management (create/switch/remove worktrees): `~/.agents/skills/worktrees/SKILL.md`.

Terminology:

- A domain overlay is a repo/org-specific skill selected from the verified target repo/org, not guessed from wording.
  It layers repo-specific policy onto this generic GitHub mechanics skill.
- Current concrete overlay: for the `elastic` org / `elastic/kibana`, load `~/.agents/skills/elastic-domain/SKILL.md`.

First actions:

1. Set `GH_PAGER=cat`.
2. Resolve the exact target repo/object (PR, issue, comment thread, release) before mutating anything.
3. For context-dependent actions — PR/issue creation, PR/issue body/title edits, replies/resolves, labels inferred from content, or follow-ups — run the GitHub Context Intake + Reference Resolution gate in `~/.agents/skills/review/references/pr_common.md` before composing or mutating.
   PR creation is a composition action; it is not exempt.
   Fully specified mechanical actions, such as applying an explicitly named label, are exempt.
4. If the context is contested, historically unclear, or depends on product/team precedent, also run Ambient Topic Exploration in `~/.agents/skills/review/references/pr_common.md`.
5. If the user also needs authored text, reviewer reasoning, labels, ownership guidance, or repo-specific GitHub metadata, invoke the required secondary skill(s) or domain overlay first and use their output before posting/applying.
6. Before creating or editing public PR/issue text, sanitize the body/title for portable public context:
   - remove session-specific hosts, ports, workspace paths, temp paths, browser automation session references, and local usernames
   - replace local-only validation details with reproducible setup/check steps another maintainer can run
   - if a local URL is needed, prefer `http://localhost:<port>` or a placeholder over private/non-standard hostnames

Approvals:

- Any GitHub side effect requires explicit approval unless the user instructed otherwise.
  Examples (non-exhaustive): create/edit PRs or issues, post comments/reviews, apply metadata (labels/assignees/milestones/projects), merge, or create releases.
- Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.
  If the user did not provide the exact title/body/labels, draft the complete payload, show it with the target repo/base/head, and get approval before `gh pr create`.
- Before relying on a known-bot allowlist, verify and load any applicable domain overlay for the target repo.
  Without a verified overlay, classify bots only from platform evidence such as GitHub `user.type == "Bot"` or a login ending in `[bot]`.
- Human-Visible Publication Gate (see the SOP, `~/AGENTS.md`): a reply/resolve/comment that a human will see is always supervised —
  draft, show the exact payload + target, wait for approval.
  The only carve-out is a **verified bot-authored** thread (GitHub `user.type == "Bot"`, login ending in `[bot]`, or known-bot allowlist from the verified overlay), which may be auto-replied/auto-resolved inside an explicitly-invoked flow.
  Ambiguous or mixed human+bot threads fail safe to human (supervised). Verify author type via the API before treating any thread as bot:
  - `gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID --jq '{login:.user.login, type:.user.type}'`
- Wording for any human-visible content (PR/issue bodies, comments, replies, review summaries, release notes —
  tone, concision, addressed-vs-not-addressed triage): follow the centralized `~/.agents/skills/communication/SKILL.md`.
  This skill carries GitHub mechanics only (endpoints, `in_reply_to`, anchoring, clickable source/commit links).

PR review side effects (draft / pending reviews):

> **CRITICAL:** never include `event` in a create-review payload unless the user explicitly asked to publish.
> `POST /reviews` without `event` is the only safe way to create a `PENDING` (draft) review;
> adding `event` immediately and irreversibly publishes it to the PR author and subscribers.

- Before any create/delete-recreate/submit action, read existing current-account pending reviews and reconcile them with the new payload;
  do not create or submit fragmented review feedback.
- Full mechanics — pre-flight checklist, pending-review definition/constraints, the existing-pending-review merge guard, the batch draft-posting procedure (including `position` math), and post-submit verification — live in `~/.agents/skills/github/references/pr-reviews.md`.

Posting PR review comments:

- Use bash/zsh `$'...'` so `\n` becomes real line breaks. Do NOT send literal `\n`.
- Commit references in comment bodies must be clickable links (full GitHub URL), never bare or backtick-wrapped hashes.
- Follow the relevant PR review mode for anchoring and comment placement: `~/.agents/skills/review/references/pr_review.md` or `~/.agents/skills/review/references/pr_fix.md`.
- Inline/range, file-level, reply, and PR-timeline comment examples live in `~/.agents/skills/github/references/pr-comments.md`.

PR creation:

- Create PRs as draft by default.
- Always ask which existing issue the PR should reference (do not invent issue numbers).
- Ask the user whether the PR should `Closes #X` or `Addresses #X` before creating the PR.
- If there is no existing issue, stop and ask whether to create one; do NOT create issues unless the user explicitly instructs you to.
- PR title is a human-readable change summary (not necessarily the Conventional Commit header).
- Multiline bodies/comments: use bash/zsh `$'...'` so `\n` becomes real newlines.
  Do NOT rely on `\\n` escapes inside normal quotes when using `gh api -f body=...`.
- Test plan is inferred from the change surface; run the smallest sufficient set of checks and record the commands/results in the PR.
- For repro-driven fixes, the PR test plan must include portable local repro steps in addition to commands/results;
  do not publish only session-specific evidence such as private local hostnames or browser automation state.
- Before creating/editing a PR body, ensure the Test Plan covers any `## Reproduction`, `Expected`, or `Actual` evidence from linked/closing issues.
  If manual repro was not run, include portable reviewer-run verification steps and say which automated checks were run.
- Always propose labels/assignees/milestone/projects first and get explicit confirmation before applying any of them.
- Before `gh pr create` or any PR body/title edit, show a PR publication preflight ledger:
  - `target`: repo, base, head, draft/readiness
  - `title`: exact title plus source/rationale
  - `body`: body file/path or full text source, linked issue keyword, and footer state
  - `intake`: full linked issue/PR/comment bodies read; comments/replies status; skipped items with reasons
  - `test_plan`: observable/manual steps, expected result, commands run, and observed results
  - `metadata`: proposed labels/assignees/milestone/projects plus source skill/rationale
  - `approval`: exact side effect command/payload approved by the user
- After `gh pr create` or `gh pr edit`, read back title, body, labels, draft state, base/head, and closing keyword.
  Compare each field against the approved preflight ledger; if any field differs, do not mark the task complete until the mismatch is fixed or explicitly accepted.

Composition (draft-only) guidance:

- Before creating/editing a PR body, invoke the `compose-pr` skill via the Skill tool.
- Before creating/editing an issue body, invoke the `compose-issue` skill via the Skill tool.
- For repo-specific labels, ownership, reviewer targeting, or PR body rules, load the verified domain overlay first.
  For Elastic/Kibana, load `~/.agents/skills/elastic-domain/SKILL.md`.

Output:

- Before each side effect, restate the exact target and action you are about to perform.
- After each side effect, verify via read-back (`gh`/API) and report the URL, identifier, or resulting state.

Do not add/modify repo `.github/*` templates unless the user explicitly asks.

Sub-issues API:

GitHub's sub-issue API creates real parent-child relationships (not tasklists).
Full create/link/verify procedure: `~/.agents/skills/github/references/sub-issues.md`.
