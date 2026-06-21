# Git, identity, and worktrees

This section is three related systems, not one blob:

| System            | What it owns                                                       | Page                                      |
| ----------------- | ------------------------------------------------------------------ | ----------------------------------------- |
| Git defaults      | Global git behavior, conditional includes, aliases, signing config | [Git config](git-config.md)               |
| Identity and keys | 1Password SSH agent, public-key selectors, work/personal switching | [Identity and keys](identity-and-keys.md) |
| Worktrees         | `,w`, `,gh-worktree`, branch/issue metadata, tmux session naming   | [Worktrees](worktrees.md)                 |

The systems connect at runtime: Git chooses identity by repo path, 1Password holds the private keys, worktree metadata helps pickers and helper commands resolve PRs/issues, and tmux gives each worktree a stable session.

## Quick checks

```bash
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
echo "$SSH_AUTH_SOCK"
,w doctor
```

## Related

- [Switching work vs personal identity](switch-identity.md)
- [GitHub CLI extension management](gh-extension.md)
- [Security and secrets](../../security/security-and-secrets.md)
- [Session picker](../tmux/session-picker.md)
