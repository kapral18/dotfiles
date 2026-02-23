# Git And Identity

Back: [`docs/categories/index.md`](index.md)

This setup is built around the idea that:

- private keys should not live on disk
- git identity should switch automatically based on where you're working

The mechanics are implemented through a combination of 1Password's SSH agent,
`~/.ssh/config`, and git's `includeIf` support.

## SSH Agent

SSH is wired to use the 1Password agent socket:

- `home/private_dot_ssh/private_executable_config`

The 1Password agent key set is configured via:

- `home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl`

Installed as:

- `~/.ssh/config`

## Public Keys On Disk

Git is configured to use SSH "public key" paths as identity selectors. The
matching private keys are held by 1Password.

Relevant templates:

- `home/private_dot_ssh/primary_public_key.pub.tmpl`
- `home/private_dot_ssh/secondary_public_key.pub.tmpl`

## Git Config

Primary git config:

- `home/private_readonly_dot_gitconfig.tmpl`

Installed as:

- `~/.gitconfig`

Work override (included conditionally):

- `home/work/private_dot_gitconfig.tmpl`

The primary config uses `includeIf "gitdir:~/work/"` on non-work machines so
repos under `~/work/` automatically use the secondary identity.

## GitHub CLI + Dashboards

This setup configures a few GitHub-related tools:

- GitHub CLI config directory: `home/dot_config/exact_private_gh/` (private)
- `gh-dash` config: `home/dot_config/exact_gh-dash/config.yml`
- Managed extensions hook: `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`

Git TUIs:

- `gitui` config: `home/dot_config/exact_gitui/`
- `lazygit` config: `home/dot_config/exact_lazygit/config.yml`
- `tig` config: `home/dot_config/exact_tig/`

## Signing

Git commit signing is configured for SSH signing, using the 1Password signing
helper:

- `home/private_readonly_dot_gitconfig.tmpl`
- `home/private_dot_ssh/private_executable_allowed_signers.tmpl`

## Verify

See which identity is currently active:

```bash
git config --get user.name
git config --get user.email
git config --get core.sshCommand
```

If you are in a repo under `~/work/` on a non-work machine, you should see the
secondary identity.

## Troubleshooting

- Identity did not switch:
  - verify repo path (`~/work/...` for `includeIf`-based work identity on
    non-work machines).
  - check effective config origin:

```bash
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
```

- SSH auth problems:
  - verify `SSH_AUTH_SOCK` points to 1Password agent socket.
  - verify required key is enabled in 1Password agent config.

## Related

- Identity switching: [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- Worktrees: [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
- Security model: [`docs/categories/security-and-secrets.md`](security-and-secrets.md)
