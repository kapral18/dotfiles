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
- Fish packages: `home/.chezmoiscripts/run_onchange_after_04-update-fish-packages.fish.tmpl`

## Packages

- Brewfile: `home/readonly_dot_Brewfile.tmpl`
- ASDF plugins: `home/asdf_plugins.tmpl`
- ASDF versions: `home/readonly_dot_tool-versions.tmpl`
- cargo crates: `home/readonly_dot_default-cargo-crates`
- go tools: `home/readonly_dot_default-golang-pkgs`
- ruby gems: `home/readonly_dot_default-gems`
- global npm: `home/readonly_dot_default-npm-pkgs`
- uv tools: `home/readonly_dot_default-uv-tools.tmpl`
- uv python versions: `home/readonly_dot_python-version`
- manual packages: `home/readonly_dot_default-manual-packages.tmpl`
- GitHub CLI extensions: `home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl`
- uv python installation: `home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl`
- uv tools installation: `home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl`

## Shell

- Fish main config: `home/dot_config/fish/readonly_config.fish.tmpl`
- Fish plugins: `home/dot_config/fish/readonly_fish_plugins`
- Starship prompt: `home/dot_config/readonly_starship.toml`
- Shared ignores (fd/fzf): `home/dot_config/readonly_ignore-globs`

## Git + Identity

- Git main config template: `home/private_readonly_dot_gitconfig.tmpl`
- Work override gitconfig: `home/work/private_dot_gitconfig.tmpl`
- SSH config (1Password agent socket): `home/private_dot_ssh/private_executable_config`
- Allowed signers (SSH signing): `home/private_dot_ssh/private_executable_allowed_signers.tmpl`
- 1Password SSH agent config: `home/dot_config/exact_private_1Password/exact_ssh/agent.toml.tmpl`

## Editor

- Neovim: `home/dot_config/exact_nvim/`

## Terminal + Multiplexing

- tmux: `home/dot_config/exact_tmux/readonly_tmux.conf`
- Ghostty: `home/dot_config/exact_ghostty/readonly_config`
- bat: `home/dot_config/exact_bat/readonly_config`

## macOS Automation

- Defaults scripts: `home/.osx.core`, `home/.osx.extra`
- Hammerspoon: `home/dot_hammerspoon/`
- Karabiner: `home/dot_config/exact_private_karabiner/`
- App icons mapping: `home/app_icons/readonly_icon_mapping.yaml`

## Security + AI

- Setup pass managers: `home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl`
- OpenCode: `home/dot_config/opencode/`
- Pi config: `home/dot_pi/agent/`
- Pi CLI package list entry: `home/readonly_dot_default-npm-pkgs`
- Claude Code: `home/dot_claude/`
- Codex: `home/dot_codex/`
- Codex model catalog generator: `home/.chezmoiscripts/run_onchange_after_07-generate-codex-model-catalog.sh.tmpl`
- Gemini: `home/dot_gemini/`
- Copilot CLI: `home/dot_config/dot_copilot/`
- Cursor: `home/dot_cursor/`
- Amp: `home/dot_config/exact_amp/`
- Assistant SOP entrypoints: `home/readonly_AGENTS.md`, `home/readonly_CLAUDE.md`
- Assistant playbooks: `home/exact_dot_agents/exact_playbooks/`
- Assistant skills: `home/exact_dot_agents/exact_skills/`
- Ollama models: `home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh`

## Custom Commands

- Commands source: `home/exact_bin/`
