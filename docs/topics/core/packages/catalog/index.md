---
title: Package catalog
---

# Package catalog

This is the human map of the tools this dotfiles repo controls across package managers. The add-package pages explain how to change the lists; this catalog explains what the lists are for.

## Read path

| Slice                                                                      | Covers                                                                                |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [AI and agent tooling](ai-and-agent-tooling.md)                            | coding agents, local inference, MCP/subagents, review helpers, AI model assets        |
| [Developer workflow](developer-workflow.md)                                | git, GitHub, worktrees, code quality, build/test, containers, CI                      |
| [Terminal, files, and data](terminal-files-and-data.md)                    | shells, tmux, file navigation/search, structured data, TUIs, documentation tools      |
| [macOS apps and system utilities](macos-apps-and-system.md)                | browsers, desktop/security apps, macOS automation, fonts, monitoring, network tools   |
| [Media, personal tools, and custom releases](media-personal-and-custom.md) | audio/video/image tools, personal casks, flight/travel tools, GitHub release installs |
| [Languages and runtimes](languages-and-runtimes.md)                        | mise, uv Python versions, Cargo/Go/Ruby/yarn/uv global packages                       |

## Source families

| Family                                                                                                                 | Source                                                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [Homebrew](https://brew.sh/) formulae/casks/taps                                                                       | [`home/.chezmoitemplates/brews/`](../../../../../home/.chezmoitemplates/brews/)                                                                                                            |
| [mise](https://mise.jdx.dev/) runtimes                                                                                 | [`home/dot_config/mise/config.toml.tmpl`](../../../../../home/dot_config/mise/config.toml.tmpl)                                                                                            |
| [Cargo](https://doc.rust-lang.org/cargo/) crates                                                                       | [`home/readonly_dot_default-cargo-crates`](../../../../../home/readonly_dot_default-cargo-crates)                                                                                          |
| [Go](https://go.dev/) tools                                                                                            | [`home/readonly_dot_default-golang-pkgs.tmpl`](../../../../../home/readonly_dot_default-golang-pkgs.tmpl)                                                                                  |
| [RubyGems](https://rubygems.org/) gems                                                                                 | [`home/readonly_dot_default-gems`](../../../../../home/readonly_dot_default-gems)                                                                                                          |
| [Yarn](https://yarnpkg.com/) globals                                                                                   | [`home/readonly_dot_default-yarn-pkgs`](../../../../../home/readonly_dot_default-yarn-pkgs)                                                                                                |
| [uv](https://docs.astral.sh/uv/) Python/tools                                                                          | [`home/readonly_dot_python-version`](../../../../../home/readonly_dot_python-version), [`home/readonly_dot_default-uv-tools.tmpl`](../../../../../home/readonly_dot_default-uv-tools.tmpl) |
| [GitHub CLI](https://cli.github.com/) extensions                                                                       | [`run_onchange_after_05-install-gh-extensions.fish.tmpl`](../../../../../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl)                                       |
| [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) / source builds | [`home/readonly_dot_default-custom-packages.tmpl`](../../../../../home/readonly_dot_default-custom-packages.tmpl)                                                                          |
| [llama.cpp](https://llama.app) model assets                                                                            | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../../../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                                        |

## Reading convention

| Badge                                      | Meaning                                        |
| ------------------------------------------ | ---------------------------------------------- |
| `brew` / `cask` / `tap`                    | Homebrew source                                |
| `yarn`, `uv`, `cargo`, `go`, `gem`, `mise` | language/runtime manager source                |
| `custom`                                   | GitHub release, DMG, or source build installer |
| `personal`                                 | gated to non-work machines                     |
| `model`                                    | large local model asset                        |
