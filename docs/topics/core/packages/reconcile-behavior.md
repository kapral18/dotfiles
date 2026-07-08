---
sidebar_position: 2
title: Reconcile behavior
---

# Reconcile behavior

Each package source has a different convergence model. The important question is whether removed declarations also remove installed tools.

## Manager behavior

| Manager         | Installs / updates                                                   | Removes when deleted from list?                 | Notes                                                                                    |
| --------------- | -------------------------------------------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Homebrew        | `brew bundle --global --no-upgrade`                                  | Yes, via `brew bundle cleanup --global --force` | assembled Brewfile is authoritative; installs missing only (upgrades owned by `,update`) |
| mise            | `mise install --yes`, then `mise reshim`                             | No cleanup of old runtimes by this hook         | respects project `.tool-versions`; Node reads `.nvmrc`                                   |
| Cargo           | installs missing crates                                              | Yes                                             | hook uninstalls crates no longer listed                                                  |
| Go              | installs missing module binaries                                     | Yes, but only binaries this tooling installed   | state ledger at `~/.cache/chezmoi/golang-pkgs-state` protects hand-installed binaries    |
| Ruby gems       | installs listed gems                                                 | No                                              | hook does not uninstall gems removed from the list                                       |
| yarn            | installs missing globals, uninstalls absent globals, upgrades latest | Yes                                             | avoids Yarn v1 staying on old `0.x` ranges                                               |
| uv Python       | installs listed managed Python versions                              | Yes                                             | hook uninstalls managed Python versions absent from `home/readonly_dot_python-version`   |
| uv tools        | installs listed global tools                                         | managed by uv tool hook                         | tool source is `home/readonly_dot_default-uv-tools.tmpl`                                 |
| gh extensions   | installs managed extensions                                          | Yes                                             | hook prunes extensions no longer listed                                                  |
| Custom packages | downloads GitHub release assets, DMGs, or source builds              | Partial                                         | stale launchers/repos are cleaned when safe; dirty source repos are preserved            |

## Notable package decisions

| Decision                                            | Reason                                                                                                                                       |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Homebrew `link: false` for colliding `sem` binaries | GNU `parallel` and Ataraxy semantic-git both expose `sem`; wrappers expose the intended `,parallel` and `,sem` commands                      |
| Pi globals live in yarn                             | `@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, `pi-mcp-adapter`, and `pi-subagents` are kept together in the managed yarn list |
| Custom installer includes `ytsurf`                  | installed outside standard package managers in this setup                                                                                    |
| `git_maven_jar` rows are declarative                | add/update rows clone/build/install; removed clean repos are deleted; dirty stale repos are preserved                                        |

## Where to make changes

| Goal                               | Start here                                 |
| ---------------------------------- | ------------------------------------------ |
| Add or remove a Homebrew package   | [Add a Homebrew package](homebrew.md)      |
| Pin a runtime                      | [Pin a tool version](mise.md)              |
| Add a language-specific CLI        | Cargo / Go / Ruby / yarn / uv recipe pages |
| Add a GitHub release binary or DMG | [Custom packages registry](custom.md)      |
