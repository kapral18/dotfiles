---
name: k-github
description: "Use for GitHub effects: PRs, issues, comments, reviews, labels, releases, merges, gists, attachments."
---

# GitHub + gh Skill

Defaults:

- Use `gh` CLI; set `GH_PAGER=cat` for non-interactive reliability.
- Follow repo merge settings; never merge into the base branch via CLI.
- Gists use `gh gist` or `gh api`; do not fetch gist URLs directly.
- Attachment uploads (local images/videos/files -> `user-attachments`) are impossible via REST/GraphQL;
  use `~/.agents/skills/k-github/references/attachments.md`.

## Targeting

- Implicit current PR (“this PR”, “current PR”, “PR for this branch”): resolve with `,gh-prw --number` / `,gh-prw --url`;
  if it fails once, ask for URL. Do not assume current-branch PR unless wording clearly implies it.
- Implicit current issue: resolve with `,gh-issuew --number` / `,gh-issuew --url`; if it fails once, ask for URL.

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
3. If context is contested, historical, or precedent-dependent, also run Ambient Topic Exploration from the same reference.
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

- Never include `event` in create-review payloads unless the user explicitly asked to publish;
  `POST /reviews` without `event` creates a pending draft.
- Before create/delete-recreate/submit, reconcile current-account pending reviews with the new payload; do not fragment feedback.
- UI-related review feedback needs screenshot handoff evidence outside the body, or a valid blocker/non-applicability reason.
- Full mechanics live in `~/.agents/skills/k-github/references/pr-reviews.md`.

## PR review comments

- Use bash/zsh `$'...'` so `\n` becomes real line breaks; never send literal `\n`.
- Commit references must be clickable full GitHub URLs.
- UI-related comments/replies/PR-level feedback need screenshot handoff evidence outside the body; never include local screenshot paths.
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
- Do not add/modify repo `.github/*` templates unless explicitly asked.
- Sub-issues API creates real parent-child relationships; use `~/.agents/skills/k-github/references/sub-issues.md`.
