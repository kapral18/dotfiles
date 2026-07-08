---
sidebar_position: 10
---

# Add A Homebrew Package

Homebrew packages are managed declaratively. The deployed `~/.Brewfile` is a single file, but in the chezmoi source it is split into per-category, per-profile partials under [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews) so it stays explorable:

- `brews/shared/NN-<category>.brewfile` — installed on every machine.
- `brews/personal/NN-<category>.brewfile` — installed when `.isWork` is `false`.
- `brews/work/NN-<category>.brewfile` — installed when `.isWork` is `true` (none exist yet; create as needed).

File roles:

| File / convention                                                                         | Role                                                             |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| profile directory                                                                         | decides machine scope; not an inline `{{ if }}` inside a partial |
| [`brews/_assemble.brewfile`](../../../../home/.chezmoitemplates/brews/_assemble.brewfile) | index of category banners and `includeTemplate` calls            |
| [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl)          | renders the assembler into `~/.Brewfile`                         |

## Preconditions

- You know whether the package is a formula or cask.
- You verified the package name with:

```bash
brew info <formula-or-cask>
```

## Steps

1. Pick the category and profile, then edit the matching partial under [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews):
   - Every machine: `brews/shared/NN-<category>.brewfile`.
   - Personal-only: `brews/personal/NN-<category>.brewfile`.
   - Work-only: `brews/work/NN-<category>.brewfile`.

2. Add the entry (`brew "<formula>"` or `cask "<cask>"`, with its comment/URL) to that file.

   If the category file does not exist yet:

   | Step           | Detail                                                                                                                                                              |
   | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | Create partial | reuse the `NN-<category>` ordinal+slug of the matching `shared/` sibling                                                                                            |
   | Wire assembler | add `{{ includeTemplate "brews/<profile>/NN-<category>.brewfile" . }}` to [`brews/_assemble.brewfile`](../../../../home/.chezmoitemplates/brews/_assemble.brewfile) |
   | Work profile   | place work entries inside a `{{ if eq .isWork true }}` block                                                                                                        |

3. Apply:

```bash
chezmoi apply
```

The brew hook is:

- [`home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`](../../../../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl)

It runs `brew bundle cleanup --global --force` and `brew bundle --global --no-upgrade`, so the assembled Brewfile is the source-of-truth (anything not listed is uninstalled). Its `run_onchange` hash is computed from the rendered assembler, so editing any partial re-triggers the hook.

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

1. Remove the package entry from its `home/.chezmoitemplates/brews/<profile>/NN-<category>.brewfile` partial.
2. Re-apply:

```bash
chezmoi apply
```
