---
sidebar_position: 3
---

# New Machine Bootstrap

On a new machine, the first `chezmoi apply` can do more than "copy dotfiles".

## Preconditions

- `chezmoi` is installed.
- You can authenticate where required (GitHub, 1Password, sudo).
- You are ready for first-run installs (Xcode CLT, Homebrew, shells, package hooks).

## Steps

1. Initialize from remote:

```bash
chezmoi init kapral18
```

1. Preview:

```bash
chezmoi diff
```

1. Apply:

```bash
chezmoi apply
```

## What To Expect

- Xcode Command Line Tools install + license acceptance: [`home/.chezmoiscripts/run_once_before_00-install-xcode.sh`](../../home/.chezmoiscripts/run_once_before_00-install-xcode.sh)
- Homebrew install: [`home/.chezmoiscripts/run_once_after_01-install-brew.sh`](../../home/.chezmoiscripts/run_once_after_01-install-brew.sh)
- Fish install + switching login shell: [`home/.chezmoiscripts/run_once_after_02-install-fish.sh`](../../home/.chezmoiscripts/run_once_after_02-install-fish.sh)
- Brew bundle install + cleanup: [`home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`](../../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl)

There are additional "converge" scripts for:

- ASDF plugins and pinned versions
- language tooling (cargo/go/gems/npm/uv)
- GitHub CLI extensions
- macOS defaults (`.osx.core` / `.osx.extra`)

Secrets tooling setup can also run:

- pass + password-store clone + PGP import: [`home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`](../../home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl)

On non-work machines, this script also attempts to clone a second password store into `~/.password-store-work` so `wpass` can switch.

## Verification

```bash
chezmoi doctor
which fish
which brew
```

Spot-check one or two managed files in `$HOME` (for example `~/.gitconfig`, `~/.config/fish/config.fish`).

## Rollback / Undo

- Revert local changes in the source repo if needed.
- Re-run apply after fixing prompt/config issues:

```bash
chezmoi diff
chezmoi apply
```

## If You Get Stuck

Start here:

- [`docs/troubleshooting.md`](../reference/troubleshooting.md)
- [`docs/recipes/debugging-chezmoi-hooks.md`](../topics/core/chezmoi/debug-hooks.md)
