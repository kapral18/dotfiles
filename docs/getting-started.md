# Getting Started

Back: [`docs/index.md`](index.md)

This setup is managed with `chezmoi`. The basic loop is:

1. Initialize from GitHub
2. Review the changes `chezmoi` wants to apply
3. Apply them (which can trigger install hooks)

If you are coming from VSCode/JetBrains and do not live in a terminal: think of `chezmoi` like "dotfiles as code" with a build step.

## Preconditions

**⚠️ Important:** This setup has a hard dependency on 1Password.

- **1Password app** must be installed and signed in. This setup assumes 1Password is the source of truth for SSH keys and many secrets. If you don't use 1Password, you will need to heavily modify the templates.
- Willingness to let the bootstrap scripts install system tooling.

## Safe Preview Flow

The safest way to approach any dotfiles setup is to preview what would change before applying.

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

Use this once you're comfortable with what the scripts do. The preview flow is still recommended for first-time adopters.

## What `chezmoi apply` Can Trigger Here

This setup uses `chezmoi` hooks under [`home/.chezmoiscripts/`](../home/.chezmoiscripts/). On first run, you should expect:

| Hook                                                    | What it does                                          |
| ------------------------------------------------------- | ----------------------------------------------------- |
| `run_once_before_00-install-xcode.sh`                   | Xcode Command Line Tools install + license acceptance |
| `run_once_after_01-install-brew.sh`                     | Homebrew install                                      |
| `run_once_after_02-install-fish.sh`                     | Fish install + switching your login shell             |
| `run_onchange_after_03-install-brew-packages.fish.tmpl` | Brew bundle install + cleanup                         |
| `run_onchange_after_04-update-fish-packages.fish.tmpl`  | Fish packages update                                  |

There are also hooks that manage language/tool versions and global packages (ASDF, cargo, go, gems, npm, uv) and some macOS preferences.

## Work vs Personal Machines

During init/apply, `chezmoi` will prompt for values via [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl):

- `isWork` (drives conditional config)
- emails / SSH public keys
- PGP cache TTL

Those values are used by templates (for example: git identity switching and conditional package lists).
