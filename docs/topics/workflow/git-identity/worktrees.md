---
sidebar_position: 3
---

# Git worktree workflow

This setup uses `,w` to make branch isolation, PR checkout, issue work, and tmux session switching cheap.

| Surface        | Source                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| CLI entry      | [`home/exact_bin/executable_,w`](../../../../home/exact_bin/executable_,w)                                                                        |
| Helpers        | [`home/exact_lib/exact_,w/`](../../../../home/exact_lib/exact_,w/) and [`home/exact_lib/exact_shared/`](../../../../home/exact_lib/exact_shared/) |
| GitHub wrapper | [`home/exact_bin/executable_,gh-worktree`](../../../../home/exact_bin/executable_,gh-worktree)                                                    |
| Visual picker  | [Session picker](../tmux/session-picker.md) and [GitHub picker](../tmux/github-picker.md)                                                         |

## Mental model

| Task                               | Use                                |
| ---------------------------------- | ---------------------------------- |
| Create an isolated branch checkout | `,w add`                           |
| Check out PRs locally              | `,w prs` or the GitHub picker      |
| Start work from an issue           | `,w issue` or `,gh-worktree issue` |
| Focus a worktree's tmux session    | `,w switch` / `,w open`            |
| Rename/move branch + worktree      | `,w mv`                            |
| Remove finished work               | `,w remove`                        |
| Clean stale metadata               | `,w prune`                         |
| Check dependencies/state           | `,w doctor`                        |

## Preconditions

- You are inside a git repository.
- `,w` is installed and on `PATH`.
- For GitHub-backed flows, `gh` is authenticated.

## Fast path

```bash
,w add feat/my-change main
,w prs 12345 --focus
,w issue --branch chore/fix-widget 12345 --focus
,w switch
,w remove
,w doctor
```

## Details

- [Worktree subcommands](worktree-subcommands.md) — exact flags and behavior for `add`, `prs`, `issue`, `ls`, `switch`, `open`, `mv`, `remove`, `prune`, and `doctor`.
- [GitHub worktree integration](worktree-github-integration.md) — how `,gh-worktree`, the GitHub picker, repo bootstrap, Octo review, PR/issue metadata, and tmux sessions fit together.

## Verification

```bash
,w ls
,w doctor
```

Confirm the expected worktree exists and tmux session switching works.

## Rollback / undo

```bash
,w remove
,w prune --apply
```

## Related

- [Session picker](../tmux/session-picker.md)
- [GitHub picker](../tmux/github-picker.md)
- [Git config](git-config.md)
- [Identity and keys](identity-and-keys.md)
