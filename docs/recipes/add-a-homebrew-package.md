# Add A Homebrew Package

Back: [`docs/recipes/index.md`](index.md)

Homebrew packages are managed declaratively through a Brewfile template.

## Preconditions

- You know whether the package is a formula or cask.
- You verified the package name with:

```bash
brew info <formula-or-cask>
```

## Steps

1. Edit:

- `home/readonly_dot_Brewfile.tmpl`

2. Add the entry (`brew "<formula>"` or `cask "<cask>"`) in the correct section.

3. Apply:

```bash
chezmoi apply
```

The brew hook is:

- `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`

It runs `brew bundle cleanup --global --force` and `brew bundle --global`, so
your Brewfile should be treated as the source-of-truth.

## Verification

```bash
brew bundle check --global
brew list | rg '<formula-or-cask>'
```

If something unexpected changed:

```bash
chezmoi diff
```

## Rollback / Undo

1. Remove the package entry from `home/readonly_dot_Brewfile.tmpl`.
2. Re-apply:

```bash
chezmoi apply
```
