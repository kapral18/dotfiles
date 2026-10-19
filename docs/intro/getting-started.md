---
sidebar_position: 1
---

# Getting Started

This setup is managed with `chezmoi`. The basic loop is:

1. Initialize from GitHub
2. Review the changes `chezmoi` wants to apply
3. Apply them (which can trigger install hooks)

Chezmoi renders the source files under `home/` into your home directory.

## Preconditions

- Use macOS with **1Password** installed and signed in for SSH keys and secrets. Using another secret manager requires template changes.
- Install `chezmoi` before using the preview commands below; the [bootstrap command](#one-liner-bootstrap-what-the-readme-uses) also installs it.
- Applying the setup installs tools, changes your login shell and macOS preferences, and can remove Homebrew packages not listed in the Brewfile. Inspect the hooks before applying it to an existing machine.

## Safe Preview Flow

Review the file changes before applying:

```bash
chezmoi init kapral18
chezmoi diff
```

You can also do a dry-run apply (no changes):

```bash
chezmoi apply --dry-run --verbose
```

If the diff looks good:

```bash
chezmoi apply
```

## One-Liner Bootstrap (What The README Uses)

The repo root `README.md` uses the upstream `chezmoi` installer + init in one line:

```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

This command applies the setup immediately. Use the preview flow first if you need to inspect changes.

## What `chezmoi apply` Can Trigger Here

This setup uses `chezmoi` hooks under [`home/.chezmoiscripts/`](../../home/.chezmoiscripts/). On first run, you should expect:

| Hook                                                    | What it does                                          |
| ------------------------------------------------------- | ----------------------------------------------------- |
| `run_once_before_00-install-xcode.sh`                   | Xcode Command Line Tools install + license acceptance |
| `run_once_after_01-install-brew.sh`                     | Homebrew install                                      |
| `run_once_after_02-install-fish.sh`                     | Fish install + switching your login shell             |
| `run_onchange_after_03-install-brew-packages.fish.tmpl` | Brew bundle install + cleanup                         |
| `run_onchange_after_04-update-fish-packages.fish.tmpl`  | Fish packages update                                  |

There are also hooks that manage language/tool versions and global packages (mise, cargo, go, gems, pnpm, uv) and some macOS preferences.

## Init Prompts

During init/apply, `chezmoi` will prompt for values via [`home/.chezmoi.toml.tmpl`](../../home/.chezmoi.toml.tmpl):

- email / SSH public key
- PGP cache TTL

Those values are used by templates (for example: git identity and SSH signing).
