# Reference Map

Back: [`docs/index.md`](index.md)

This page answers two questions:

- where do I change X?
- what file actually drives it?

## Chezmoi

| Component      | Source path                                                   |
| -------------- | ------------------------------------------------------------- |
| Prompts / data | [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl)       |
| Externals      | [`home/.chezmoiexternal.toml`](../home/.chezmoiexternal.toml) |
| Ignore rules   | [`home/.chezmoiignore`](../home/.chezmoiignore)               |
| Hooks          | [`home/.chezmoiscripts/`](../home/.chezmoiscripts/)           |

## Core Provisioning Hooks

| Hook                       | Source path                                                                                                                                                   |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Xcode CLT                  | [`home/.chezmoiscripts/run_once_before_00-install-xcode.sh`](../home/.chezmoiscripts/run_once_before_00-install-xcode.sh)                                     |
| Homebrew install           | [`home/.chezmoiscripts/run_once_after_01-install-brew.sh`](../home/.chezmoiscripts/run_once_after_01-install-brew.sh)                                         |
| Fish install + login shell | [`home/.chezmoiscripts/run_once_after_02-install-fish.sh`](../home/.chezmoiscripts/run_once_after_02-install-fish.sh)                                         |
| Brew bundle                | [`home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`](../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl) |
| Fish packages              | [`home/.chezmoiscripts/run_onchange_after_04-update-fish-packages.fish.tmpl`](../home/.chezmoiscripts/run_onchange_after_04-update-fish-packages.fish.tmpl)   |

## Packages

| Component              | Source path                                                                                                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Brewfile               | [`home/readonly_dot_Brewfile.tmpl`](../home/readonly_dot_Brewfile.tmpl)                                                                                       |
| ASDF plugins           | [`home/asdf_plugins.tmpl`](../home/asdf_plugins.tmpl)                                                                                                         |
| ASDF versions          | [`home/readonly_dot_tool-versions.tmpl`](../home/readonly_dot_tool-versions.tmpl)                                                                             |
| Cargo crates           | [`home/readonly_dot_default-cargo-crates`](../home/readonly_dot_default-cargo-crates)                                                                         |
| Go tools               | [`home/readonly_dot_default-golang-pkgs`](../home/readonly_dot_default-golang-pkgs)                                                                           |
| Ruby gems              | [`home/readonly_dot_default-gems`](../home/readonly_dot_default-gems)                                                                                         |
| Global npm             | [`home/readonly_dot_default-npm-pkgs`](../home/readonly_dot_default-npm-pkgs)                                                                                 |
| uv tools               | [`home/readonly_dot_default-uv-tools.tmpl`](../home/readonly_dot_default-uv-tools.tmpl)                                                                       |
| uv python versions     | [`home/readonly_dot_python-version`](../home/readonly_dot_python-version)                                                                                     |
| Manual packages        | [`home/readonly_dot_default-manual-packages.tmpl`](../home/readonly_dot_default-manual-packages.tmpl)                                                         |
| GitHub CLI extensions  | [`home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`](../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl) |
| uv python installation | [`home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl`](../home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl)         |
| uv tools installation  | [`home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`](../home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl)                 |

## Shell

| Component               | Source path                                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| Fish main config        | [`home/dot_config/fish/readonly_config.fish.tmpl`](../home/dot_config/fish/readonly_config.fish.tmpl) |
| Fish plugins            | [`home/dot_config/fish/readonly_fish_plugins`](../home/dot_config/fish/readonly_fish_plugins)         |
| Starship prompt         | [`home/dot_config/readonly_starship.toml`](../home/dot_config/readonly_starship.toml)                 |
| Shared ignores (fd/fzf) | [`home/dot_config/readonly_ignore-globs`](../home/dot_config/readonly_ignore-globs)                   |

## Git + Identity

| Component                           | Source path                                                                                                                                   |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Git main config template            | [`home/private_readonly_dot_gitconfig.tmpl`](../home/private_readonly_dot_gitconfig.tmpl)                                                     |
| Work override gitconfig             | [`home/work/private_dot_gitconfig.tmpl`](../home/work/private_dot_gitconfig.tmpl)                                                             |
| SSH config (1Password agent socket) | [`home/private_dot_ssh/private_executable_config`](../home/private_dot_ssh/private_executable_config)                                         |
| Allowed signers (SSH signing)       | [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../home/private_dot_ssh/private_executable_allowed_signers.tmpl)             |
| 1Password SSH agent config          | [`home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl`](../home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl)   |
| gh-dash shared config               | [`home/dot_config/exact_gh-dash/gh-dash-shared.yml`](../home/dot_config/exact_gh-dash/gh-dash-shared.yml)                                     |
| gh-dash work/home templates         | [`home/dot_config/exact_gh-dash/readonly_config-{work,home}.yml.tmpl`](../home/dot_config/exact_gh-dash/readonly_config-{work,home}.yml.tmpl) |

