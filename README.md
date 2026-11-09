# dotfiles

Personal macOS setup managed with [chezmoi](https://www.chezmoi.io/): Fish, Neovim, herdr, packages, and comma-prefixed commands.

## Before you apply

Applying is destructive. Back up existing configuration first.

- Hooks in [`home/.chezmoiscripts/`](home/.chezmoiscripts/) install packages, change the login shell and macOS settings, and **remove Homebrew packages absent from the Brewfile**.
- `exact_` directories delete unmanaged files in their deployed directory.

## Install on a new Mac

Run in Terminal (requires administrator access):

```sh
sh -c "$(curl -fsLS https://get.chezmoi.io/lb)" -- -b "$HOME/.local/bin" init --use-builtin-git=true --apply kapral18
```

The command installs chezmoi into `~/.local/bin`, prepares [1Password and GitHub](home/.bootstrap.sh), asks setup questions, then applies. Expect these stops:

- **Full Disk Access.** If the terminal cannot change protected macOS settings, setup opens Full Disk Access settings and exits. Allow the terminal, reopen it, and rerun the command.
- **Administrator password.** Asked when installing Homebrew, and once more for the apply phase.
- **1Password.** Sign in, enable CLI integration and the SSH agent, then press Enter. You can then copy setup answers, such as your public SSH key, from 1Password.
- **GitHub CLI.** Signs in through the browser if signed out.
- **App Store.** If a Brewfile App Store app is missing, setup opens the App Store and waits for you to sign in.

A failed check stops setup: fix the prerequisite and rerun the same command. Reruns skip finished steps and reuse saved answers.

## Install on a Mac with its own configuration

On a Mac that already has dotfiles or settings you care about, but not this repo, apply in steps and review what chezmoi would overwrite. Install `chezmoi` and configure 1Password first; `chezmoi init` runs the same 1Password and GitHub setup.

```sh
chezmoi init kapral18
chezmoi diff
chezmoi apply --dry-run --verbose
chezmoi apply
```

## Rerun on a Mac that already uses this repo

Rerunning the install command fetches the existing clone in `~/.local/share/chezmoi` first; a plain `chezmoi init` without `kapral18` never fetches. A clean clone behind GitHub is fast-forwarded, then setup stops so you can rerun on the latest version. Local changes, or local commits on a clone that is also behind, stop setup without touching the clone. A clone older than this check needs deleting once: `rm -rf ~/.local/share/chezmoi`.

## Use and maintenance

- Edit sources under [`home/`](home/), not their deployed copies. Run `chezmoi diff` before `chezmoi apply`.
- Custom commands live in [`home/exact_bin/`](home/exact_bin/); run `,<name> --help` for usage. Internals live in [`home/exact_lib/`](home/exact_lib/).
- Package lists live in [`home/.chezmoitemplates/brews/`](home/.chezmoitemplates/brews/) and `home/readonly_dot_default-*`; tool versions live in [`home/dot_config/mise/`](home/dot_config/mise/).

## Recovery

- For setup failures, run `chezmoi doctor`, inspect the failing hook in `home/.chezmoiscripts/`, fix the source, then preview and reapply.
- Reverting source files does not undo installed packages, deletions, or macOS settings. Restore backups or reverse those changes separately.

Repository editing and checks: [CONTRIBUTING.md](CONTRIBUTING.md). Agent rules: [AGENTS.md](AGENTS.md).
