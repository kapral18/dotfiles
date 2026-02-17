# Shell: Fish

Back: [`docs/categories/index.md`](index.md)

Fish is the primary shell in this setup.

Zsh and Bash are also configured so the environment is usable even if you don't
switch your login shell.

Relevant files:

- Bash: `home/readonly_dot_bashrc.tmpl`, `home/readonly_dot_bash_profile`
- Zsh: `home/readonly_dot_zshrc.tmpl`, `home/readonly_dot_zprofile`
- POSIX profile: `home/readonly_dot_profile.tmpl`

## Core Config

- Template: `home/dot_config/fish/config.fish.tmpl`

Notable responsibilities in this file:

- sets editor to `nvim`
- exports `SSH_AUTH_SOCK` for 1Password
- configures Homebrew path via `homebrewPrefix` prompt data
- loads API keys from `pass` into environment variables
- defines `bdlocal` wrapper for Beads
- adds `~/bin` and `~/.local/bin` to PATH on login

It also initializes a few tools if present:

- Starship prompt (`home/dot_config/starship.toml`)
- zoxide (smarter `cd`)
- fzf integration via `PatrickF1/fzf.fish`

## Startup Model

Fish setup in this repo is split by shell mode:

- Login shell:
  - Adds Homebrew, `~/.local/bin`, `~/bin`, and ASDF shims to `PATH`.
- Interactive shell:
  - Adds aliases (`g`, `v`, `c`, `t`, and others).
  - Initializes prompt/tools (`starship`, `zoxide`, `navi` when installed).

If a command works in one terminal but not another, check whether the shell is
login vs non-login.

## Verification Workflows

### Confirm effective shell + path

```bash
echo "$SHELL"
fish --version
echo "$PATH"
```

### Confirm key runtime wiring

```bash
echo "$SSH_AUTH_SOCK"
echo "$BEADS_DIR"
type -a bdlocal
```

### Confirm API key loading behavior

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

## Ignore Globs (fd / ripgrep / fzf)

This setup keeps a shared ignore-globs file used by `fd`/`fzf` defaults:

- `home/dot_config/ignore-globs`

In fish, it's wired via:

- `FD_DEFAULT_OPTS` in `home/dot_config/fish/config.fish.tmpl`

## Password-Store Switching (Non-Work Machines)

Two helper functions are defined in fish:

- `wpass`: points `PASSWORD_STORE_DIR` at `~/.password-store-work`
- `ppass`: unsets `PASSWORD_STORE_DIR` (back to default store)

Verification:

```bash
wpass
echo "$PASSWORD_STORE_DIR"
ppass
echo "$PASSWORD_STORE_DIR"
```

## Fish Plugins

Fish plugins are managed with Fisher:

- Plugin list: `home/dot_config/fish/fish_plugins`
- Hook: `home/.chezmoiscripts/run_onchange_after_04-update-fish-packages.fish.tmpl`

## Troubleshooting

- `command not found` for `,commands`:
  - check `~/bin` in `PATH`
  - run `chezmoi apply` again
- Missing API keys:
  - verify `pass` is installed and unlocked
  - verify the expected secret paths exist in your password store
- Wrong password store selected:
  - run `ppass` to clear `PASSWORD_STORE_DIR`
- Beads DB points to wrong repo:
  - `cd` into the correct git repo and re-run `echo "$BEADS_DIR"`

## Making Fish Your Login Shell

The setup script installs fish and will attempt to set it as your main shell:

- `home/.chezmoiscripts/run_once_after_02-install-fish.sh`

## Related

- Switching identity: [`docs/recipes/switching-work-personal-identity.md`](../recipes/switching-work-personal-identity.md)
- Beads task tracking: [`docs/recipes/beads-task-tracking.md`](../recipes/beads-task-tracking.md)
- Packages: [`docs/categories/packages.md`](packages.md)
- Security and secrets: [`docs/categories/security-and-secrets.md`](security-and-secrets.md)
