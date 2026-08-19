---
name: k-github
description: "Use for GitHub effects: PRs, issues, comments, reviews, labels, releases, merges, gists, attachments."
---

# GitHub + gh Skill

Defaults:

- Use `gh` CLI; set `GH_PAGER=cat` for non-interactive reliability.
- Follow repo merge settings; merge into the base branch only via the GitHub UI, never via CLI.
- Gists use `gh gist` or `gh api`, replacing direct gist URL fetches.
- Attachment uploads (local images/videos/files -> `user-attachments`) are impossible via REST/GraphQL;
  use `~/.agents/skills/k-github/references/attachments.md`.

## Targeting

- Implicit current PR (“this PR”, “current PR”, “PR for this branch”): resolve with `,gh-prw --number` / `,gh-prw --url`.
  Assume current-branch PR only when wording clearly implies it.
  `,gh-prw` already probes the current branch + commit SHA fallback, so a number literal that returns "could not resolve" is a hint that the number is wrong, not a signal that the helper is broken.
- If the user names a number that `,gh-prw` cannot resolve: reroute before writing prose about it.
  Fallback chain (each step is read-only and cheap):
  1. `,gh-prw --number <n>` — handles the typical case (number, branch, commit SHA).
  2. `gh pr view --repo <upstream-fork-owner>/<repo> <n>` — for branches that target a different fork than the authenticated `gh` account (verified via `gh auth status`, not assumed from `git config`).
  3. `gh pr view` (no args) — relies on the branch's tracked remote, regardless of authenticated `gh` account.
  4. `gh pr view --head <branch>` — covers branches that exist on a fork but lack a default-remote config.
  5. `gh issue view <n> --repo <owner>/<repo>` — covers the common case where a number is an issue, not a PR.
     Three rounds of guessing "this number is the PR" without trying any of those is the failure mode.
- Implicit current issue: resolve with `,gh-issuew --number` / `,gh-issuew --url`; same fallback applies if the helper fails.

## Route away

- Draft-only PR/issue text: `k-compose-pr` / `k-compose-issue`.
- PR review feedback, PR-fix verification, thread handling, review-comment drafting: `k-review`.
- Local git operations: `k-git`.
- Worktree management: `k-worktrees`.

## Domain overlays

A domain overlay is selected from verified repo/org evidence, not guessed from wording.
For `elastic` / `elastic/kibana`, load `~/.agents/skills/k-elastic-domain/SKILL.md`.

## First actions

1. Resolve exact target repo/object (PR, issue, comment thread, release) before mutating anything.
2. For context-dependent actions — PR/issue creation, body/title edits, replies/resolves, inferred labels, or follow-ups —
   run GitHub Context Intake + Reference Resolution in `~/.agents/skills/k-review/references/pr_common.md` before composing or mutating.
   PR creation is a composition action; it is not exempt.
   Fully specified mechanical actions, such as applying an explicitly named label, are exempt.
3. If context is contested, historical, or precedent-dependent, also run Ambient Topic Exploration from `~/.agents/skills/k-review/references/pr_context_audits.md`.
4. If authored text, review reasoning, labels, ownership, or repo-specific metadata are needed, invoke the required secondary skill/overlay before posting/applying.
5. Before public PR/issue text changes, sanitize session-specific hosts, ports, workspace/temp paths, browser sessions, and local usernames;
   replace local-only validation with reproducible steps.

## Approvals

- Any GitHub side effect needs explicit approval unless the user instructed otherwise:
  create/edit PRs/issues, comments/reviews, metadata, merge, release, uploads.
- Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.
  If title/body/labels were not provided, draft the full payload, show target repo/base/head, and get approval before `gh pr create`.
- Before using a known-bot allowlist, verify/load the domain overlay; otherwise classify bots only from GitHub `user.type == "Bot"` or login ending `[bot]`.
- Human-visible replies/resolves/comments are supervised: draft, show exact payload + target, wait for approval.
  Only verified bot-authored threads may be auto-replied/auto-resolved inside an explicitly invoked flow;
  ambiguous/mixed threads fail safe to human.
  Verify author type via API, e.g. `gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID --jq '{login:.user.login, type:.user.type}'`.
- Human-visible wording (PR/issue bodies, comments, replies, review summaries, release notes) follows `~/.agents/skills/k-communication/SKILL.md`; this skill owns mechanics only.

## PR review side effects

- Create-review payloads must omit `event`; `POST /reviews` without `event` creates a pending draft.
  Publish only via a separate submit call after explicit approval.
- Before create/append/delete-recreate/submit, reconcile current-account pending reviews with the new payload so feedback stays consolidated.
  Append net-new comments to an existing pending review; delete/recreate only to change or drop existing ones.
- UI-related review feedback needs screenshot handoff evidence outside the body, or a valid blocker/non-applicability reason.
- Full mechanics live in `~/.agents/skills/k-github/references/pr-reviews.md`.

## PR review comments

- Use bash/zsh `$'...'` so `\n` becomes real line breaks; send only real line breaks, with literal `\n` excluded.
- Commit references must be clickable full GitHub URLs.
- UI-related comments/replies/PR-level feedback need screenshot handoff evidence outside the body; keep local screenshot paths out of it.
- Follow `~/.agents/skills/k-review/references/pr_review.md` or `pr_fix.md` for anchoring/placement.
- Comment examples live in `~/.agents/skills/k-github/references/pr-comments.md`.

## PR creation/body edits

- Load `~/.agents/skills/k-github/references/pr-create.md` before `gh pr create` or any PR body/title edit.
- It owns draft default, issue linkage, `k-compose-pr` publication packet, screenshot/metadata gates, preflight ledger, and readback comparison.

## Issue creation/body edits

- Load `~/.agents/skills/k-github/references/issue-create.md` before `gh issue create` or any issue body/title edit.
- It owns `k-compose-issue` publication packet, issue type gate, preflight ledger, relationship mutations, and readback comparison.

## Composition guidance

- Before PR body edits, invoke `k-compose-pr`; before issue body edits, invoke `k-compose-issue`.
- For repo-specific labels, ownership, reviewer targeting, or PR body rules, load the verified domain overlay first.

## Output

- Before each side effect, restate exact target and action.
- After each side effect, verify via read-back (`gh`/API) and report URL, identifier, or resulting state.
- Add/modify repo `.github/*` templates only when explicitly asked.
- Sub-issues API creates real parent-child relationships; use `~/.agents/skills/k-github/references/sub-issues.md`.
