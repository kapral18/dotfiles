---
sidebar_position: 4
---

# Worktree subcommands

Detailed reference for the `,w` command family.

## `add` — create a worktree

```bash
,w add feat/my-change main
,w add origin/some-branch
,w add -q feat/quick
```

- `<branch_name>` can be a local branch, `origin/<branch>`, or `user/<branch>`.
- `[base_branch]` is optional; defaults to the current branch.
- Plain base branch names resolve as `origin/<base>`, then `upstream/<base>`, then local `<base>`.
- `-q` / `--quiet` suppresses informational output.
- Adds a zoxide entry for the new path when zoxide is installed.

## `prs` — check out PRs into worktrees

```bash
,w prs 12345
,w prs 12345 12346
,w prs --focus 12345
,w prs --awaiting
,w prs "label:bug"
```

- No arguments opens an interactive fzf multi-select picker.
- `--focus` switches/attaches to the created worktree's tmux session.
- `--awaiting` lists PRs awaiting your review; `COMMA_W_AWAITING_DAYS` tunes the lookback.
- Contributor forks are added as remotes when needed.
- First-party PRs use plain branch names; third-party forks use `<remote>__<branch>` and write per-worktree push routing.
- Upstream tracking prefers canonical refs (`origin/<branch>`, then `upstream/<branch>`).
- The tmux session picker highlights PR-review worktree rows in standout magenta when the PR author is not your configured/authenticated GitHub login. If login cannot be resolved, review coloring is skipped rather than mislabeling.

Login resolution order:

1. `PICK_SESSION_GITHUB_LOGIN` / `@pick_session_github_login`
2. `GITHUB_USER`
3. 7-day cached `gh api user`

## `issue` — create or reuse an issue worktree

```bash
,w issue 12345
,w issue --focus 12345
,w issue --branch my-fix 12345
,w issue https://github.com/elastic/kibana/issues/12345
```

- Reuses an existing issue worktree when metadata or branch heuristics match.
- Prompts for a branch name when creating new work; branch is created as `<name>-<issue_number>`.
- `-b` / `--branch` supplies the branch non-interactively.
- `--focus` switches/attaches to the tmux session.
- Existing local branches with no unique commits relative to default branch are fast-forwarded before worktree creation.
- If you already created a matching branch manually, entering that exact branch links issue metadata without renaming.

## `ls` — list worktrees

```bash
,w ls
,w ls --long
,w ls --dirty
,w ls --porcelain
,w ls --sort path --no-header
```

- Default table: `CUR`, `BRANCH`, `PATH`, `UPSTREAM`, `TMUX`, `STATE`.
- `--long` adds ahead/behind columns.
- `--dirty` computes dirty state, which can be slower in large repos.
- `--porcelain` prints raw `git worktree list --porcelain`.
- `--selectable` prints `branch<TAB>path` for non-detached, non-locked worktrees.
- `--full-path` disables path shortening.
- `--sort branch|path` controls row order.

## `switch` — interactive worktree picker

```bash
,w switch
,w switch kibana
```

- Opens an fzf picker over selectable worktrees.
- Exact branch/path arguments switch directly without fzf.
- Creates a tmux session for the worktree if one does not exist.

## `open` — focus a worktree by name/path

```bash
,w open feat/my-change
,w open /path/to/worktree
```

Accepts a branch name or absolute path, creates a tmux session if needed, and switches/attaches to it.

## `mv` — move/rename a worktree

```bash
,w mv old-branch new-branch
,w mv --keep-path old-branch new-branch
,w mv --path ~/work/repo/new-dir old-branch new-branch
,w mv --focus old-branch new-branch
```

- Renames the branch and moves the worktree directory as a unit.
- Updates tmux session name and zoxide entries.
- `--keep-path` renames only the branch.
- `--path <dir>` overrides destination.
- `--focus` switches to the resulting tmux session.

## `remove` — clean up worktrees

```bash
,w remove
,w remove --paths /path/to/wt1 /path/to/wt2
,w remove --tmux-notify
```

- Interactive fzf multi-select by default.
- Removes directory, deletes local branch, removes unused fork remotes, cleans empty parent dirs, purges from zoxide, and kills the tmux session.
- Protects the repository's actual default branch.
- Treats `.DS_Store` as ignorable.
- Bags leftover files in otherwise-empty parents under `../.bag/worktree_remove/<wrapper>/<timestamp>/...`.
- `--paths` skips the picker and allows removing detached worktrees.
- `--tmux-notify` shows progress via tmux messages.

## `prune` — clean stale metadata

```bash
,w prune
,w prune --apply
,w prune --apply --all
```

- Default is dry-run.
- `--apply` runs `git worktree prune` and kills stale tmux sessions.
- `--all` considers tmux sessions across all repos.

## `doctor` — check dependencies and state

```bash
,w doctor
```

Checks for `git`, `fzf`, `gh`, `tmux`, `zoxide`, and `bat`; reports stale worktree paths and stale tmux sessions; suggests `,w prune --apply` when issues are found.
