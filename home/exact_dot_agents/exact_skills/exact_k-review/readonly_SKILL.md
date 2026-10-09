---
name: k-review
description: "Use to review local changes, a PR, review threads (PR fixes), or a plan, and for an independent capped verify pass (two fresh reviewers, then a bounded fix loop)."
---

# Review

Pick one mode, review inline, and report anchored findings.
Load `~/.agents/skills/k-review/references/authorship.md` once before any mode; it decides whether you may edit.

## Modes

Pick exactly one. If intent stays ambiguous after the checks in Disambiguation, ask one question and state a default.

| Mode          | Use when                                                        | Open                                                    |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| Local changes | working tree, branch delta, or commit range with no PR in scope | `~/.agents/skills/k-review/references/local_changes.md` |
| PR review     | initial or continued PR review, or "does this PR fix it"        | `~/.agents/skills/k-review/references/pr_review.md`     |
| PR fix        | address reviewer comments, reply to or resolve threads          | `~/.agents/skills/k-review/references/pr_fix.md`        |
| Plan review   | a plan, design doc, RFC, issue body, or pasted text             | `~/.agents/skills/k-review/references/plan_review.md`   |

A review that `~/AGENTS.md` §3 step 5 requires always uses Verify mode.
Otherwise, a small, self-authored, local-only change with no risk trigger goes to `k-light-review` unless the user asked for a full review.
Risk triggers: PR context, security/auth/crypto, persisted data, public API, deletion or replacement, stateful/parser/workflow behavior, or a needed base/runtime investigation.

If the conversation is already in a mode, "continue" or "next" stays in it.

## PR detection

When the user mentions or implies a PR:

1. Run `gh auth status` once.
2. `,gh-prw --number` gives the current branch's PR; `,gh-prw --number <n|url|branch|sha>` resolves a specific one.
3. If that fails, use the `k-github` Targeting fallbacks: `gh pr view [--repo OWNER/REPO] <n>`, `gh pr view`, `gh pr view <branch> --repo <owner>/<repo>`, `gh issue view <n>`.
4. Ask for the URL or number only after these fail.

Never review someone else's draft PR unless the user explicitly asks. Say: "This PR is a draft — skipping review unless you explicitly ask."
An explicitly requested draft review uses the same depth as a ready PR.

## Disambiguation

- A document, issue body, or pasted text: plan review.
- Outside a git repo: ask whether this is a PR (URL/number), local changes, or a plan.
- Inside a git repo, run `git status --porcelain=v1 -b` and `,gh-prw --number`:
  - local changes exist (with or without a PR): local changes mode; mention the PR so the user can switch.
  - only a PR: PR review.
  - neither: local changes mode on the branch delta.

## How to review (every mode)

- Read full changed files plus their callers and consumers, never hunks alone.
  Compare with base: `~/.agents/skills/k-review/references/shared_rules.md` Base-Branch Context Gate.
- Judge with `~/.agents/skills/k-review/references/judging_core.md`.
  Load the extra lens files only when `judging_core.md` names their trigger.
- Also check hygiene: redundancy (name both locations), verbosity with real reading cost, the same contract expressed inconsistently, and gaps (missing consumers, docs, generated outputs, tests).
- Reuse checks already run on this snapshot; do not rerun them. Run a check only when a finding depends on it.
- Treat every finding as a hypothesis until a source read, repro, or failing check supports it. Drop unsupported findings.
  Keep a material unverified one as `verification_needed` with the missing observation.
- Merge findings with the same cause. Do not invent cleanup findings outside the change.

Each finding: `[critical|high|medium|low] file:line — trigger → consequence — evidence — smallest fix`.

## Reviewer launch

Use this procedure for both full reviews and fix-diff reviews:

- Claude Code, Pi, OMP: launch the `k-agent-reviewer` profile.
- Codex: read `~/.agents/skills/k-review/references/reviewer_prompt.md`.
  Call native `spawn_agent` with `fork_turns: "none"` for each reviewer; its default copies the author's conversation.
  Put the shared reviewer prompt and review packet in `message`. Keep the parent's model and reasoning effort.
- Without a reviewer profile or fresh native agent support, review inline once and report the lack of independent review.

## Verify mode (independent review, bounded fix loop)

Use when `~/AGENTS.md` §3 step 5 requires a review of a finished change, or when the user asks for an independent, fresh, or second-opinion review, or to verify or de-slop a change.

1. Fix the scope. For a §3 step 5 review, use the task-start working-tree state, not only its starting commit.
   Exclude pre-existing hunks and untracked files unless the user included them.
   Use saved originals or edit records to separate them; do not guess.
   Include the task's behavior-map entry ids (`,behavior-map show <id>`) and memory writes. Otherwise, review the change the user named.
   Add the user's request in their words, the intent in one line, the checks already run with their results, and your `Assumptions:`.
2. Launch two fresh reviewers in parallel using Reviewer launch above.
   Pass both only the same scope, request, intent, check results, assumptions, and known gaps.
3. Merge the findings. Check each finding against source yourself. Reject unsupported ones with a one-line reason.
4. Apply supported findings within write scope using `~/.agents/skills/k-review/references/review_fixes.md`.
   Its bounded Verify procedure owns scratch copies, checks, fix-diff reviews, and stopping rules.
5. Report the review scope, fixed findings with evidence, rejected findings with reasons, and remaining `Open:` or `Known gaps:`.

NEVER start a second full review (two reviewers on the whole change) on your own; the fix loop reviews only fix diffs.
Another full round needs the user to ask for it.

## Posting

Review is read-only toward GitHub.
Before drafting public-ready comments or a verdict, load `~/.agents/skills/k-review/references/review_delivery.md`.
Post only when the user asks, through the `k-github` skill, under `~/AGENTS.md` §5 approval rules.

Load `k-github` earlier only for read-only targeting and context intake. Load `k-buildkite` only when a CI job's contents matter.
Label, release-note, and version classification run only when the user asks for labels or a PR body.
