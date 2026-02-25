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

Clean up a worktree:

```bash
,w remove
```

Notes:

- Cleanup treats `.DS_Store` as ignorable, so empty parent directories aren’t kept alive by Finder metadata.
- If cleanup would otherwise leave behind empty parent directories *only because of unrelated leftover files/dirs*, `,w remove` moves those leftovers into a bag directory outside the wrapper:
  `../.bag/worktree_remove/<wrapper>/<timestamp>/...` (relative to the wrapper’s parent).

Non-interactive cleanup (useful from tmux pickers/scripts):

```bash
,w remove --paths /path/to/worktree1 /path/to/worktree2
```

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
