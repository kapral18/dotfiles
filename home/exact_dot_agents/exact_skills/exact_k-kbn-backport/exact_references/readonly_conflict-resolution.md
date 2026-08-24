# Kibana Backport Conflict Resolution

Reference for the `k-kbn-backport` skill. Triggered only when the run pauses with a conflict on the current target branch.

The conflict state lives in the tool-owned checkout (`~/.backport/repositories/elastic/kibana`); run every command below there —
addressed explicitly with `git -C <checkout>` or from a shell `cd`'d into it, not from the controlling window.
Per pause, the order is: inspect → understand → resolve → stage → `yarn kbn bootstrap` → validate → send ENTER (to the controlling window's pane).
Do all of it in this checkout before handing back, then let the run advance to the next branch.

## Set up before editing

1. Follow the local `k-git` skill for git safety.
2. Identify the exact state in the checkout:
   - `git status --short --branch`
   - `git diff --name-only --diff-filter=U`
   - `git show --stat --oneline CHERRY_PICK_HEAD` when present
   - `git log -1 --oneline`
3. Inspect conflict context before editing:
   - `git diff --cc -- <conflicted-path>`
   - `git show CHERRY_PICK_HEAD -- <changed-paths>`
   - read the conflicted files and nearby destination-branch code
4. Check ownership before staging in `elastic/kibana`:
   - `,codeowners --owner-of <affected-path>` for every affected path
   - If any affected path is outside team ownership, stop and ask before the side effect.

## Understand The Original Change

Before resolving the conflict, investigate the commit/PR being backported so the resolution carries the same intent.
Do not resolve from the conflict hunks alone.

1. Identify the source change:
   - `git show CHERRY_PICK_HEAD` for the full original diff, message, and rationale.
   - Extract the originating PR number from the commit message (Kibana commits end with `(#NNNNN)`).
2. Read the original PR exhaustively — every reference, comment, and linked issue, all the way down.
   Do not skim the description and stop; build the complete context for why the change exists and what shape reviewers landed on.
   - Full PR body, metadata, and linked issues: `gh pr view <NNNNN> --repo elastic/kibana --json title,body,state,labels,closingIssuesReferences,comments,reviews,url`.
   - Every conversation comment: `gh pr view <NNNNN> --repo elastic/kibana --comments` (read all of them, not just the latest).
   - Every review and inline review-thread comment (these hold the design rationale):
     `gh api --paginate repos/elastic/kibana/pulls/<NNNNN>/reviews` and `gh api --paginate repos/elastic/kibana/pulls/<NNNNN>/comments`.
   - The complete intended change on its source branch: `gh pr diff <NNNNN> --repo elastic/kibana`.
   - Follow references transitively, to the last bit: for every linked/closing issue read the issue and all its comments (`gh issue view <n> --repo elastic/kibana --comments`), and for every other PR/issue referenced in the body, comments, or reviews, open and read it the same way.
     Continue until no new referenced PR/issue/discussion adds context.
   - Note what behavior the change adds/removes/fixes, every constraint or follow-up raised in review, and any decision that altered the change from its original form.

## Establish Destination-Branch Context

Especially when the original diff does not apply cleanly, learn how the affected areas work on the destination branch:

- Use the `k-semantic-code-search` skill (`~/.agents/skills/k-semantic-code-search/SKILL.md`) against the `kibana-repo` index to learn how the affected modules, symbols, and call sites work on the destination branch.
  Verify `kibana-repo` exists via `list_indices` first, then pass `index: kibana-repo` explicitly to the SCSI tools.
- Treat semantic results as base context only; validate the actual destination-branch state against local file reads and `git` on the backport checkout.
- If `kibana-repo` is missing from `list_indices` or SCSI is unavailable, fall back to local `rg`, file reads, and `git log`/`git blame` on the affected paths.

## Check For Missing Prerequisite Backports

A conflict is often caused not by the change itself but by an earlier PR that touched the same files and has not been backported to the destination branch yet.
The interactive run prints this hint, but the agent driving the pane may not have it; reproduce it directly.

1. Detect prerequisites with the non-interactive `--ls --onlyMissing` command and post-filtering documented in `references/backport-tool.md` (Missing Prerequisite Backports).
   Pass the conflicting files (from `git diff --name-only --diff-filter=U`) as the paths and the current backport branch as the target.
   If the user pasted the tool's hint block from the interactive pane, use that as the authoritative list instead.
2. Investigate each missing/pending candidate using the same exhaustive PR reading as Understand The Original Change, and classify whether the current conflict actually depends on that PR:
   - **Blocker / prerequisite** — the conflicting hunks reference structure, files, or APIs introduced by that PR, so a faithful resolution is impossible (or unsafe) until it lands on the destination branch.
   - **Incidental** — the overlap is cosmetic/adjacent and can be resolved by hand on the destination branch without that PR.
3. Surface and stop at the boundary — do not auto-backport prerequisites.
   Opening other backport PRs is a separate, human-visible side effect outside this skill's contract.
   - If any prerequisite is a blocker: stop, report it (PR link, why it blocks, destination branch), and recommend backporting it first.
     Resume only when the user says to proceed or confirms the prerequisite is handled.
   - If all are incidental: note them in the summary and continue resolving.

## Apply The Resolution

Carry the gathered context into resolution: the resolved hunks must reproduce the original change's intent, adapted to the destination branch — not just a syntactically clean merge of the two sides.
Apply under the Resolution Rules below, stage the resolved files, then `yarn kbn bootstrap` and run Validation, and only then hand back via Stage And Continue The Run.

## Resolution Rules

- Treat the destination branch as source of truth for paths, generated-vs-source files, test conventions, parser/runtime shape, and available tooling.
- If the incoming commit touches a file that does not exist or is superseded on the backport branch, find the branch-equivalent file before applying the change.
- For deleted-by-us conflicts, verify whether the destination branch intentionally removed or relocated the file.
  Prefer applying the behavior to the active branch file, then remove the stale incoming path.
- For additive test conflicts, keep both destination-branch coverage and incoming PR coverage when they test distinct behavior.
- Do not remove unrelated destination-branch behavior while cleaning conflict markers.
- Search for conflict markers after every edit:
  - `rg '<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|' <resolved-files>`

## Validation

These checks need `node_modules` in place for the destination branch, so run `yarn kbn bootstrap` in the checkout first (it can take several minutes) — this is also why bootstrap happens here, per conflict, and not before the run.
The checkout is re-prepared for each target branch, so run bootstrap again every time you reach this step, even if you already bootstrapped on an earlier branch in the same run.
Then run the smallest checks that prove the adapted backport is correct:

- Focused Jest for changed tests, using the closest package config:
  - `node scripts/jest --config=<package>/jest.config.js <test-file>`
- ESLint on changed source and test files:
  - `node scripts/eslint <changed-files>`
- Scoped type check for the owning package:
  - `node scripts/type_check --project <package>/tsconfig.json`
- Kibana change check when available:
  - `node scripts/check_changes.ts`

If `scripts/check_changes.ts` or a branch-local validation script is missing, report it as unavailable and rely on the focused checks above.
