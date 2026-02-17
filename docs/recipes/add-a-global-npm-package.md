# Add A Global npm Package

Back: [`docs/recipes/index.md`](index.md)

Global npm packages are managed via a plain list.

## Preconditions

- Node.js/npm are installed (through ASDF in this setup).
- You verified the package name.

## Steps

1. Add the package name to:

   - `home/readonly_dot_default-npm-pkgs`

   This file is installed as `~/.default-npm-pkgs`.

2. Apply dotfiles (which triggers the hook):

   ```bash
   chezmoi apply
   ```

Or run the installer command directly:

- `home/exact_bin/executable_,install-npm-pkgs`

## Verification

```bash
npm --global --silent ls | rg '<package-name>'
```

## What It Does

The installer reads `~/.default-npm-pkgs`, installs missing packages, and then
runs `asdf reshim nodejs`.

## Rollback / Undo

1. Remove the package from `home/readonly_dot_default-npm-pkgs`.
2. Re-apply:

```bash
chezmoi apply
```
