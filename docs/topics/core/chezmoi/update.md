---
sidebar_position: 1
---

# Updating

## Quick: One Command

```bash
,update
```

This pulls dotfiles, updates package managers (Homebrew, mise, Cargo, pnpm, Gems, Go, uv, manual packages), and reports what changed.

### Useful flags

| Flag                | Effect                                              |
| ------------------- | --------------------------------------------------- |
| `--dry-run` / `-n`  | Preview what would happen without changing anything |
| `--only brew,pnpm`  | Update only the listed categories                   |
| `--skip cargo,gems` | Update everything except the listed categories      |
| `--verbose` / `-v`  | Show extra detail and per-step timings              |

Categories: `dotfiles`, `brew`, `gh`, `mise`, `cargo`, `pnpm`, `gems`, `go`, `uv`, `manual`.

Each step's output is relayed through a prefixed indent. The relay flushes partial lines, so an interactive prompt that ends without a newline (for example chezmoi's `... has changed since chezmoi last wrote it [overwrite,all-overwrite,skip,quit]`) appears within about 0.2s and can be answered in place; the child keeps the terminal as stdin. Earlier the output went through `sed`, which held such prompts until a newline arrived, so the run looked stalled until Ctrl-C.

When multiple package categories run in parallel, `,update` launches [mprocs](https://github.com/pvolok/mprocs) to give each step its own scrollable terminal pane. Press `q` to exit after reviewing the logs. If `mprocs` is not installed, steps run sequentially instead. Manual packages run after the parallel package phase so non-Homebrew apps and release assets converge after Homebrew cleanup.

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
