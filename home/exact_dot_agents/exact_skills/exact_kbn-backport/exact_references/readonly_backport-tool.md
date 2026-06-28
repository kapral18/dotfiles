# How The Kibana Backport Tool Works

Reference for the `backport` CLI (`sorenlouv/backport`) as wired into `elastic/kibana`, used by the `kbn-backport` flow.
Descriptive only — it does not perform a backport.

Verify specifics against the locally installed version before relying on them;
the facts below were confirmed against `backport` 10.2.0 in `~/.backport/repositories/elastic/kibana/node_modules/backport`.
Treat the version as the identity to re-check (`node node_modules/backport/bin/backport --version`).

## Identity And Invocation

- The Kibana checkout used for backports is usually `~/.backport/repositories/elastic/kibana`.
  Backport branches are created and resolved there, not in your `~/work/kibana` worktrees.
  The tool derives this path from `repoOwner`/`repoName` (`getRepoPath` → `~/.backport/repositories/<owner>/<repo>`, or
  a `--dir` override) **independent of the process CWD**,
  so you can launch `node scripts/backport` from any checkout that has the wrapper (e.g. your operating `~/work/kibana`)
  and it still cherry-picks in the tool-owned checkout.
  The tool resets/re-clones and re-prepares that checkout per target branch,
  so do not root any long-lived process (like the controlling tmux window) inside it.
- Kibana's configured `backportBinary` is `node scripts/backport` (from `.backportrc.json`).
  That wrapper is the right entrypoint for the **interactive** run a human drives.
- The wrapper uses `require('backport')` (CommonJS).
  The package is an ESM build, so under some Node versions invoking it programmatically fails with `ERR_PACKAGE_PATH_NOT_EXPORTED`.
  For **non-interactive helper calls** the agent makes itself (listing, detection), invoke the bin directly and confirm it runs:
  - `node node_modules/backport/bin/backport <args>` from the checkout root.
- Config sources: `~/.backport/config.json` (global, holds `accessToken`), and
  the repo's `.backportrc.json` on `main` (target branches, label mapping, auto-merge).
  Logs: `~/.backport/backport.info.log` and `backport.debug.log`.

## Run Shapes

The tool has two fundamentally different modes; the conflict behavior differs and dictates how it can be automated.

### Interactive (`node scripts/backport --pr <N>`)

A human (or an agent driving the TTY) runs it. The flow prompts and pauses:

1. `Select pull request` — skipped when `--pr <N>` / `--sha <sha>` is given.
2. `Select branch` — a multi-select checkbox list (space toggles, enter confirms).
   Skipped when `--targetBranch`/`-b` is passed (may be given more than once).
3. For each target branch it creates `backport/<targetBranch>/pr-<N>` from the target branch and cherry-picks.
4. On a clean cherry-pick it pushes the branch and opens the backport PR automatically.
   (With `rerere` enabled, a repeat conflict it already knows is auto-resolved and looks like a clean cherry-pick here.)
5. On a conflict it:
   - prints `The commit could not be backported due to conflicts` and the repo path,
   - prints the missing-prerequisite hint (see below) when any are found,
   - opens `options.editor` if set (avoid setting an editor when driving non-visually),
   - **pauses** on `Press ENTER when the conflicts are resolved and files are staged (Y/n)`,
     looping until there are no conflict markers and the files are staged.
     Only then does it continue to push + open the PR.

The interactive pause is the seam the `kbn-backport` flow plugs into: resolve + stage in the checkout, then
send ENTER to let the tool finish push + PR creation.

### Non-interactive (`--nonInteractive` / `--json`)

Returns JSON, no prompts.
Requires `--pr`/`--sha` (or `--ls`).
On conflict there is **no pause and no resume**: per-branch it either auto-resolves crudely or throws, and
the branch is recorded as an error while the run continues to the next branch — push and PR creation are skipped for the conflicted branch.
The conflict-handling options:

- `--autoResolveConflictsWithTheirs` — abort and re-cherry-pick with `--strategy-option=theirs` (takes the source side wholesale;
  not a faithful resolution).
- `--commitConflicts` — commit the conflict markers and open a draft PR.
- `autoFixConflicts` — a real hook to inject intelligent resolution mid-cherry-pick, but
  it is **API-only** (a callback passed to `backportRun({ options })`), not a CLI flag.
- none of the above — throws `merge-conflict-exception` for that branch.

Implication: you cannot resolve a conflict and then have the **CLI** resume and push/open the PR in the same run.
Smart resolution with tool-owned push/PR is only possible interactively (drive the pause) or via the API hook.
This is why the e2e flow drives the interactive run.

## Missing Prerequisite Backports

A conflict is often caused by an earlier PR that touched the same files and is not on the target branch yet.
The interactive run prints this as: `Hint:
Before fixing the conflicts manually you should consider backporting the following pull requests to "<branch>"`,
each line tagged `(backport missing)` (links the source PR) or `(backport pending)` (links the open target-branch backport PR).

Detection heuristic (`getCommitsWithoutBackports`):
prior PRs (any author) that touched the **same conflicting files** on the source branch,
committed on or before the commit being backported,
whose backport to the target branch is not yet present (no `MERGED` target PR
and the target merge commit is not already an ancestor of the checkout `HEAD`).

