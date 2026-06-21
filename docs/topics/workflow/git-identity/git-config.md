---
sidebar_position: 1
---

# Git config

Git configuration is managed from chezmoi source and installed into `$HOME`.

| Concern                  | Source                                                                                                                                                                                                                             |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Main git config template | [`home/private_readonly_dot_gitconfig.tmpl`](../../../../home/private_readonly_dot_gitconfig.tmpl)                                                                                                                                 |
| Work override            | [`home/work/private_dot_gitconfig.tmpl`](../../../../home/work/private_dot_gitconfig.tmpl)                                                                                                                                         |
| Allowed signers          | [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../../../../home/private_dot_ssh/private_executable_allowed_signers.tmpl)                                                                                         |
| Git TUIs                 | [`home/dot_config/exact_lazygit/`](../../../../home/dot_config/exact_lazygit/), [`home/dot_config/exact_gitui/`](../../../../home/dot_config/exact_gitui/), [`home/dot_config/exact_tig/`](../../../../home/dot_config/exact_tig/) |

## Conditional identity

On non-work machines, the primary gitconfig uses `includeIf "gitdir:~/work/"` so repositories under `~/work/` automatically use the secondary/work identity.

Check the active value and the file that set it:

```bash
git config --show-origin --get user.name
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
```

## Signing

Commit signing uses SSH signing through the 1Password signing helper. The public key selector lives on disk; the private key stays in 1Password.

Relevant files:

- [`home/private_readonly_dot_gitconfig.tmpl`](../../../../home/private_readonly_dot_gitconfig.tmpl)
- [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../../../../home/private_dot_ssh/private_executable_allowed_signers.tmpl)

## GitHub CLI and dashboard config

| Component               | Source                                                                                                                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GitHub CLI config       | [`home/dot_config/exact_private_gh/`](../../../../home/dot_config/exact_private_gh/)                                                                                                     |
| gh picker work config   | [`home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-work.yml`](../../../../home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-work.yml) |
| gh picker home config   | [`home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-home.yml`](../../../../home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-home.yml) |
| Managed extensions hook | [`run_onchange_after_05-install-gh-extensions.fish.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl)                                        |

## Related

- [Identity and keys](identity-and-keys.md)
- [Worktrees](worktrees.md)
- [GitHub picker](../tmux/github-picker.md)
