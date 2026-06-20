---
name: kbn-backport
description: Run an end-to-end elastic/kibana backport for a given PR — compute target branches, launch and steer the interactive backport tool in a dedicated tmux window, resolve each cherry-pick conflict faithfully, and let the tool push and open the backport PRs. Manual-only skill, invoked by name with a PR number.
disable-model-invocation: true
---

# Kibana Backport End-To-End

Use this skill only when explicitly invoked by name, typically as "run/resolve the backport for PR `<N>`". It takes a source PR number and drives the whole backport: it computes the target branches, launches the interactive `node scripts/backport` run in a dedicated tmux window, drives that run, resolves every cherry-pick conflict faithfully, stages, and lets the tool push the branches and open the backport PRs — stopping only where your judgment is genuinely required.

This skill requires a source PR number. If none was provided, ask the user for it before doing anything else.

Read `~/.agents/skills/kbn-backport/references/backport-tool.md` first — it is the source of truth for how the tool behaves (prompts, flags, missing-backport detection, branch policy, per-branch flow). This skill orchestrates that tool; it does not restate it.

## Contract

- One interactive `node scripts/backport` run, launched in a dedicated tmux window, drives the **whole** process. The tool owns branch creation, cherry-pick, push, and PR creation; this skill owns target selection, conflict resolution, and the decision of when to hand control back to you.
- Keep the controlling window and the tool's checkout separate. Spawn a dedicated window in the current tmux session (the one the agent is running in, rooted at your `~/work/kibana` checkout), never inside the tool-owned `~/.backport/repositories/elastic/kibana` — the tool resets/re-clones that directory, so a window rooted there is unsafe. The run still backports into the tool-owned checkout regardless of where it is launched.
- The tool's checkout (`~/.backport/repositories/elastic/kibana`, the tool-owned dir — not your `~/work/kibana` worktrees) is where cherry-picks and conflict resolution happen. The run is strictly sequential and uses this single checkout: one target branch at a time, fully, before the next. There is only one checkout state at any moment, and the tool re-prepares it from each new target branch — so the previous branch's `node_modules` no longer matches.
- Do nothing in the tool-owned checkout until the run actually pauses on a conflict. A clean cherry-pick needs no agent action — the tool pushes and opens the PR on its own and moves to the next branch. Per-conflict work (investigate, resolve, `yarn kbn bootstrap`, validate, stage) happens only for the branch currently paused, never up front and never for multiple branches at once. Because each branch re-prepares the checkout, `yarn kbn bootstrap` must run again for every conflicting branch — it is never "already done" from a prior branch.
- Compute target branches from Kibana policy and confirm them before launching (see Compute Target Branches). Stop and confirm if the source PR carries `backport:skip`.
- Understand the original commit/PR being backported before resolving anything; a faithful resolution requires knowing what the change intended and why.
- Check whether each conflict is caused by missing prerequisite backports before hand-resolving; surface them and let the user decide — do not open prerequisite backport PRs yourself.
- Resolve in context, adapting paths and implementation style to the destination branch; preserve destination-branch behavior unless the incoming PR intentionally changes it.
- Stop points (hand back to the user): `backport:skip` present, target-branch ambiguity, a missing prerequisite that blocks faithful resolution, any path outside team ownership, or a resolution you are not confident is faithful.
- Compatibility impact default: `none`. Do not add compatibility shims unless explicitly requested.

## Compute Target Branches

Before launching the tool, decide which branches to backport to and confirm with the user. Use the Target-Branch Policy in `references/backport-tool.md` for the authoritative rules; the steps here are the procedure.

1. Read the source PR's labels and backport intent: `gh pr view <N> --repo elastic/kibana --json number,title,labels,url`.
2. If `backport:skip` is present, **stop and confirm** with the user before doing anything else — the author marked it as not to be backported.
3. Derive the candidate target set:
   - `backport:all-open` → the active release branches from `versions.json` (`branchType: "release"`).
   - `backport:version` + `vX.Y.Z` → branch `X.Y` per the `branchLabelMapping`.
   - Otherwise fall back to the tool's `suggestedTargetBranches` for the PR, or ask the user. (These only seed the candidate set; presence on a branch is decided in step 4, not here.)
