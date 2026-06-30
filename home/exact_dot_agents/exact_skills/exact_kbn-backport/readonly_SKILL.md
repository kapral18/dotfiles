---
name: kbn-backport
description: Run an end-to-end elastic/kibana backport in tmux, including conflict resolution and tool-driven PRs.
disable-model-invocation: true
---

# Kibana Backport End-To-End

Use this skill only when explicitly invoked by name, typically as "run/resolve the backport for PR `<N>`".
It takes a source PR number and drives the whole backport.
It computes the target branches, launches the interactive `node scripts/backport` run in a dedicated tmux window, drives that run, resolves every cherry-pick conflict faithfully, and stages the result.
The tool then pushes the branches and opens the backport PRs; this skill stops only where your judgment is genuinely required.

This skill requires a source PR number. If none was provided, ask the user for it before doing anything else.

Read `~/.agents/skills/kbn-backport/references/backport-tool.md` first.
It is the source of truth for how the tool behaves: prompts, flags, missing-backport detection, branch policy, and per-branch flow.
This skill orchestrates that tool; it does not restate it.

## Contract

- One interactive `node scripts/backport` run, launched in a dedicated tmux window, drives the **whole** process.
  The tool owns branch creation, cherry-pick, push, and PR creation; this skill owns target selection, conflict resolution, and the decision of when to hand control back to you.
- Keep the controlling window and the tool's checkout separate.
  Spawn a dedicated window in the current tmux session, rooted at your `~/work/kibana` checkout.
  Never spawn inside the tool-owned `~/.backport/repositories/elastic/kibana`;
  the tool resets/re-clones that directory, so a window rooted there is unsafe.
  The run still backports into the tool-owned checkout regardless of where it is launched.
- The tool's checkout (`~/.backport/repositories/elastic/kibana`, the tool-owned dir —
  not your `~/work/kibana` worktrees) is where cherry-picks and conflict resolution happen.
  The run is strictly sequential and uses this single checkout: one target branch at a time, fully, before the next.
  There is only one checkout state at any moment, and the tool re-prepares it from each new target branch —
  so the previous branch's `node_modules` no longer matches.
- Do nothing in the tool-owned checkout until the run actually pauses on a conflict.
  A clean cherry-pick needs no agent action — the tool pushes and opens the PR on its own and moves to the next branch.
  Per-conflict work (investigate, resolve, `yarn kbn bootstrap`, validate, stage) happens only for the branch currently paused, never up front and never for multiple branches at once.
  Because each branch re-prepares the checkout, `yarn kbn bootstrap` must run again for every conflicting branch —
  it is never "already done" from a prior branch.
- Compute target branches from Kibana policy and confirm them before launching (see Compute Target Branches).
  Stop and confirm if the source PR carries `backport:skip`.
- Understand the original commit/PR being backported before resolving anything;
  a faithful resolution requires knowing what the change intended and why.
- Check whether each conflict is caused by missing prerequisite backports before hand-resolving; surface them and let the user decide —
  do not open prerequisite backport PRs yourself.
- Resolve in context, adapting paths and implementation style to the destination branch;
  preserve destination-branch behavior unless the incoming PR intentionally changes it.
- Stop points (hand back to the user):
  - `backport:skip` present
  - target-branch ambiguity
  - a missing prerequisite that blocks faithful resolution
  - any path outside team ownership
  - a resolution you are not confident is faithful
- Compatibility impact default: `none`. Do not add compatibility shims unless explicitly requested.

## Compute Target Branches

Before launching the tool, decide which branches to backport to and confirm with the user.
Use the Target-Branch Policy in `references/backport-tool.md` for the authoritative rules; the steps here are the procedure.

1. Read the source PR's labels and backport intent: `gh pr view <N> --repo elastic/kibana --json number,title,labels,url`.
2. If `backport:skip` is present, **stop and confirm** with the user before doing anything else —
   the author marked it as not to be backported.
3. Derive the candidate target set:
   - `backport:all-open` → the active release branches from `versions.json` (`branchType: "release"`).
   - `backport:version` + `vX.Y.Z` → branch `X.Y` per the `branchLabelMapping`.
   - Otherwise fall back to the tool's `suggestedTargetBranches` for the PR, or ask the user.
     (These only seed the candidate set; presence on a branch is decided in step 4, not here.)
