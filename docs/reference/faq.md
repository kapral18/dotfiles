---
sidebar_position: 3
---

# FAQ

## Will this overwrite my existing dotfiles?

`chezmoi` will prompt if a target file was modified since chezmoi last wrote it. Use a preview first:

```bash
chezmoi diff
chezmoi apply --dry-run --verbose
```

## Do I need to use Neovim/tmux to use this setup?

No. A full apply installs the configured tools, but you can keep using VSCode or JetBrains while learning the terminal workflow.

See [Learning Paths](../intro/learning-paths.md).

## Does this work without 1Password?

Using another secret manager requires template changes. This setup uses 1Password for:

- SSH agent keys (no private keys on disk)
- 1Password CLI access for some bootstrap steps

See [Security And Secrets](../topics/security/security-and-secrets.md).

## Why does applying packages remove things?

Some hooks are intentionally declarative.

For example, the Brewfile hook runs `brew bundle cleanup --global --force`, so packages not in the Brewfile can be removed.

See:

- [Packages](../topics/core/packages/index.md)

## How do I update?

Use:

```bash
chezmoi update
```

See [Updating](../topics/core/chezmoi/update.md).
