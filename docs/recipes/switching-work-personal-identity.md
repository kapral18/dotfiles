# Switching Work vs Personal Identity

Back: [`docs/recipes/index.md`](index.md)

This setup uses two related mechanisms:

- git identity switching via `includeIf` (based on working directory)
- password-store switching via `PASSWORD_STORE_DIR`

## Preconditions

- Dotfiles are applied.
- On non-work machines, `~/.password-store-work` exists if you use `wpass`.

## Steps

1. For git identity switching, use directory placement (`~/work/...` vs personal paths).
2. For password-store switching:

```bash
wpass
ppass
```

## Git Identity Switching

On non-work machines, repos under `~/work/` load a secondary git config.

Relevant files:

- `home/private_readonly_dot_gitconfig.tmpl` (primary, installed as `~/.gitconfig`)
- `home/work/private_dot_gitconfig.tmpl` (work override)

In practice: if you clone a repo under `~/work/...`, commits and SSH identity
selection switch automatically.

## Password Store Switching

On non-work machines, fish defines helpers:

- `wpass` sets `PASSWORD_STORE_DIR=~/.password-store-work`
- `ppass` unsets `PASSWORD_STORE_DIR` (defaulting back to `~/.password-store`)

Setup script:

- `home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`

## Verification

Git:

```bash
git config --get user.email
git config --get core.sshCommand
```

Password store:

```bash
echo "$PASSWORD_STORE_DIR"
pass ls
```

## Rollback / Undo

- Reset password-store selection:

```bash
ppass
```

- Move repo out of `~/work/` (or into it) to change `includeIf` matching.
- Re-check effective config:

```bash
git config --show-origin --get user.email
```
