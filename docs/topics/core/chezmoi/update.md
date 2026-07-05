---
sidebar_position: 1
---

# Updating

## Quick: One Command

```bash
,update
```

This pulls dotfiles, updates package managers (Homebrew, mise, Cargo, yarn, Gems, Go, uv, manual GitHub releases), checks self-updating cask drift, and reports what changed.

### Useful flags

| Flag                | Effect                                              |
| ------------------- | --------------------------------------------------- |
| `--dry-run` / `-n`  | Preview what would happen without changing anything |
| `--only brew,yarn`  | Update only the listed categories                   |
| `--skip cargo,gems` | Update everything except the listed categories      |
| `--verbose` / `-v`  | Show extra detail and per-step timings              |

Categories: `dotfiles`, `brew`, `gh`, `mise`, `cargo`, `yarn`, `gems`, `go`, `uv`, `manual`, `selfupdaters`.

When multiple package categories run in parallel, `,update` launches [mprocs](https://github.com/pvolok/mprocs) to give each step its own scrollable terminal pane. Press `q` to exit after reviewing the logs. If `mprocs` is not installed, steps run sequentially instead. The `selfupdaters` category runs after Homebrew and the parallel package phase so it can inspect final cask state.

`selfupdaters` enumerates installed Homebrew casks with `auto_updates true`. It reports unsupported casks and heals only casks with a verified adapter when a manual reinstall or forced bundle path has reasserted an older Homebrew artifact over app-owned state.

## Manual Steps (if you prefer granular control)

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
,doctor          # full ecosystem health check
chezmoi status
chezmoi diff
```

If package-related hooks ran, spot-check expected package managers:

```bash
brew bundle check --global
mise ls --current
```

## Rollback / Undo

- If a specific repo change caused issues, revert that change in the source repo.
- Re-apply the previous known-good state:

```bash
chezmoi diff
chezmoi apply
```
