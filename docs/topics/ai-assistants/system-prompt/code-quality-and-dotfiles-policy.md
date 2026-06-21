---
sidebar_position: 5
title: Code-quality and dotfiles policy
---

# Code-quality and dotfiles policy

The SOP's coding rules are intentionally conservative: minimal edit scope, no unrequested compatibility, and verification before completion.

## Code-change rules

| Rule                  | Effect                                                            |
| --------------------- | ----------------------------------------------------------------- |
| Minimal edit scope    | no unrelated cleanup or behavior removal                          |
| Simplicity discipline | no abstractions/features beyond the ask                           |
| Artifact necessity    | prove a new file/config/dependency has a runtime/tooling consumer |
| Dead-code handling    | remove only dead code introduced by the change unless asked       |
| Type safety           | avoid broad casts and success-shaped fallbacks                    |

## Dotfiles overlay

| Concern                   | Rule                                                                                |
| ------------------------- | ----------------------------------------------------------------------------------- |
| Chezmoi source of truth   | resolve target -> `chezmoi source-path` -> edit `home/**` source                    |
| Read-only `$HOME` targets | investigate `readonly_` source; never `chmod` deployed output                       |
| Validation                | run `make check` then `make fmt` after repo changes                                 |
| Docs hygiene              | behavior changes under `home/`, `scripts/`, or `tools/` update docs and `.mermaids` |
| Shell scripts             | shell stays glue; non-trivial logic goes under `scripts/` helpers                   |
| `~/bin` commands          | command updates require fish completion and docs/catalog updates                    |
