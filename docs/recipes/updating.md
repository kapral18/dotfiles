# Updating

Back: [`docs/recipes/index.md`](index.md)

## Quick: One Command

```bash
,update
```

This pulls dotfiles, updates all package managers (Homebrew, asdf, Cargo, npm,
Gems, Go, uv, manual GitHub releases), and reports what changed.

### Useful flags

| Flag                | Effect                                              |
| ------------------- | --------------------------------------------------- |
| `--dry-run` / `-n`  | Preview what would happen without changing anything |
| `--only brew,npm`   | Update only the listed categories                   |
| `--skip cargo,gems` | Update everything except the listed categories      |
| `--verbose` / `-v`  | Show extra detail and per-step timings              |

Categories: `dotfiles`, `brew`, `gh`, `asdf`, `cargo`, `npm`, `gems`, `go`,
`uv`, `manual`.

When multiple categories run in parallel, `,update` launches
[mprocs](https://github.com/pvolok/mprocs) to give each step its own scrollable
terminal pane. Press `q` to exit after reviewing the logs. If `mprocs` is not
installed, steps run sequentially instead.

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
asdf current
```

## Rollback / Undo

- If a specific repo change caused issues, revert that change in the source
  repo.
- Re-apply the previous known-good state:

```bash
chezmoi diff
chezmoi apply
```
