# FAQ

Back: [`docs/index.md`](index.md)

## Will this overwrite my existing dotfiles?

`chezmoi` will prompt if a target file was modified since chezmoi last wrote it.
Use a preview first:

```bash
chezmoi diff
chezmoi apply --dry-run --verbose
```

## Do I need to use Neovim/tmux to use this setup?

No. You can adopt slices.

Start with:

- Git identity switching + 1Password SSH agent
- Homebrew package lists

See [`docs/adoption-paths.md`](adoption-paths.md).

## Does this work without 1Password?

Not really.

This setup assumes 1Password provides:

- SSH agent keys (no private keys on disk)
- 1Password CLI access for some bootstrap steps

See [`docs/categories/security-and-secrets.md`](categories/security-and-secrets.md).

## Why does applying packages remove things?

Some hooks are intentionally declarative.

For example, the Brewfile hook runs `brew bundle cleanup --global --force`, so
packages not in the Brewfile can be removed.

See:

- [`docs/categories/packages.md`](categories/packages.md)

## How do I update?

Use:

```bash
chezmoi update
```

See [`docs/recipes/updating.md`](recipes/updating.md).
