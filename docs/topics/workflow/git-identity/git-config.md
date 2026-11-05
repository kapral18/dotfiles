---
sidebar_position: 1
---

# Git config

Git configuration is managed from chezmoi source and installed into `$HOME`.

| Concern                  | Source                                                                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Main git config template | [`home/private_readonly_dot_gitconfig.tmpl`](../../../../home/private_readonly_dot_gitconfig.tmpl)                                                     |
| Allowed signers          | [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../../../../home/private_dot_ssh/private_executable_allowed_signers.tmpl)             |
| Git TUIs                 | [`home/dot_config/exact_lazygit/`](../../../../home/dot_config/exact_lazygit/), [`home/dot_config/exact_tig/`](../../../../home/dot_config/exact_tig/) |

## Identity

Check the active value and the file that set it:

```bash
git config --show-origin --get user.name
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
```

## Large repositories

The global gitconfig avoids repository-size-specific defaults such as `core.fsmonitor`, `feature.manyFiles`, and `feature.experimental`. Large repositories opt into performance settings through their local `.git/config`, so small repos do not spawn fsmonitor daemons or inherit experimental Git defaults.

For very large worktrees, keep maintenance, index, and untracked-cache settings repo-local. Avoid `scalar register` as durable setup in this chezmoi-managed environment because it writes `scalar.repo` and `maintenance.repo` paths into the managed global gitconfig, and the next `chezmoi apply` removes them. Keep `core.fsmonitor=false` unless a repo-specific benchmark proves the daemon is safe and worthwhile for that worktree.

## Pull from upstream

`git pup` pulls from the `upstream` branch whose name matches the current branch and rebases local commits onto it. Configure the `upstream` remote before running it.

## Transfer tracked changes

From the receiving checkout, run `git wtgrab "/path/to/source checkout"`. Staged and unstaged changes transfer separately, including binary files, additions, and deletions. Untracked source files stay at the source. The source clears only after both patches apply successfully; a conflict leaves its changes intact and rolls back the receiving checkout's staged patch.

If the source changes during transfer, cleanup stops and both checkouts retain the transferred changes. The error prints the recovery patch directory when cleanup or rollback needs attention. Inspect both checkouts before retrying.

`,fzf-git-changed-lines` emits added lines as `path:line:col:text`. Hunk counts distinguish source text such as `++ count;` from file headers. Status mode includes text from untracked files and skips deleted and binary files.

## Signing

Commit signing uses SSH signing through the 1Password signing helper. The public key selector lives on disk; the private key stays in 1Password.

Relevant files:

- [`home/private_readonly_dot_gitconfig.tmpl`](../../../../home/private_readonly_dot_gitconfig.tmpl)
- [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../../../../home/private_dot_ssh/private_executable_allowed_signers.tmpl)

## GitHub CLI and dashboard config

| Component               | Source                                                                                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GitHub CLI config       | [`home/dot_config/exact_private_gh/`](../../../../home/dot_config/exact_private_gh/)                                                                                 |
| gh picker config        | [`home/dot_config/herdr/exact_scripts/pickers/github/readonly_gh-picker.yml`](../../../../home/dot_config/herdr/exact_scripts/pickers/github/readonly_gh-picker.yml) |
| Managed extensions hook | [`run_onchange_after_05-install-gh-extensions.fish.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl)                    |

## Related

- [Identity and keys](identity-and-keys.md)
- [Worktrees](worktrees.md)
- [GitHub picker](../herdr/github-picker.md)
