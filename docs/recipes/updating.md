# Updating

Back: [`docs/recipes/index.md`](index.md)

There are two common update loops:

## Preconditions

- Working tree is in a state you are comfortable updating from.
- You can authenticate to remotes and package registries if needed.

## Steps

### Update Dotfiles From GitHub (Chezmoi)

```bash
chezmoi update
```

This pulls changes from the source repo and applies them.

If you want to preview first:

```bash
chezmoi update --apply=false
chezmoi diff
chezmoi apply
```

### Update Packages

Homebrew itself:

```bash
brew update
brew upgrade
```

Then re-converge your dotfiles (which can run package-management hooks):

```bash
chezmoi apply
```

## Verification

```bash
chezmoi status
chezmoi diff
```

If package-related hooks ran, spot-check expected package managers:

```bash
brew bundle check --global
asdf current
```

## Rollback / Undo

- If a specific repo change caused issues, revert that change in the source repo.
- Re-apply the previous known-good state:

```bash
chezmoi diff
chezmoi apply
```