4. Determine which candidates still need a backport by **actual commit presence** — this is the only source of truth for "already backported". Do not infer it from labels, PR titles, or the tool's `targetPullRequestStates`/`suggestedTargetBranches` (those can be stale, in-flight, or wrong).
   - Find the source PR's merge commit on the source branch: `gh pr view <N> --repo elastic/kibana --json mergeCommit -q .mergeCommit.oid` (Kibana squash-merges, so this is the single commit to look for).
   - Identify the upstream remote in the backport checkout — the one pointing at `elastic/kibana` (commonly `elastic`, not `origin`; your fork is a separate remote): `git remote -v | rg 'github.com[:/]elastic/kibana'`.
   - Fetch only the candidate branches you are about to check — never a bare `git fetch` or `--all`, which pulls every ref and is very heavy on Kibana: `git fetch <upstream> <branch1> <branch2> …` (one branch name per candidate). With the upstream's standard refspec this refreshes the `<upstream>/<branch>` tracking refs for just those branches (and `FETCH_HEAD`); if a tracking ref is not updated, check against `FETCH_HEAD` for the branch you just fetched.
   - For each candidate release branch, test whether that commit is already present against the upstream remote-tracking ref: `git merge-base --is-ancestor <mergeCommitSha> <upstream>/<branch>` (exit 0 = present → already backported, drop it; exit 1 = absent → still needs backporting, keep it). The squash commit's SHA differs per branch, so also confirm absence by content where the SHA check is inconclusive — search the branch for the source PR reference: `git log <upstream>/<branch> --grep '(#<N>)' --oneline` (a hit means it is already there).
   - The branches to suggest are exactly the active release branches where the commit is **not** present.
5. Present the proposed target branches (those still missing the commit) and, separately, any candidates dropped because the commit is already on that branch. Get the user's confirmation. Branch selection sometimes needs human judgment — treat ambiguity as a stop point.

## Drive The Backport Run

This run **is** the backport. Launch the interactive tool once in a dedicated tmux window and let it walk the confirmed target branches one at a time; you only step in when it pauses on a conflict. Do not pre-bootstrap, pre-resolve, or do any per-branch work before launching. Driving the window's TTY pane follows the repo's existing send-keys pattern (`~/.config/tmux/scripts/pickers/session/action_send_command.sh`): address the pane by the id you captured at spawn, then `tmux send-keys -t '<pane>' …`.

Two locations are in play; keep them separate:

- **Controlling window** — a dedicated tmux window running `node scripts/backport`, driven through its pane id. Spawn it in the current tmux session (the one the agent is running in, rooted at the `~/work/kibana` checkout), **never** in `~/.backport/repositories/elastic/kibana`. That tool-owned checkout is the tool's mutable workspace — it resets, re-clones, and re-prepares it for every target branch and may nuke it at any time, so a window rooted there can have its CWD pulled out from under it. The tool computes its checkout path from `repoOwner`/`repoName` under `~/.backport/repositories/`, independent of where it is launched, so launching from the operating checkout still backports into the tool-owned checkout correctly.
- **Tool-owned checkout** — `~/.backport/repositories/elastic/kibana`, where the paused conflict state lives. All per-conflict resolution commands (git inspection, edits, `yarn kbn bootstrap`, validation, `git add`) run there, addressed explicitly (`git -C ~/.backport/repositories/elastic/kibana …` or a separate shell `cd`'d into it) — not in the controlling window's pane.

1. Spawn a dedicated controlling **window** in the current tmux session, detached, with its CWD on the operating checkout (not the tool-owned checkout) — e.g. `tmux new-window -d -n kbn-backport -c <operating-kibana-checkout> -PF '#{pane_id}'`, which creates the window in the current session without stealing focus and prints its pane id. Drive the run through that pane id (`capture-pane`/`send-keys -t '<pane>'`). Own this window; do not reuse the user's existing shell pane or window.
2. Launch the run from that pane, passing the confirmed branches so you do not have to drive the checkbox prompt:
   - `tmux send-keys -t '<pane>' 'node scripts/backport --pr <N> -b <branch> [-b <branch> …]' C-m`
   - Do not set an editor (`--editor`/`$EDITOR`) for this pane; the tool only spawns one if configured, and an editor popup cannot be driven blind.
3. Poll the pane with `tmux capture-pane -p -t '<pane>'` to follow progress. Drive the run as a loop until it exits:
   - Cherry-pick succeeded for a branch → the tool pushes and opens the PR itself; continue watching.
   - Conflict pause (`Press ENTER when the conflicts are resolved and files are staged (Y/n)`) → work the per-conflict procedure against the tool-owned checkout (not the controlling window) for the current branch (Resolve A Conflict → Apply under Resolution Rules → stage → `yarn kbn bootstrap` + Validation), then Stage And Continue The Run sends ENTER to the controlling window's pane once it is staged, conflict-free, and validated. Only then does the run move to the next branch.
   - Run completed → capture the final summary and the opened backport PR URLs.
4. If the launched `node scripts/backport` wrapper fails to start (e.g. `ERR_PACKAGE_PATH_NOT_EXPORTED`), report it and stop; do not silently fall back to a different mechanism.
5. Clean up the window you spawned (`tmux kill-window -t '<pane>'` — a pane id is a valid window target) once the run has exited and its output is captured. Keep it open only if the run ended with something needing the user's attention (failed/aborted run, unresolved conflict, or a blocked prerequisite) — say so and leave the window for inspection.

## Resolve A Conflict

Triggered only when the run pauses with a conflict on the current target branch. The conflict state lives in the tool-owned checkout (`~/.backport/repositories/elastic/kibana`); run every command below there — addressed explicitly with `git -C <checkout>` or from a shell `cd`'d into it, not from the controlling window. Per pause, the order is: inspect → understand → resolve → stage → `yarn kbn bootstrap` → validate → send ENTER (to the controlling window's pane). Do all of it in this checkout before handing back, then let the run advance to the next branch.

Set up before editing:

1. Follow the local `git` skill for git safety.
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

### Understand The Original Change

Before resolving the conflict, investigate the commit/PR being backported so the resolution carries the same intent. Do not resolve from the conflict hunks alone.

1. Identify the source change:
   - `git show CHERRY_PICK_HEAD` for the full original diff, message, and rationale.
   - Extract the originating PR number from the commit message (Kibana commits end with `(#NNNNN)`).
2. Read the original PR exhaustively — every reference, comment, and linked issue, all the way down. Do not skim the description and stop; build the complete context for why the change exists and what shape reviewers landed on.
   - Full PR body, metadata, and linked issues: `gh pr view <NNNNN> --repo elastic/kibana --json title,body,state,labels,closingIssuesReferences,comments,reviews,url`.
   - Every conversation comment: `gh pr view <NNNNN> --repo elastic/kibana --comments` (read all of them, not just the latest).
   - Every review and inline review-thread comment (these hold the design rationale): `gh api --paginate repos/elastic/kibana/pulls/<NNNNN>/reviews` and `gh api --paginate repos/elastic/kibana/pulls/<NNNNN>/comments`.
   - The complete intended change on its source branch: `gh pr diff <NNNNN> --repo elastic/kibana`.
   - Follow references transitively, to the last bit: for every linked/closing issue read the issue and all its comments (`gh issue view <n> --repo elastic/kibana --comments`), and for every other PR/issue referenced in the body, comments, or reviews, open and read it the same way. Continue until no new referenced PR/issue/discussion adds context.
   - Note what behavior the change adds/removes/fixes, every constraint or follow-up raised in review, and any decision that altered the change from its original form.

### Establish Destination-Branch Context

Especially when the original diff does not apply cleanly, learn how the affected areas work on the destination branch:

- Use the `semantic-code-search` skill (`~/.agents/skills/semantic-code-search/SKILL.md`) against the `kibana-repo` index to learn how the affected modules, symbols, and call sites work on the destination branch. Verify `kibana-repo` exists via `list_indices` first, then pass `index: kibana-repo` explicitly to the SCSI tools.
- Treat semantic results as base context only; validate the actual destination-branch state against local file reads and `git` on the backport checkout.
- If `kibana-repo` is missing from `list_indices` or SCSI is unavailable, fall back to local `rg`, file reads, and `git log`/`git blame` on the affected paths.

### Check For Missing Prerequisite Backports

A conflict is often caused not by the change itself but by an earlier PR that touched the same files and has not been backported to the destination branch yet. The interactive run prints this hint, but the agent driving the pane may not have it; reproduce it directly.

1. Detect prerequisites with the non-interactive `--ls --onlyMissing` command and post-filtering documented in `references/backport-tool.md` (Missing Prerequisite Backports). Pass the conflicting files (from `git diff --name-only --diff-filter=U`) as the paths and the current backport branch as the target. If the user pasted the tool's hint block from the interactive pane, use that as the authoritative list instead.
2. Investigate each missing/pending candidate using the same exhaustive PR reading as Understand The Original Change, and classify whether the current conflict actually depends on that PR:
   - **Blocker / prerequisite** — the conflicting hunks reference structure, files, or APIs introduced by that PR, so a faithful resolution is impossible (or unsafe) until it lands on the destination branch.
   - **Incidental** — the overlap is cosmetic/adjacent and can be resolved by hand on the destination branch without that PR.
3. Surface and stop at the boundary — do not auto-backport prerequisites. Opening other backport PRs is a separate, human-visible side effect outside this skill's contract.
   - If any prerequisite is a blocker: stop, report it (PR link, why it blocks, destination branch), and recommend backporting it first. Resume only when the user says to proceed or confirms the prerequisite is handled.
   - If all are incidental: note them in the summary and continue resolving.

### Apply The Resolution

Carry the gathered context into resolution: the resolved hunks must reproduce the original change's intent, adapted to the destination branch — not just a syntactically clean merge of the two sides. Apply under the Resolution Rules below, stage the resolved files, then `yarn kbn bootstrap` and run Validation, and only then hand back via Stage And Continue The Run.

## Resolution Rules

- Treat the destination branch as source of truth for paths, generated-vs-source files, test conventions, parser/runtime shape, and available tooling.
- If the incoming commit touches a file that does not exist or is superseded on the backport branch, find the branch-equivalent file before applying the change.
- For deleted-by-us conflicts, verify whether the destination branch intentionally removed or relocated the file. Prefer applying the behavior to the active branch file, then remove the stale incoming path.
- For additive test conflicts, keep both destination-branch coverage and incoming PR coverage when they test distinct behavior.
- Do not remove unrelated destination-branch behavior while cleaning conflict markers.
- Search for conflict markers after every edit:
  - `rg '<<<<<<<|=======|>>>>>>>|\|\|\|\|\|\|\|' <resolved-files>`

## Validation

These checks need `node_modules` in place for the destination branch, so run `yarn kbn bootstrap` in the checkout first (it can take several minutes) — this is also why bootstrap happens here, per conflict, and not before the run. The checkout is re-prepared for each target branch, so run bootstrap again every time you reach this step, even if you already bootstrapped on an earlier branch in the same run. Then run the smallest checks that prove the adapted backport is correct:

- Focused Jest for changed tests, using the closest package config:
  - `node scripts/jest --config=<package>/jest.config.js <test-file>`
- ESLint on changed source and test files:
  - `node scripts/eslint <changed-files>`
- Scoped type check for the owning package:
  - `node scripts/type_check --project <package>/tsconfig.json`
- Kibana change check when available:
  - `node scripts/check_changes.ts`

If `scripts/check_changes.ts` or a branch-local validation script is missing, report it as unavailable and rely on the focused checks above.

## Stage And Continue The Run

Once the resolution is applied (Apply The Resolution), stage and gate it, then hand back to the run:

1. Review final diffs:
   - `git diff -- <changed-files>`
   - `git diff --cached -- <changed-files>`
2. Stage only the resolved backport files:
   - `git add <resolved-files>`
3. With the resolution staged, run `yarn kbn bootstrap` and Validation (above) so the verifiers actually run and pass before you continue.
4. Confirm there is nothing left to resolve:
   - `git diff --check --cached`
   - `git diff --name-only --diff-filter=U`
   - `git status --short --branch`
5. Hand control back to the tool: send ENTER to the run's pane (`tmux send-keys -t '<pane>' C-m`) so it continues — pushing the branch and opening the backport PR for this target. Send ENTER only after step 4 shows no remaining conflicts, the files are staged, and validation passed; the tool re-prompts otherwise.
6. Resume polling the pane (Drive The Backport Run): the run advances to the next target branch in the same checkout — handle its conflict the same way if one occurs, or capture the completion summary when the run exits.

## Finish And Summarize

When the run has exited, summarize the whole backport:

- source PR/commit backported, and the target branches attempted
- per target branch: the opened backport PR URL (or that it was skipped/failed and why)
- missing/pending prerequisite backports found, each classified blocker or incidental (or "none found")
- conflicts resolved and the validation commands + results
- anything left for the user (unresolved conflicts, blocked prerequisites, branches needing manual attention)
- `Compatibility impact: none | removed (requested) | kept existing (requested)`