4. Determine which candidates still need a backport by **actual commit presence** —
   this is the only source of truth for "already backported".
   Do not infer it from labels, PR titles, or the tool's `targetPullRequestStates`/`suggestedTargetBranches` (those can be stale, in-flight, or wrong).
   - Find the source PR's merge commit on the source branch: `gh pr view <N> --repo elastic/kibana --json mergeCommit -q .mergeCommit.oid`.
     Kibana squash-merges, so this is the single commit to look for.
   - Identify the upstream remote in the backport checkout — the one pointing at `elastic/kibana` (commonly `elastic`, not `origin`;
     your fork is a separate remote): `git remote -v | rg 'github.com[:/]elastic/kibana'`.
   - Fetch only the candidate branches you are about to check.
     Never run a bare `git fetch` or `--all`, which pulls every ref and is very heavy on Kibana:
     `git fetch <upstream> <branch1> <branch2> …` (one branch name per candidate).
     With the upstream's standard refspec this refreshes the `<upstream>/<branch>` tracking refs for just those branches (and `FETCH_HEAD`);
     if a tracking ref is not updated, check against `FETCH_HEAD` for the branch you just fetched.
   - For each candidate release branch, test whether that commit is already present against the upstream remote-tracking ref:
     `git merge-base --is-ancestor <mergeCommitSha> <upstream>/<branch>` (exit 0 = present → already backported, drop it;
     exit 1 = absent → still needs backporting, keep it).
     The squash commit's SHA differs per branch, so also confirm absence by content where the SHA check is inconclusive —
     search the branch for the source PR reference: `git log <upstream>/<branch> --grep '(#<N>)' --oneline` (a hit means it is already there).
   - The branches to suggest are exactly the active release branches where the commit is **not** present.
5. Present the proposed target branches (those still missing the commit) and, separately, any candidates dropped because the commit is already on that branch.
   Get the user's confirmation. Branch selection sometimes needs human judgment — treat ambiguity as a stop point.

## Drive The Backport Run

This run **is** the backport.
Launch the interactive tool once in a dedicated tmux window and let it walk the confirmed target branches one at a time;
you only step in when it pauses on a conflict. Do not pre-bootstrap, pre-resolve, or do any per-branch work before launching.
Driving the window's TTY pane follows the repo's existing send-keys pattern (`~/.config/tmux/scripts/pickers/session/action_send_command.sh`): address the pane by the id you captured at spawn, then `tmux send-keys -t '<pane>' …`.

Two locations are in play; keep them separate:

- **Controlling window** — a dedicated tmux window running `node scripts/backport`, driven through its pane id.
  Spawn it in the current tmux session (the one the agent is running in, rooted at the `~/work/kibana` checkout), **never** in `~/.backport/repositories/elastic/kibana`.
  That tool-owned checkout is the tool's mutable workspace — it resets, re-clones, and re-prepares it for every target branch and may nuke it at any time, so a window rooted there can have its CWD pulled out from under it.
  The tool computes its checkout path from `repoOwner`/`repoName` under `~/.backport/repositories/`, independent of where it is launched, so launching from the operating checkout still backports into the tool-owned checkout correctly.