It runs only mid-conflict in interactive mode, so an agent that did not see that terminal cannot read it.
Reproduce it non-interactively (read-only GitHub query; safe while a cherry-pick is in progress):

```bash
node node_modules/backport/bin/backport --ls --onlyMissing --all \
  -p <conflicting-file-1> -p <conflicting-file-2> ... \
  -b <targetBranch> -n 50 --json
```

- Run from the checkout root.
  Do **not** pass `--pr`/`--sha`: those dispatch to a pull-number lookup and skip the path-based history search.
  Use `--all` (all authors) + one `-p` per conflicting file (from `git diff --name-only --diff-filter=U`).
- Default max is 10 commits; pass `-n 50` to match the interactive window.
  Optionally bound with `--until <ISO date>` using the backported commit's date (`git show -s --format=%cI CHERRY_PICK_HEAD`).
- Caveat: `--onlyMissing` filters to "any target PR state ≠ `MERGED`" —
  it is **not** target-branch-specific and does not run the ancestor check.
  Post-filter the JSON to entries whose `targetPullRequestStates[]` has `branch == <targetBranch>` and `state != MERGED`, and
  confirm "already present" with `git merge-base --is-ancestor <mergeCommit.sha> HEAD` (exit 0 = present, skip it).
  Here `HEAD` is the in-progress backport branch you are resolving on — this is the mid-conflict prerequisite check,
  distinct from the pre-run candidate-selection check against the upstream `<upstream>/<branch>` tracking ref.
- JSON shape: `commits[].sourcePullRequest{number,title,url}` and `commits[].targetPullRequestStates[]{branch,state,url,mergeCommit{sha}}`.
  `state` is `NOT_CREATED` (missing → use the source PR url), `OPEN` (pending → use that target PR url), or `MERGED` (present).

## Target-Branch Policy (elastic/kibana)

Decide targets from policy, then reconcile against what already exists. Sources (read live, do not hardcode):

- **Active release branches** — `versions.json` on `main` (`gh api repos/elastic/kibana/contents/versions.json`):
  `versions[]` with `branch` + `branchType`.
  Backport targets are the `branchType: "release"` entries (e.g.
  `9.4`, `9.3`, `8.19`); `branchType: "development"` (`main`) is the source, never a target.
- **`.backportrc.json`** on `main`: `targetBranchChoices`, `targetPRLabels` (`backport`), `branchLabelMapping` (`^v9.5.0$` → `main`;
  `^v(\d+).(\d+).\d+$` → `$1.$2`, i.e. a `vX.Y.Z` label → branch `X.Y`), `autoMerge: true`, `autoMergeMethod: squash`.
- **Source PR `backport:*` label** (see `~/.agents/skills/kibana-labels-propose/SKILL.md` for label semantics):
  - `backport:skip` — the author marked it as not to be backported. Do not proceed without explicit user confirmation.
  - `backport:all-open` — backport to all open release minors = the `versions.json` `branchType: "release"` branches.
  - `backport:version` + `vX.Y.Z` — backport to the specific `X.Y` branch(es).
- **The tool's own suggestion** — each commit carries `suggestedTargetBranches`:
  version-label branches whose backport state is `NOT_CREATED`/`CLOSED`, minus those already `MERGED`.
  Available in the `--ls`/`--json` output for the PR.

Reconcile before selecting targets: Kibana CI (`.github/workflows/on-merge.yml`) auto-creates backports
when `backport:all-open`/`backport:version` is present on merge,
so some target backports may already exist by the time you backport manually.
The policy: the **only** source of truth for "already backported" is whether the source PR's merge commit is actually present on the target release branch (an ancestor of the upstream `elastic/kibana` remote-tracking ref for that branch, e.g.
`elastic/<branch>`); the tool's `targetPullRequestStates` / `suggestedTargetBranches` and `gh pr list` are candidate hints only
and can be stale or reflect an in-flight PR that never merged — never treat them as proof the commit landed.
The `kbn-backport` flow performs the per-branch presence check,
fetching only the candidate branches from the upstream remote (never a bare `git fetch`/`--all`, which is heavy on Kibana);
suggest exactly the active release branches where the commit is absent.

## Per-Branch Flow And Naming

For each selected target branch (`cherrypickAndCreateTargetPullRequest`):
validate the branch → create `backport/<targetBranch>/pr-<N>` from it → cherry-pick each commit → (unless `--dryRun`) push the branch and delete the local copy → open the backport PR (title from the source commit, body `# Backport …`) → add target labels (`backport`) / assignees / reviewers → enable auto-merge (squash) when there were no conflicts.

Because the per-branch working branch is cut fresh from each target branch's base,
the checkout's tree (and therefore its `node_modules`) is re-prepared for every target.
A bootstrap done while resolving one branch does not carry over to the next;
re-run `yarn kbn bootstrap` on each branch that needs hand-resolution.

Useful flags for the e2e flow: `--pr <N>`, `-b/--targetBranch <branch>` (repeatable; skips the branch prompt), `--ls` (list,
do not backport), `--onlyMissing`, `-p/--path` (repeatable), `-n/--maxNumber`, `--json`, `--dryRun`, `--draft`, `--autoMerge`.
