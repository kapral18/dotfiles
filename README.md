# dotfiles

Personal macOS setup managed with [chezmoi](https://www.chezmoi.io/): Fish, Neovim, herdr, packages, and comma-prefixed commands.

## Setup

Install `chezmoi` and sign in to 1Password first; templates use it for SSH keys and secrets. Preview before applying to an existing machine:

```sh
chezmoi init kapral18
chezmoi diff
chezmoi apply --dry-run --verbose
chezmoi apply
```

Apply hooks install packages, change the login shell and macOS settings, and **remove Homebrew packages absent from the Brewfile**. Review [`home/.chezmoiscripts/`](home/.chezmoiscripts/) before applying. Directories marked `exact_` can delete unmanaged files in their deployed directory. Back up existing configuration first.

To install chezmoi and apply immediately on a new machine:

```sh
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

## Use and maintenance

- Edit sources under [`home/`](home/), not their deployed copies. Run `chezmoi diff` before `chezmoi apply`.
- Find custom commands in [`home/exact_bin/`](home/exact_bin/); run `,<name> --help` for usage. Command internals live in [`home/exact_lib/`](home/exact_lib/).
- Package lists live in [`home/.chezmoitemplates/brews/`](home/.chezmoitemplates/brews/) and `home/readonly_dot_default-*`; tool versions live in [`home/dot_config/mise/`](home/dot_config/mise/).
- For setup failures, run `chezmoi doctor`, inspect the failing hook in `home/.chezmoiscripts/`, fix the source, then preview and reapply. Reverting source files does not undo installed packages, deletions, or macOS settings; restore backups or reverse those changes separately.

Repository editing and checks: [CONTRIBUTING.md](CONTRIBUTING.md). Agent rules: [AGENTS.md](AGENTS.md).
