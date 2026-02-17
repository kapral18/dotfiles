# Security And Secrets

Back: [`docs/categories/index.md`](index.md)

This setup assumes secrets live outside the git repo:

- SSH private keys: in 1Password (via the 1Password SSH agent)
- API tokens and small secrets: in `pass` (password-store)

## 1Password

The 1Password SSH agent is the expected SSH identity provider.

- SSH config: `home/private_dot_ssh/private_executable_config`
- Git wiring: `home/private_readonly_dot_gitconfig.tmpl`

The 1Password SSH agent itself is configured via:

- `home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl`

This controls which 1Password items (ssh keys) are available to the agent based
on `isWork`.

## GPG Agent (Pinentry + Cache TTL)

This setup configures `gpg-agent` to:

- use `pinentry-mac` on macOS
- set a cache TTL based on the `pgpCacheTtl` prompt

Relevant files:

- Prompts: `home/.chezmoi.toml.tmpl`
- Template: `home/private_dot_gnupg/gpg-agent.conf.tmpl`

## Password Store (`pass`)

Fish loads several API keys from `pass` if they are not already set in the
environment:

- `home/dot_config/fish/config.fish.tmpl`

On first setup, `pass` is installed and the password store is cloned via:

- `home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`

That script also imports PGP keys (via `op read`) and adjusts trust for the
primary identity.

## Work vs Personal Password Stores

On non-work machines, fish defines helpers to switch the `PASSWORD_STORE_DIR`:

- `wpass` selects a work password store
- `ppass` resets back to the default

Implementation:

- `home/dot_config/fish/config.fish.tmpl`

On first setup, the pass bootstrap script attempts to clone both password-store
repositories on non-work machines:

- personal store -> `~/.password-store`
- work store (optional) -> `~/.password-store-work`

See:

- `home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`

## Verification And Troubleshooting

Check security wiring:

```bash
echo "$SSH_AUTH_SOCK"
git config --get core.sshCommand
gpgconf --list-options gpg-agent | rg -i 'default-cache-ttl|max-cache-ttl'
```

Check password-store switching:

```bash
wpass
echo "$PASSWORD_STORE_DIR"
ppass
echo "$PASSWORD_STORE_DIR"
```

If secrets are missing at runtime:

- confirm `pass` is initialized and unlocked.
- confirm secret paths referenced in `home/dot_config/fish/config.fish.tmpl`
  exist.
- confirm work store clone exists at `~/.password-store-work` on non-work
  machines if using `wpass`.

## Related

- Git + identity: [`docs/categories/git-and-identity.md`](git-and-identity.md)
- Switching identity: [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- AI and assistants: [`docs/categories/ai-and-assistants.md`](ai-and-assistants.md)
