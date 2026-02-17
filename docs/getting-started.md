# Getting Started

Back: [`docs/index.md`](index.md)

This setup is managed with `chezmoi`. The basic loop is:

1. Initialize from GitHub
2. Review the changes `chezmoi` wants to apply
3. Apply them (which can trigger install hooks)

If you are coming from VSCode/JetBrains and do not live in a terminal: think of
`chezmoi` like "dotfiles as code" with a build step.

## Preconditions

- 1Password app installed and signed in (this setup assumes 1Password is the
  source of truth for SSH keys and a lot of secrets)
- Willingness to let the bootstrap scripts install system tooling

## Safe Preview Flow

The safest way to approach any dotfiles setup is to preview what would change
before applying.

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

The repo root `README.md` uses the upstream `chezmoi` installer + init in one
line:

```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

Use this once you're comfortable with what the scripts do. The preview flow is
still recommended for first-time adopters.

## What `chezmoi apply` Can Trigger Here

This setup uses `chezmoi` hooks under `home/.chezmoiscripts/`. On first run, you
should expect:

- Xcode Command Line Tools install + license acceptance:
  `home/.chezmoiscripts/run_once_before_00-install-xcode.sh`
- Homebrew install:
  `home/.chezmoiscripts/run_once_after_01-install-brew.sh`
- Fish install + switching your login shell:
  `home/.chezmoiscripts/run_once_after_02-install-fish.sh`
- Brew bundle install + cleanup:
  `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`

There are also hooks that manage language/tool versions and global packages
(ASDF, cargo, go, gems, npm, uv) and some macOS preferences.

## Work vs Personal Machines

During init/apply, `chezmoi` will prompt for values via `home/.chezmoi.toml.tmpl`:

- `isWork` (drives conditional config)
- emails / SSH public keys
- PGP cache TTL

Those values are used by templates (for example: git identity switching and
conditional package lists).
