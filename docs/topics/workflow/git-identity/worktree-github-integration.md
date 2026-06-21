---
sidebar_position: 5
---

# GitHub worktree integration

The fzf-based GitHub picker (`prefix` + `G`) calls `,gh-worktree` for repo/bootstrap routing. `,gh-worktree` delegates to `,w` for worktree creation and tmux session management.

## Reusable CLI flow

Use `,gh-worktree` when you want the same repo/bootstrap behavior outside tmux pickers, including from agent sessions.

```bash
,gh-worktree pr elastic/kibana 12345 --focus
,gh-worktree issue elastic/kibana 12345 --focus
,gh-worktree issue elastic/kibana 12345 --branch chore/fix-widget
,gh-worktree pr elastic/kibana 12345 --create-bg --quiet
```

Behavior:

- Resolves the local checkout root from a repo hint (`--repo-path`) or conventional wrapper path.
- Bootstraps missing repos with `,gh-tfork` unless `--no-bootstrap` is set.
- Delegates PR/issue branch naming and worktree creation to `,w prs` / `,w issue`.
- Supports `--print-root` to resolve and print repo root without creating a worktree.

For non-interactive issue work, prefer:

```bash
,gh-worktree issue <owner/repo> <issue_number> --branch <branch-base-name>
```

Without `--branch`, issue creation may prompt for branch input.

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

| Repo owner      | Destination     |
| --------------- | --------------- |
| `elastic/*`     | `~/work/<repo>` |
| everything else | `~/code/<repo>` |

If the repo does not exist locally, picker actions bootstrap it first with `,gh-tfork <owner/repo>`.

## Picker markers

The GitHub picker shows:

- `◆` markers for PRs/issues that already have local worktrees.
- review status badges: approved, changes requested, pending.
- CI status badges: green/red/yellow for success/failure/pending.

Those markers line up with the session picker enrichment so a PR/issue checked out from the GitHub dashboard appears as a rich worktree row in `prefix` + `T`.
