---
sidebar_position: 2
title: Developer workflow
---

# Developer workflow

This slice covers source control, review/readiness tooling, build/test utilities, CI, containers, and code-quality tools.

## Git, GitHub, and branch work

| Tool                                                                                                                                                        | Source                        | Why it is here                                          |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------------------------- |
| [`git`](https://git-scm.com), [`git-lfs`](https://git-lfs.com/), [`gh`](https://cli.github.com/)                                                            | `brew`                        | core Git/GitHub workflow                                |
| [`weave`](https://ataraxy-labs.github.io/weave/)                                                                                                            | `brew`                        | entity-level semantic merge preview/conflict resolution |
| [`sem`](https://github.com/Ataraxy-Labs/sem)                                                                                                                | `brew` tap `ataraxy-labs/tap` | semantic git diff/blame/impact CLI exposed as `,sem`    |
| [`gitui`](https://github.com/gitui-org/gitui), [`lazygit`](https://github.com/jesseduffield/lazygit/), [`tig`](https://jonas.github.io/tig/)                | `brew`                        | terminal Git UIs                                        |
| [`git-absorb`](https://github.com/tummychow/git-absorb)                                                                                                     | `brew`                        | automatically amend fixups into earlier commits         |
| [`git-delta`](https://dandavison.github.io/delta/), [`difftastic`](https://difftastic.wilfred.me.uk/)                                                       | `brew`                        | readable diff renderers                                 |
| [`git-cal`](https://github.com/k4rthik/git-cal), [`git-extras`](https://github.com/tj/git-extras), [`git-redate`](https://github.com/PotatoLabs/git-redate) | `brew`                        | history/statistics and branch maintenance utilities     |
| [`git-brws`](https://crates.io/crates/git-brws)                                                                                                             | `cargo`                       | open/browse git remotes from the terminal               |
| [`bfg`](https://rtyley.github.io/bfg-repo-cleaner/)                                                                                                         | `brew personal`               | destructive repo cleanup tool, personal-only            |

## GitHub CLI extensions

| Extension                                                               | Source         | Why it is here                            |
| ----------------------------------------------------------------------- | -------------- | ----------------------------------------- |
| [`MohamedElashri/gh-cp`](https://github.com/MohamedElashri/gh-cp)       | `gh extension` | copy GitHub objects/metadata from the CLI |
| [`MohamedElashri/gh-rsize`](https://github.com/MohamedElashri/gh-rsize) | `gh extension` | inspect repository size                   |
| [`dlvhdr/gh-dash`](https://github.com/dlvhdr/gh-dash)                   | `gh extension` | GitHub dashboard TUI                      |
| [`gennaro-tedesco/gh-i`](https://github.com/gennaro-tedesco/gh-i)       | `gh extension` | issue workflow helper                     |
| [`gennaro-tedesco/gh-s`](https://github.com/gennaro-tedesco/gh-s)       | `gh extension` | search/status workflow helper             |

## Code quality and formatters

| Tool                                                                                                              | Source | Why it is here                         |
| ----------------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------- |
| [`shellcheck`](https://www.shellcheck.net/), [`shfmt`](https://github.com/mvdan/sh)                               | `brew` | shell lint/format gates                |
| [`stylua`](https://github.com/JohnnyMorganz/StyLua)                                                               | `brew` | Lua formatting for Neovim/tmux helpers |
| [`markdownlint-cli`](https://github.com/igorshubovych/markdownlint-cli), [`prettier`](https://prettier.io/)       | `brew` | docs and web formatting                |
| [`ruff`](https://docs.astral.sh/ruff/)                                                                            | `brew` | Python lint/format                     |
| [`gofumpt`](https://github.com/mvdan/gofumpt), [`goimports`](https://pkg.go.dev/golang.org/x/tools/cmd/goimports) | `brew` | Go formatting/import normalization     |
| [`bats-core`](https://github.com/bats-core/bats-core)                                                             | `brew` | shell tests                            |
| [`tokei`](https://github.com/XAMPPRocky/tokei)                                                                    | `brew` | code statistics                        |
| [`feluda`](https://github.com/anistark/feluda)                                                                    | `brew` | code/search analysis utility           |

## Build, CI, and containers

| Tool                                                                                                                                                                                                                                               | Source          | Why it is here                    |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------- | --------------------------------- |
| [`cmake`](https://www.cmake.org/), [`automake`](https://www.gnu.org/software/automake/), [`tcl-tk`](https://www.tcl-lang.org)                                                                                                                      | `brew`          | native build dependencies         |
| [`buildkite/buildkite/bk@3`](https://github.com/buildkite/cli)                                                                                                                                                                                     | `brew` tap      | Buildkite CI CLI                  |
| [`dive`](https://github.com/wagoodman/dive), [`colima`](https://colima.run), [`podman`](https://podman.io/), [`lazydocker`](https://github.com/jesseduffield/lazydocker), [`k9s`](https://k9scli.io/), [`minikube`](https://minikube.sigs.k8s.io/) | `brew`          | container and Kubernetes workflow |
| [`sou`](https://github.com/knqyf263/sou), [`cek`](https://github.com/bschaatsbergen/cek)                                                                                                                                                           | `brew`          | container/devops utilities        |
| [`docker-desktop`](https://www.docker.com/products/docker-desktop), [`gcloud-cli`](https://cloud.google.com/cli/), [`azure-cli`](https://docs.microsoft.com/cli/azure/overview)                                                                    | `cask` / `brew` | cloud/container desktop CLIs      |

## Project/runtime helpers

| Tool                                                            | Source | Why it is here                       |
| --------------------------------------------------------------- | ------ | ------------------------------------ |
| [`mise`](https://mise.jdx.dev/)                                 | `brew` | runtime/version manager              |
| [`uv`](https://docs.astral.sh/uv/)                              | `brew` | Python runtime/tool manager          |
| [`bundler`](https://bundler.io/)                                | `gem`  | Ruby project dependency manager      |
| [`neovim`](https://github.com/neovim/node-client)               | `yarn` | Node remote-plugin client for Neovim |
| [`go-global-update`](https://github.com/Gelio/go-global-update) | `go`   | update Go-installed tools            |
