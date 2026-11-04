---
sidebar_position: 5
---

# GitHub worktree integration

The fzf-based GitHub picker (`prefix` + `G`) calls `,gh-worktree` for repo/bootstrap routing. `,gh-worktree` delegates to `,w` for worktree creation and tmux session management.

## Reusable CLI flow

Use `,gh-worktree` when you want the same repo/bootstrap behavior outside tmux pickers, including from agent sessions.

```bash
,gh-worktree pr owner/repo 12345 --focus
,gh-worktree issue owner/repo 12345 --focus
,gh-worktree issue owner/repo 12345 --branch chore/fix-widget
,gh-worktree pr owner/repo 12345 --create-bg --quiet
```

Behavior:

- Resolves the local checkout root from a repo hint (`--repo-path`) or conventional wrapper path, then verifies that `origin` or `upstream` identifies the requested GitHub repository. A same-name checkout for another owner fails before bootstrap or worktree creation.
- Bootstraps missing repos with `,gh-tfork` unless `--no-bootstrap` is set.
- Delegates PR/issue branch naming and worktree creation to `,w prs` / `,w issue`, with `GH_REPO` set to the requested repository.
- Supports `--print-root` to resolve and print repo root without creating a worktree.

For non-interactive issue work, prefer:

```bash
,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>
```

Without `--branch`, issue creation may prompt for branch input.

## Issue references and PR patches

`,gh-issuew` preserves the repository in explicit issue URLs, absolute issue links in PR bodies, and worktree issue metadata. `--url` and browser actions keep that identity; `--number` prints only the number.

`,w issue` skips worktrees associated with another repository or issue when matching a branch suffix. Explicit branch reuse refuses a conflicting association before changing metadata or focusing its tmux session. Legacy worktrees without issue metadata remain reusable.

`,add-patch-to-prs` resolves each PR's head repository, branch, and commit. It applies and commits the patch in a temporary checkout, then pushes explicitly to that head branch. Existing local branches with the same name stay unchanged. Tracked changes in the starting checkout cause an early refusal. A failed push retains the patch commit on a local `patch-pr-…` recovery branch and reports its name.

`,gh-subissues-create` requires an issue as its parent and rejects pull-request numbers before entering or creating children. It accepts milestone titles containing quotes and saves milestone and label text as JSON values for the next session. Milestone lookup and recovery lists include all API pages. Before creating an issue, it checks every page in the existing two-week issue window for the same title, excluding pull requests. If that lookup fails, the command stops before creating an issue.

## PR shortcuts in the GitHub picker

| Key                   | Behavior                                                                   |
| --------------------- | -------------------------------------------------------------------------- |
| `enter` with no marks | Create/switch to the PR worktree and focus its tmux session                |
| `enter` with marks    | Batch worktree creation for all marked items                               |
| `ctrl-t`              | Explicit batch worktree creation                                           |
| `alt-b`               | Same as single enter, then open the PR in Octo review in a new tmux window |
| `alt-o`               | Open the PR/issue in the browser                                           |
| `alt-y`               | Copy URL to clipboard                                                      |

## Issue shortcuts

`enter` with no marks creates/switches to the issue worktree and focuses its tmux session via `,gh-worktree issue ... --focus`. If the worktree does not exist yet, it presents a branch-name prompt.

## Bootstrap locations

Repos live under `~/code/<repo>`. If the repo does not exist locally, picker actions bootstrap it first with `,gh-tfork <owner/repo>`.

## Picker markers

The GitHub picker shows:

- `◆` markers for PRs/issues that already have local worktrees.
- review status badges: approved, changes requested, pending.
- CI status badges: green/red/yellow for success/failure/pending.

Those markers line up with the session picker enrichment so a PR/issue checked out from the GitHub dashboard appears as a rich worktree row in `prefix` + `T`.
