---
name: k-github
description: "Use for GitHub effects and GitHub issue context/targeting: PRs, issues, comments, reviews, labels, releases, merges, gists, attachments."
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
  4. `gh pr view <branch> --repo <owner>/<repo>` — use the verified target repository when the branch is on a fork without a default-remote config.
  5. `gh issue view <n> --repo <owner>/<repo>` — covers the common case where a number is an issue, not a PR.
     Three rounds of guessing "this number is the PR" without trying any of those is the failure mode.
- Implicit current issue: resolve with `,gh-issuew --number` / `,gh-issuew --url`; same fallback applies if the helper fails.
  Verify the association from repository and object metadata; NEVER treat a branch number alone as the issue identity.

## GitHub Context Intake + Reference Resolution

Use this read-only intake during Understand for applicable issue diagnosis, implementation, or review work.
It does not require a PR or review workflow, and intake-only use MUST NOT start PR resolution, pending-review handling, mutation, or unrelated reference workflows.

Read complete primary discussion before relying on it: an issue's full body and comments;
a PR's full body, review threads and replies, current-account pending drafts, and diff metadata through the existing `~/.agents/skills/k-review/references/pr_snapshot.md` pack.
Do not rely on summaries, previews, truncated/compacted output, or sliced fields such as `body[0:N]`.
Retrieve complete raw artifacts with pagination before relying on them, and reuse an already-complete pack or artifact instead of refetching it.
Reading discussion establishes intent and claims; it does not prove technical claims.

Follow a reference only when it can settle a named material question about intent, changed behavior, a claimed precedent, or an acceptance condition.
Record that question before following further links. The presence of a URL is not an instruction to fetch it.
Do not recursively crawl every reachable or potentially relevant reference.

- Keep a visited set by canonical URL/object ID and reuse each complete artifact.
- For a selected issue/PR, read its full body and discussion before relying on it;
  inspect its diff/files only when the claim depends on code.
- For a selected comment/thread, read the complete thread with author, order, resolution, and outdated state.
- For selected media, use `~/.agents/skills/k-review/references/pr_snapshot.md` → Media, inspect the actual file, and retain the manifest evidence.
  For video/GIF claims, inspect the relevant transition plus surrounding states and audio/captions when material.
- For selected Buildkite evidence, use `k-buildkite`; verified overlays own repo-specific routing.
- If a claim depends on visuals and visuals are missing, inaccessible, or unclear, stop and ask for visuals or better access before making that claim.
- Stop reference expansion when the named question is answered or the required source is inaccessible.
  Do not create new questions solely from incidental links. Report material unresolved questions as blocked.

Keep the intake ledger in the existing topic artifact: question, source, complete-content status, conclusion or access blocker.
User output contains only decision-relevant conclusions and evidence pointers, not a crawl transcript.

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
   run this skill's GitHub Context Intake + Reference Resolution before composing or mutating.
   PR creation is a composition action; it is not exempt.
   Fully specified mechanical actions, such as applying an explicitly named label, are exempt.
3. If context is contested, historical, or precedent-dependent, also run Ambient Topic Exploration from `~/.agents/skills/k-review/references/pr_context_audits.md`.
4. If authored text, review reasoning, labels, ownership, or repo-specific metadata are needed, invoke the required secondary skill/overlay before posting/applying.
5. Before public PR/issue text changes, sanitize session-specific hosts, ports, workspace/temp paths, browser sessions, and local usernames;
   replace local-only validation with reproducible steps.

## Approvals

- Any GitHub side effect needs explicit approval unless the user instructed otherwise:
  create/edit PRs/issues, comments/reviews, metadata, merge, release, uploads.
- SOP §3.8 owns authorization persistence, conditional authorization, and its hard boundaries.
  Reuse existing authorization only within its target, scope, and allowed effects; NEVER broaden it to a new target or effect.
- A user-invoked `k-pr-fix-loop` approval packet is explicit approval for scoped PR body edits, needed PR media uploads, review-thread replies, and resolving addressed threads in that loop only.
- Existing PR body/title edits follow `~/.agents/skills/k-github/references/pr-create.md`;
  that packet decides whether the user's approval for the current PR workflow covers the edit or whether a draft must be surfaced first.
- Approval to "create a PR" authorizes the GitHub side effect, but not invented human-visible content.
  If title/body/labels were not provided, draft the full payload, show target repo/base/head, and get approval before `gh pr create`.
- Before using a known-bot allowlist, verify/load the domain overlay; otherwise classify bots only from GitHub `user.type == "Bot"` or login ending `[bot]`.
- Human-visible replies/resolves/comments are supervised: draft unapproved authored content, show exact payload + target, and wait only when SOP §3.8 authorization does not already cover it.
  Only verified bot-authored threads may be auto-replied/auto-resolved inside an explicitly invoked flow;
  ambiguous/mixed threads fail safe to human.
  Verify author type via API, e.g. `gh api repos/OWNER/REPO/pulls/comments/COMMENT_ID --jq '{login:.user.login, type:.user.type}'`.
- Human-visible wording (PR/issue bodies, comments, replies, review summaries, release notes) follows `~/.agents/skills/k-communication/SKILL.md`; this skill owns mechanics only.

## PR review side effects

- Never include `event` in create-review payloads; `POST /reviews` without `event` creates a pending draft.
  Publish only via a separate submit call after the applicable SOP §3.8 authorization.
- Before create/append/delete-recreate/submit, reconcile current-account pending reviews with the new payload; do not fragment feedback.
  Append net-new comments to an existing pending review; delete/recreate only to change or drop existing ones.
- UI-related review feedback needs screenshot handoff evidence outside the body, or a valid blocker/non-applicability reason.
- Full mechanics live in `~/.agents/skills/k-github/references/pr-reviews.md`.

## PR review comments

- Use bash/zsh `$'...'` so `\n` becomes real line breaks; never send literal `\n`.
- Commit references must be clickable full GitHub URLs.
- UI-related comments/replies/PR-level feedback need screenshot handoff evidence outside the body; never include local screenshot paths.
- Follow `~/.agents/skills/k-review/references/pr_review.md` or `~/.agents/skills/k-review/references/pr_fix.md` for anchoring/placement.
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
