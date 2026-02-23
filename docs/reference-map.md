# Reference Map

Back: [`docs/index.md`](index.md)

This page answers two questions:

- where do I change X?
- what file actually drives it?

## Chezmoi

- Prompts / data: `home/.chezmoi.toml.tmpl`
- Externals: `home/.chezmoiexternal.toml`
- Ignore rules: `home/.chezmoiignore`
- Hooks: `home/.chezmoiscripts/`

## Core Provisioning Hooks

- Xcode CLT: `home/.chezmoiscripts/run_once_before_00-install-xcode.sh`
- Homebrew install: `home/.chezmoiscripts/run_once_after_01-install-brew.sh`
- Fish install + login shell: `home/.chezmoiscripts/run_once_after_02-install-fish.sh`
- Brew bundle: `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`

## Packages

- Brewfile: `home/readonly_dot_Brewfile.tmpl`
- ASDF plugins: `home/asdf_plugins.tmpl`
- ASDF versions: `home/readonly_dot_tool-versions.tmpl`
- cargo crates: `home/readonly_dot_default-cargo-crates`
- go tools: `home/readonly_dot_default-golang-pkgs`
- ruby gems: `home/readonly_dot_default-gems`
- global npm: `home/readonly_dot_default-npm-pkgs`
- uv tools: `home/readonly_dot_default-uv-tools.tmpl`
- manual packages: `home/readonly_dot_default-manual-packages.tmpl`

## Shell

- Fish main config: `home/dot_config/fish/config.fish.tmpl`
- Fish plugins: `home/dot_config/fish/fish_plugins`
- Starship prompt: `home/dot_config/starship.toml`
- Shared ignores (fd/fzf): `home/dot_config/ignore-globs`

## Git + Identity

- Git main config template: `home/private_readonly_dot_gitconfig.tmpl`
- Work override gitconfig: `home/work/private_dot_gitconfig.tmpl`
- SSH config (1Password agent socket): `home/private_dot_ssh/private_executable_config`
- Allowed signers (SSH signing): `home/private_dot_ssh/private_executable_allowed_signers.tmpl`
- 1Password SSH agent config: `home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl`

## Editor

- Neovim: `home/dot_config/exact_nvim/`

## Terminal + Multiplexing

- tmux: `home/dot_config/exact_tmux/tmux.conf`
- Ghostty: `home/dot_config/exact_ghostty/config`
- bat: `home/dot_config/exact_bat/config`

## macOS Automation

- Defaults scripts: `home/.osx.core`, `home/.osx.extra`
- Hammerspoon: `home/dot_hammerspoon/`
- Karabiner: `home/dot_config/exact_private_karabiner/`
- App icons mapping: `home/app_icons/icon_mapping.yaml`

## AI + Assistants

- OpenCode: `home/dot_config/opencode/`
- Codex: `home/dot_codex/`
- Gemini: `home/dot_gemini/`
- Assistant SOP entrypoints: `home/readonly_AGENTS.md`, `home/readonly_CLAUDE.md`
- Assistant playbooks: `home/exact_dot_agents/exact_playbooks/`

## Custom Commands

- Commands source: `home/exact_bin/`
