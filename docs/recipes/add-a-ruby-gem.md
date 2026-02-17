# Add A Ruby Gem

Back: [`docs/recipes/index.md`](index.md)

Global Ruby gems are managed via a list.

## Preconditions

- Ruby and `gem` are installed.
- You verified the gem name.

## Steps

1. Add the gem name to:

   - `home/readonly_dot_default-gems`

   This installs as `~/.default-gems`.

2. Apply:

   ```bash
   chezmoi apply
   ```

Hook:

- `home/.chezmoiscripts/run_onchange_after_05-update-gems.sh.tmpl`

## Verification

```bash
gem list --local | rg '^<gemname> '
```

## Rollback / Undo

1. Remove the gem from `home/readonly_dot_default-gems`.
2. Re-apply:

```bash
chezmoi apply
```
