# dotfiles

Personal macOS setup managed with [chezmoi](https://www.chezmoi.io/): Fish, Neovim, herdr, packages, and comma-prefixed commands.

## Setup

Apply hooks install packages, change the login shell and macOS settings, and **remove Homebrew packages absent from the Brewfile**. Review [`home/.chezmoiscripts/`](home/.chezmoiscripts/) before applying. Directories marked `exact_` can delete unmanaged files in their deployed directory. Back up existing configuration first.

On a new Mac, sign in to the App Store first: the Brewfile installs App Store apps through `mas`, and a failed `mas` install stops the apply. Then run this in Terminal (requires administrator access):

```sh
sh -c "$(curl -fsLS https://get.chezmoi.io/lb)" -- -b "$HOME/.local/bin" init --use-builtin-git=true --apply kapral18
```

The installer installs chezmoi into `~/.local/bin`. During `init`, chezmoi [prepares 1Password](home/.install-1password.sh) before asking setup questions, so you can copy answers such as your public SSH key from it. If Homebrew and the app are installed, CLI authentication succeeds and the 1Password SSH agent offers keys, setup returns without installing packages, opening the app or showing setup prompts. Otherwise, it repairs missing prerequisites, reinstating app/CLI files even when Homebrew still records their casks as installed, then guides any remaining sign-in and developer settings. Enable CLI integration and the SSH agent, then press Enter. Failed installation or readiness checks stop initialization. Fix the prerequisite and rerun the command. Initialization reuses saved identity answers and keeps PATH entries unique. Ordinary `diff` and `apply` commands skip this setup. `init` does not update an existing clone: if an earlier attempt on a new Mac left `~/.local/share/chezmoi`, delete it before rerunning the command.

For manual setup, install `chezmoi` and configure 1Password first; `chezmoi init` runs the same 1Password setup. Preview before applying to an existing machine:

```sh
chezmoi init kapral18
chezmoi diff
chezmoi apply --dry-run --verbose
chezmoi apply
```

## Use and maintenance

- Edit sources under [`home/`](home/), not their deployed copies. Run `chezmoi diff` before `chezmoi apply`.
- Find custom commands in [`home/exact_bin/`](home/exact_bin/); run `,<name> --help` for usage. Command internals live in [`home/exact_lib/`](home/exact_lib/).
- Package lists live in [`home/.chezmoitemplates/brews/`](home/.chezmoitemplates/brews/) and `home/readonly_dot_default-*`; tool versions live in [`home/dot_config/mise/`](home/dot_config/mise/).
- For setup failures, run `chezmoi doctor`, inspect the failing hook in `home/.chezmoiscripts/`, fix the source, then preview and reapply. Reverting source files does not undo installed packages, deletions, or macOS settings; restore backups or reverse those changes separately.

Repository editing and checks: [CONTRIBUTING.md](CONTRIBUTING.md). Agent rules: [AGENTS.md](AGENTS.md).
