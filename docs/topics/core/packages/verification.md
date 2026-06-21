---
sidebar_position: 3
title: Verification and troubleshooting
---

# Verification and troubleshooting

Use the smallest check that proves the package source and hook converged.

## High-signal checks

```bash
brew bundle check --global
mise ls --current
cargo install --list
uv tool list
yarn global list
gh extension list
```

For one tool:

```bash
command -v <tool>
<tool> --version
```

## If a package disappeared

| Check                                             | Why                                                                 |
| ------------------------------------------------- | ------------------------------------------------------------------- |
| Is it declared in the right source list/template? | declarative cleanup removes undeclared packages                     |
| Did the corresponding hook run?                   | `run_onchange` hashes decide whether a hook re-runs                 |
| Is it scoped to the current `.isWork` profile?    | template branches can hide personal/work-only tools                 |
| For Homebrew, is it in the assembled Brewfile?    | cleanup uses `~/.Brewfile`, not the partial you edited in isolation |
| For Go, did this tooling install it?              | the state ledger prevents deleting hand-installed binaries          |

## Rollback pattern

For managers with cleanup support:

1. Remove the declaration from the source list.
2. Run `chezmoi apply`.
3. Run the manager-specific verification command.

For managers without cleanup support, removal from the list only stops future installs. Check [Reconcile behavior](reconcile-behavior.md) and follow the recipe-specific manual uninstall step, such as `gem uninstall <gemname>` for Ruby gems.

For custom DMG apps and single-file binaries, manually remove residual app/binary files only when the installer cannot safely do it.