- **Tool-owned checkout** — `~/.backport/repositories/elastic/kibana`, where the paused conflict state lives.
  All per-conflict resolution commands (git inspection, edits, `yarn kbn bootstrap`, validation, `git add`) run there, addressed explicitly (`git -C ~/.backport/repositories/elastic/kibana …` or a separate shell `cd`'d into it) — not in the controlling window's pane.

1. Spawn a dedicated controlling **window** in the current tmux session, detached, with its CWD on the operating checkout (not the tool-owned checkout) — e.g. `tmux new-window -d -n kbn-backport -c <operating-kibana-checkout> -PF '#{pane_id}'`, which creates the window in the current session without stealing focus and prints its pane id.
   Drive the run through that pane id (`capture-pane`/`send-keys -t '<pane>'`).
   Own this window; do not reuse the user's existing shell pane or window.
2. Launch the run from that pane, passing the confirmed branches so you do not have to drive the checkbox prompt:
   - `tmux send-keys -t '<pane>' 'node scripts/backport --pr <N> -b <branch> [-b <branch> …]' C-m`
   - Do not set an editor (`--editor`/`$EDITOR`) for this pane; the tool only spawns one if configured, and an editor popup cannot be driven blind.
3. Poll the pane with `tmux capture-pane -p -t '<pane>'` to follow progress. Drive the run as a loop until it exits:
   - Cherry-pick succeeded for a branch → the tool pushes and opens the PR itself; continue watching.
   - Conflict pause (`Press ENTER when the conflicts are resolved and files are staged (Y/n)`) → work the per-conflict procedure against the tool-owned checkout (not the controlling window) for the current branch (Resolve A Conflict → Apply under Resolution Rules → stage → `yarn kbn bootstrap` + Validation), then Stage And Continue The Run sends ENTER to the controlling window's pane once it is staged, conflict-free, and validated.
     Only then does the run move to the next branch.
   - Run completed → capture the final summary and the opened backport PR URLs.
4. If the launched `node scripts/backport` wrapper fails to start (e.g. `ERR_PACKAGE_PATH_NOT_EXPORTED`), report it and stop;
   do not silently fall back to a different mechanism.
5. Clean up the window you spawned (`tmux kill-window -t '<pane>'` — a pane id is a valid window target) once the run has exited and its output is captured.
   Keep it open only if the run ended with something needing the user's attention (failed/aborted run, unresolved conflict, or a blocked prerequisite) — say so and leave the window for inspection.

## Resolve A Conflict

Triggered only when the run pauses with a conflict on the current target branch.
The conflict state lives in the tool-owned checkout (`~/.backport/repositories/elastic/kibana`); run every command there —
addressed explicitly with `git -C <checkout>` or from a shell `cd`'d into it, not from the controlling window.
Per pause, the order is: inspect → understand → resolve → stage → `yarn kbn bootstrap` → validate → send ENTER (to the controlling window's pane).
Do all of it in this checkout before handing back, then let the run advance to the next branch.

Full procedure — setup-before-editing checklist, understanding the original change, establishing destination-branch context, checking for missing prerequisite backports, applying the resolution, the resolution rules, and validation — lives in `~/.agents/skills/kbn-backport/references/conflict-resolution.md`.
Load it only once the run has actually paused on a conflict.

## Stage And Continue The Run

Once the resolution is applied (Apply The Resolution, in `references/conflict-resolution.md`), stage and gate it, then hand back to the run:

1. Review final diffs:
   - `git diff -- <changed-files>`
   - `git diff --cached -- <changed-files>`
2. Stage only the resolved backport files:
   - `git add <resolved-files>`
3. With the resolution staged, run `yarn kbn bootstrap` and Validation (`references/conflict-resolution.md`) so the verifiers actually run and pass before you continue.
4. Confirm there is nothing left to resolve:
   - `git diff --check --cached`
   - `git diff --name-only --diff-filter=U`
   - `git status --short --branch`
5. Hand control back to the tool: send ENTER to the run's pane (`tmux send-keys -t '<pane>' C-m`) so it continues —
   pushing the branch and opening the backport PR for this target.
   Send ENTER only after step 4 shows no remaining conflicts, the files are staged, and validation passed; the tool re-prompts otherwise.
6. Resume polling the pane (Drive The Backport Run): the run advances to the next target branch in the same checkout —
   handle its conflict the same way if one occurs, or capture the completion summary when the run exits.

## Finish And Summarize

When the run has exited, summarize the whole backport:

- source PR/commit backported, and the target branches attempted
- per target branch: the opened backport PR URL (or that it was skipped/failed and why)
- missing/pending prerequisite backports found, each classified blocker or incidental (or "none found")
- conflicts resolved and the validation commands + results
- anything left for the user (unresolved conflicts, blocked prerequisites, branches needing manual attention)
- `Compatibility impact: none | removed (requested) | kept existing (requested)`
