# Git Worktree Workflow

Back: [`docs/recipes/index.md`](index.md)

This setup ships a worktree helper command called `,w`.

- Source: `home/exact_bin/executable_,w`

The goal is to make branch isolation + review + context switching cheap.

## Preconditions

- You are inside a git repository.
- `,w` is installed and on `PATH`.

## Steps

### Common Flows

Create a new worktree:

```bash
,w add feat/my-change main
```

Check out a PR into a worktree:

```bash
,w prs 12345
```

Check out an Issue into a worktree:

```bash
,w issue 12345
```

Notes:

- If the PR head repo is first-party (your `origin`/`upstream`, your GitHub login remote, or any remote URL owner matching your login), `,w prs` uses a normal local branch name like `feat/foo` instead of `kapral18__feat/foo`.
- For first-party remotes, upstream tracking now prefers canonical refs (`origin/<branch>`, then `upstream/<branch>`) when present, instead of keeping a login-named remote like `kapral18/<branch>`.
- For fork-prefixed branches (for example `alice__feature/foo`), `,w` writes per-worktree push routing and explicit branch tracking, so plain `git push` targets the fork branch even on reused worktrees.

You can also use these shortcuts directly from `gh-dash` when viewing PRs:
- `ctrl+t`: Create a worktree for the selected PR in the background (log: `${XDG_CACHE_HOME:-~/.cache}/gh-dash/w_prs_<PR>.log`).
- `C` or `Space`: Create/switch to the PR worktree and focus its tmux session (`\,w prs --focus`).
- `b`: Create/switch to the PR worktree, focus tmux, and open Octo review in a new tmux window.
- If the repo does not exist locally yet, PR actions bootstrap it first with `,gh-tfork <owner/repo>` and then continue.
- In the persistent `gh-dash` popup, sync PR actions (`C`/`Space`/`b`) show bootstrap progress in an overlay popup instead of replacing the `gh-dash` UI.
- Bootstrap location follows conventions: `elastic/*` in `~/work/<repo>`, everything else in `~/code/<repo>`.

You can also use these shortcuts directly from `gh-dash` when viewing Issues:
- `ctrl+t`: Create a worktree for the selected Issue in the background (log: `${XDG_CACHE_HOME:-~/.cache}/gh-dash/w_issue_<ISSUE>.log`).
- `C` or `Space`: Create/switch to the Issue worktree and focus its tmux session (`\,w issue --focus`).
- If the repo does not exist locally yet, Issue actions bootstrap it first with `,gh-tfork <owner/repo>` and then continue.
- In the persistent `gh-dash` popup, sync Issue actions (`C`/`Space`) show bootstrap progress in an overlay popup instead of replacing the `gh-dash` UI.
- Bootstrap location follows conventions: `elastic/*` in `~/work/<repo>`, everything else in `~/code/<repo>`.

Clean up a worktree:

```bash
,w remove
```

Notes:

- Cleanup treats `.DS_Store` as ignorable, so empty parent directories aren’t kept alive by Finder metadata.
- Cleanup protects the repository's actual default branch (detected from remote HEAD), not only `main`.
- If cleanup would otherwise leave behind empty parent directories *only because of unrelated leftover files/dirs*, `,w remove` moves those leftovers into a bag directory outside the wrapper:
  `../.bag/worktree_remove/<wrapper>/<timestamp>/...` (relative to the wrapper’s parent).

Non-interactive cleanup (useful from tmux pickers/scripts):

```bash
,w remove --paths /path/to/worktree1 /path/to/worktree2
```

Notes:

- When you pass explicit `--paths`, detached worktrees are removable as well (interactive `,w remove` continues to hide detached worktrees by default).

## Verification

```bash
,w ls
,w doctor
```

Confirm the expected worktree exists and tmux session switching works.

## What It Does

The `,w` command is a wrapper around `git worktree` plus extra conveniences
(directory naming, remote handling, tmux session integration).

For the high-level overview, see the root `README.md` section about `,w`.

## Rollback / Undo

- Remove the created worktree:

```bash
,w remove
```

- If metadata is stale:

```bash
,w prune
```
