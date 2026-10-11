---
sidebar_position: 10
---

# Add A Homebrew Package

Homebrew packages are managed declaratively. The deployed `~/.Brewfile` is a single file, but in the chezmoi source it is split into per-category partials (`brews/NN-<category>.brewfile`) under [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews) so it stays explorable.

File roles:

| File / convention                                                                         | Role                                                  |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| [`brews/_assemble.brewfile`](../../../../home/.chezmoitemplates/brews/_assemble.brewfile) | index of category banners and `includeTemplate` calls |
| [`home/readonly_dot_Brewfile.tmpl`](../../../../home/readonly_dot_Brewfile.tmpl)          | renders the assembler into `~/.Brewfile`              |

## Preconditions

- You know whether the package is a formula or cask.
- You verified the package name with:

```bash
brew info <formula-or-cask>
```

## Steps

1. Pick the category, then edit the matching partial under [`home/.chezmoitemplates/brews/`](../../../../home/.chezmoitemplates/brews): `brews/NN-<category>.brewfile`.

2. Add the entry (`brew "<formula>"` or `cask "<cask>"`, with its comment/URL) to that file.

   Non-official taps are declared as `tap "<owner>/<tap>", trusted: true` next to the entry that needs them. `brew bundle` writes that into Homebrew's trust store (`~/.config/homebrew/trust.json`) before loading any formula, so no `brew trust` run and no `HOMEBREW_NO_REQUIRE_TAP_TRUST` override is needed.

   If the category file does not exist yet:

   | Step           | Detail                                                                                                                                                    |
   | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | Create partial | use the next free `NN-<category>` ordinal+slug                                                                                                            |
   | Wire assembler | add `{{ includeTemplate "brews/NN-<category>.brewfile" . }}` to [`brews/_assemble.brewfile`](../../../../home/.chezmoitemplates/brews/_assemble.brewfile) |

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

1. Remove the package entry from its `home/.chezmoitemplates/brews/NN-<category>.brewfile` partial.
2. Re-apply:

```bash
chezmoi apply
```
