---
sidebar_position: 1
---

# Git Worktree Workflow

This setup ships a worktree helper command called `,w`.

- Source: [`home/exact_bin/executable_,w`](../../../../home/exact_bin/executable_,w)
- Helpers: [`home/exact_bin/utils/,w/`](../../../../home/exact_bin/utils/,w/)

The goal is to make branch isolation + review + context switching cheap.

## Preconditions

- You are inside a git repository.
- `,w` is installed and on `PATH`.

## Subcommands

### `add` — create a worktree

```bash
,w add feat/my-change main
,w add origin/some-branch
,w add -q feat/quick
```

- `<branch_name>` can be a local branch, `origin/<branch>`, or `user/<branch>`.
- `[base_branch]` is optional; defaults to the current branch.
- When `[base_branch]` is a plain branch name (like `main`), base ref resolution prefers `origin/<base>` then `upstream/<base>` before falling back to a local `<base>` branch. This avoids creating worktrees from stale local base branches.
- `-q`/`--quiet` suppresses informational output.
- Adds a zoxide entry for the new path when zoxide is installed.

### `prs` — check out PRs into worktrees

```bash
,w prs 12345
,w prs 12345 12346
,w prs --focus 12345
,w prs --awaiting
,w prs "label:bug"
```

- No arguments opens an interactive fzf multi-select picker.
- `--focus` switches/attaches to the created worktree's tmux session.
- `--awaiting` lists PRs awaiting your review (last 7 days by default; tune with `COMMA_W_AWAITING_DAYS`).
- Automatically adds contributor forks as remotes when needed.
- First-party PRs use a plain branch name (`feat/foo`); third-party forks use `<remote>__<branch>` and write per-worktree push routing so `git push` targets the fork.
- Upstream tracking prefers canonical refs (`origin/<branch>`, then `upstream/<branch>`) for first-party remotes.

### `issue` — create/reuse an issue worktree

```bash
,w issue 12345
,w issue --focus 12345
,w issue --branch my-fix 12345
,w issue https://github.com/elastic/kibana/issues/12345
```

- Reuses an existing issue worktree (metadata or issue-number heuristic) when one exists.
- Prompts for a branch name when creating a new worktree; branch is created as `<name>-<issue_number>`.
- `-b`/`--branch` provides the branch name non-interactively.
- `--focus` switches/attaches to the worktree's tmux session.
- If the target branch already exists locally but has **no unique commits** relative to the repo default branch, it is fast-forwarded to the latest default branch before worktree creation (prevents “stale branch pointer” worktrees from starting at months-old commits).
- If you already created a matching branch manually (via `,w add`), entering that exact branch name links the issue metadata without renaming.

### `ls` — list worktrees

```bash
,w ls
,w ls --long
,w ls --dirty
,w ls --porcelain
,w ls --sort path --no-header
```

- Default table: CUR, BRANCH, PATH, UPSTREAM, TMUX, STATE.
- `--long` adds AHEAD/BEHIND columns.
- `--dirty` computes and shows dirty state (slow in large repos).
- `--porcelain` prints raw `git worktree list --porcelain` output.
- `--selectable` prints `branch<TAB>path` for non-detached, non-locked worktrees (used by other subcommands).
- `--full-path` disables path shortening.
- `--sort branch|path` controls row order.

### `switch` — interactive worktree picker

```bash
,w switch
,w switch kibana
```

- Opens an fzf picker over selectable worktrees.
- If the argument exactly matches a branch or path, switches directly without opening fzf.
- Creates a tmux session for the worktree if one does not exist.

### `open` — focus a worktree by name/path

```bash
,w open feat/my-change
,w open /path/to/worktree
```

- Accepts a branch name or absolute path.
- Creates a tmux session if needed and switches/attaches to it.

### `mv` — move/rename a worktree

```bash
,w mv old-branch new-branch
,w mv --keep-path old-branch new-branch
,w mv --path ~/work/repo/new-dir old-branch new-branch
,w mv --focus old-branch new-branch
```

- Renames the branch and moves the worktree directory as a unit.
- Updates tmux session name and zoxide entries.
- `--keep-path` renames only the branch (directory stays).
- `--path <dir>` overrides the destination directory.
- `--focus` switches to the resulting tmux session after the move.

### `remove` — clean up worktrees

```bash
,w remove
,w remove --paths /path/to/wt1 /path/to/wt2
,w remove --tmux-notify
```

- Interactive fzf multi-select by default.
- For each selected worktree: removes directory, deletes local branch, removes unused fork remotes, cleans empty parent dirs, purges from zoxide, kills tmux session.
- Protects the repository's actual default branch (detected from remote HEAD).
- `.DS_Store` is treated as ignorable so Finder metadata does not keep empty dirs alive.
- Leftover files in otherwise-empty parents are bagged to `../.bag/worktree_remove/<wrapper>/<timestamp>/...`.
- `--paths` skips the picker and also allows removing detached worktrees.
- `--tmux-notify` shows progress via tmux messages (useful from scripts).

### `prune` — clean stale metadata

```bash
,w prune
,w prune --apply
,w prune --apply --all
```

- Default is dry-run (shows what would be cleaned).
- `--apply` runs `git worktree prune` and kills stale tmux sessions.
- `--all` considers tmux sessions across all repos, not just the current one.

### `doctor` — check dependencies and state

```bash
,w doctor
```

- Checks for `git`, `fzf`, `gh`, `tmux`, `zoxide`, `bat`.
- Reports stale worktree paths and stale tmux sessions.
- Suggests `,w prune --apply` when issues are found.

## GitHub Picker Integration

The fzf-based GitHub picker (`prefix` + `G`) connects directly to `,w` for worktree creation and session management.

PR shortcuts (inside the GitHub picker):

- `enter` (no marks): create/switch to the PR worktree and focus its tmux session (`,w prs --focus`). Exits the picker.
- `enter` (items marked): batch worktree creation for all marked items (same as `ctrl-t`). Stays in the picker.
- `alt-b`: same as single enter plus open the PR in Octo review in a new tmux window.
- `alt-o`: open the PR/issue in the browser.
- `alt-y`: copy the PR/issue URL to the clipboard.
- `ctrl-t`: explicit batch worktree creation for marked items.

Issue shortcuts:

- `enter` (no marks): create/switch to the issue worktree and focus its tmux session (`,w issue --focus`). Presents an interactive branch name prompt if the worktree doesn't exist yet.

Shared behavior:

- If the repo does not exist locally, actions bootstrap it first with `,gh-tfork <owner/repo>`.
- Bootstrap location: `elastic/*` in `~/work/<repo>`, everything else in `~/code/<repo>`.
- The picker shows `◆` markers for PRs/issues that already have local worktrees, review status badges (`󰄬` approved, `󰀨` changes requested, `` pending), and CI status badges (`●` green/red/yellow for success/failure/pending).

## Verification

```bash
,w ls
,w doctor
```

Confirm the expected worktree exists and tmux session switching works.

## Rollback / Undo

Remove a worktree:

```bash
,w remove
```

If metadata is stale:

```bash
,w prune --apply
```
