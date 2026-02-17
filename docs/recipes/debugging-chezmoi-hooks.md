# Debugging Chezmoi Hooks

Back: [`docs/recipes/index.md`](index.md)

When `chezmoi apply` fails, the most useful piece of information is the exact
hook script that failed.

## Preconditions

- You can reproduce the failure locally.
- You are running commands from the dotfiles source repo.

## Steps

1. Re-run apply and capture the failing script path:

```bash
chezmoi apply
```

2. Review diff/input templates:

```bash
chezmoi diff
```

3. If the failing script is a template, render it:

```bash
chezmoi execute-template < home/.chezmoiscripts/<script>.tmpl
```

4. Run the failing script directly to isolate environment/dependency issues.

## Identify The Script

The failing script path appears in `chezmoi apply` output.

## Common Causes

- missing dependency (brew/asdf/gh/op/uv)
- auth required (GitHub CLI, 1Password CLI)
- a script expects sudo access

## Verification

- The failing command reproduces outside `chezmoi apply`.
- After fixing root cause, `chezmoi apply` exits successfully.

Note: many hooks depend on binaries that are installed by earlier hooks
(Homebrew, ASDF, etc.). If a hook fails with "command not found", check whether
the earlier install hooks completed.

## Rollback / Undo

- Revert the recent script/template changes in your working tree.
- Re-run:

```bash
chezmoi apply
```
