---
name: k-review
description: "Use to review local changes, a PR, review threads (PR fixes), or a plan, and for independent verify rounds (two fresh reviewers and a fix loop, repeated until a whole-scope round is clean)."
---

# Review

Pick one mode, review inline, and report anchored findings.
Load `~/.agents/skills/k-review/references/authorship.md` once before any mode; it decides whether you may edit.

## Modes

Pick exactly one. If intent stays ambiguous after the checks in Disambiguation, pick the likeliest mode and say which.

| Mode          | Use when                                                        | Open                                                    |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| Local changes | working tree, branch delta, or commit range with no PR in scope | `~/.agents/skills/k-review/references/local_changes.md` |
| PR review     | initial or continued PR review, or "does this PR fix it"        | `~/.agents/skills/k-review/references/pr_review.md`     |
| PR fix        | address reviewer comments, reply to or resolve threads          | `~/.agents/skills/k-review/references/pr_fix.md`        |
| Plan review   | a plan, design doc, RFC, issue body, or pasted text             | `~/.agents/skills/k-review/references/plan_review.md`   |

A review that `~/AGENTS.md` §3 step 5 requires always uses Verify mode.
Otherwise, a small, self-authored, local-only change with no risk trigger goes to `k-light-review` unless the user asked for a full review.
Risk triggers: PR context, a change on the `~/AGENTS.md` §3 step 5 list, deletion or replacement, stateful or workflow behavior,
or a needed base/runtime investigation.

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
- Outside a git repo with no PR named: plan review of what the user gave you.
- Inside a git repo, run `git status --porcelain=v1 -b` and `,gh-prw --number`:
  - local changes exist (with or without a PR): local changes mode; mention the PR so the user can switch.
  - only a PR: PR review.
  - neither: local changes mode on the branch delta.

## How to review (every mode)

- Read full changed files plus their callers and consumers, never hunks alone.
  Compare with base: `~/.agents/skills/k-review/references/shared_rules.md` Base-Branch Context Gate.
- Judge with `~/.agents/skills/k-review/references/judging_core.md`.
  Load the extra lens files only when `judging_core.md` names their trigger.
- De-slop the change: load `~/.agents/skills/k-code-quality/SKILL.md` and apply its De-slop section; for duplication, name both locations.
- Also check for one contract expressed inconsistently in two places, and for gaps (missing consumers, docs, generated outputs, tests).
- Reuse checks already run on this snapshot; do not rerun them. Run a check only when a finding depends on it.
- Treat every finding as a hypothesis until a source read, repro, or failing check supports it. Drop unsupported findings.
  Keep a material unverified one as `verification_needed` with the missing observation.
- Merge findings with the same cause.
  Do not invent cleanup findings outside the change; for a change you may edit, also report defects in its impact (`~/AGENTS.md` §3 step 1),
  collecting its impact list with `k-behavior-map` (before a change) when none exists.

Each finding: `[critical|high|medium|low] file:line — trigger → consequence — evidence — smallest fix`.

## Reviewer launch

Use this procedure for both full reviews and fix-diff reviews:

- Claude Code: launch the `k-agent-reviewer` profile with `run_in_background: false`.
  Put a round's reviewer calls in one message: they run in parallel, and the turn waits for their results.
- Pi, OMP: launch the `k-agent-reviewer` profile.
- Codex: read `~/.agents/skills/k-review/references/reviewer_prompt.md`.
  Call native `spawn_agent` with `fork_turns: "none"` for each reviewer; its default copies the author's conversation.
  Put the shared reviewer prompt and review packet in `message`. Keep the parent's model and reasoning effort.
- Without a reviewer profile or fresh native agent support, review inline once and report the lack of independent review.

## Verify mode (independent review rounds, fix loop until clean)

Use when `~/AGENTS.md` §3 step 5 requires a review of a finished change, or when the user asks for an independent, fresh, or second-opinion review, or to verify or de-slop a change.

1. Fix the scope. For a §3 step 5 review, use the task-start working-tree state, not only its starting commit.
   After `continue <topic>`, take it from the handoff note's State; if the note lacks it, use this session's start and say so.
   For a §3 step 5 review of a later change in the same task, review only the diff against the baseline the last Verify review saved.
   For a file missing from the baseline, diff against its task-start original, unless the baseline's `.k-review-deleted.txt` lists it and it is still absent.
   If the baseline is gone (deleted, or lost to a reboot), review the whole task change from its starting commit and say so.
   Exclude pre-existing hunks and untracked files unless the user included them.
   Use saved originals or edit records to separate them; do not guess.
   Include the task's behavior-map entry ids (`,behavior-map show <id>`) and memory writes. Otherwise, review the change the user named.
   For a change within write scope (`authorship.md`), include the change's impact as `~/AGENTS.md` §3 step 1 defines it.
   Add the user's request in their words, the intent in one line, the checks already run with their results, and your `Assumptions:`.
2. Launch two fresh reviewers in parallel using Reviewer launch above.
   Pass both only the same scope, change's impact (if any; a narrowed round gets none), request, intent, check results, assumptions, and `Open:` items;
   a later full round, or a verify-again run, also gets every finding fixed, rejected, or proposed so far.
   Tell the reviewers of a narrowed later round (`review_fixes.md` step 7) that it is narrowed and which files it covers.
3. Merge the findings. Check each finding against source yourself. Reject unsupported ones with a one-line reason.
4. Apply supported findings within write scope using `~/.agents/skills/k-review/references/review_fixes.md`.
   Its Fix procedure (the Verify-mode steps) owns scratch copies, checks, fix-diff reviews, further full rounds, and stopping rules.
5. Copy every file in the reviewed scope, as it stands after the fixes, into the baseline, even when nothing was fixed:
   a fresh scratch directory for the task's first Verify review, the existing baseline after that.
   For a file with a fix marked "(unreviewed)", copy that round's pre-fix copy instead, so the next review still covers the fix.
   List each reviewed path the task deleted in the baseline's `.k-review-deleted.txt`.
   That copy is the baseline for a later §3 step 5 review in the same task. Keep it until the task ends; `k-cleanup` does not delete it.
   A handoff note records its path.
6. Report the review scope, fixed findings with evidence, rejected findings with reasons, `Open:` items with their blockers, `Proposed:` items (`~/AGENTS.md` §3 step 8), and the rounds trend (`review_fixes.md` step 8).

Run full rounds without asking until `review_fixes.md` says to stop.

## Posting

Review is read-only toward GitHub.
Before drafting public-ready comments or a verdict, load `~/.agents/skills/k-review/references/review_delivery.md`.
Post only when the user asks, through the `k-github` skill, under `~/AGENTS.md` §5 approval rules.

Load `k-github` earlier only for read-only targeting and context intake.
Label, release-note, and version classification run only when the user asks for labels or a PR body.