## Editor

| Component | Source path                                                     |
| --------- | --------------------------------------------------------------- |
| Neovim    | [`home/dot_config/exact_nvim/`](../home/dot_config/exact_nvim/) |

## Terminal + Multiplexing

| Component | Source path                                                                                         |
| --------- | --------------------------------------------------------------------------------------------------- |
| tmux      | [`home/dot_config/exact_tmux/readonly_tmux.conf`](../home/dot_config/exact_tmux/readonly_tmux.conf) |
| Ghostty   | [`home/dot_config/exact_ghostty/readonly_config`](../home/dot_config/exact_ghostty/readonly_config) |
| bat       | [`home/dot_config/exact_bat/readonly_config`](../home/dot_config/exact_bat/readonly_config)         |

## macOS Automation

| Component         | Source path                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------- |
| Defaults scripts  | [`home/.osx.core`](../home/.osx.core), [`home/.osx.extra`](../home/.osx.extra)              |
| Hammerspoon       | [`home/dot_hammerspoon/`](../home/dot_hammerspoon/)                                         |
| Karabiner         | [`home/dot_config/exact_private_karabiner/`](../home/dot_config/exact_private_karabiner/)   |
| App icons mapping | [`home/app_icons/readonly_icon_mapping.yaml`](../home/app_icons/readonly_icon_mapping.yaml) |

## Security + AI

| Component                     | Source path                                                                                                                                                             |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Setup pass managers           | [`home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`](../home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl)                       |
| OpenCode                      | [`home/dot_config/opencode/`](../home/dot_config/opencode/)                                                                                                             |
| Pi config                     | [`home/dot_pi/agent/`](../home/dot_pi/agent/)                                                                                                                           |
| Pi CLI package list entry     | [`home/readonly_dot_default-npm-pkgs`](../home/readonly_dot_default-npm-pkgs)                                                                                           |
| Claude Code                   | [`home/dot_claude/`](../home/dot_claude/)                                                                                                                               |
| Codex                         | [`home/dot_codex/`](../home/dot_codex/)                                                                                                                                 |
| Codex model catalog generator | [`home/.chezmoiscripts/run_onchange_after_07-generate-codex-model-catalog.sh.tmpl`](../home/.chezmoiscripts/run_onchange_after_07-generate-codex-model-catalog.sh.tmpl) |
| Gemini                        | [`home/dot_gemini/`](../home/dot_gemini/)                                                                                                                               |
| Copilot CLI                   | [`home/dot_config/dot_copilot/`](../home/dot_config/dot_copilot/)                                                                                                       |
| Cursor                        | [`home/dot_cursor/`](../home/dot_cursor/)                                                                                                                               |
| Amp                           | [`home/dot_config/exact_amp/`](../home/dot_config/exact_amp/)                                                                                                           |
| Assistant SOP entrypoints     | [`home/readonly_AGENTS.md`](../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../home/readonly_CLAUDE.md)                                                        |
| Assistant playbooks           | [`home/exact_dot_agents/exact_playbooks/`](../home/exact_dot_agents/exact_playbooks/)                                                                                   |
| Assistant skills              | [`home/exact_dot_agents/exact_skills/`](../home/exact_dot_agents/exact_skills/)                                                                                         |
| Ollama models                 | [`home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`](../home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh)                                 |
| Merge script shared library   | [`scripts/chezmoi_lib.sh`](../scripts/chezmoi_lib.sh)                                                                                                                   |
| LiteLLM model definitions     | [`home/.chezmoidata/litellm_models.yaml`](../home/.chezmoidata/litellm_models.yaml)                                                                                     |

## Formatting

| Component       | Source path       |
| --------------- | ----------------- |
| Format script   | `bin/fmt`         |
| EditorConfig    | `.editorconfig`   |
| Prettier config | `.prettierrc`     |
| Prettier ignore | `.prettierignore` |
| StyLua config   | `.stylua.toml`    |
| Ruff config     | `ruff.toml`       |

## Custom Commands

| Component       | Source path                             |
| --------------- | --------------------------------------- |
| Commands source | [`home/exact_bin/`](../home/exact_bin/) |
