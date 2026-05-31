---
sidebar_position: 1
---

# Reference Map

This page answers two questions:

- where do I change X?
- what file actually drives it?

Paths are relative to the repo root. Hooks live under [`home/.chezmoiscripts/`](../../home/.chezmoiscripts/) and run in numeric order; helper scripts live under [`scripts/`](../../scripts/).

## Chezmoi

| Component      | Source path                                                      |
| -------------- | ---------------------------------------------------------------- |
| Prompts / data | [`home/.chezmoi.toml.tmpl`](../../home/.chezmoi.toml.tmpl)       |
| Shared data    | [`home/.chezmoidata/`](../../home/.chezmoidata/)                 |
| Externals      | [`home/.chezmoiexternal.toml`](../../home/.chezmoiexternal.toml) |
| Ignore rules   | [`home/.chezmoiignore`](../../home/.chezmoiignore)               |
| Hooks          | [`home/.chezmoiscripts/`](../../home/.chezmoiscripts/)           |

## Provisioning hooks (first run)

| Hook                       | Source path                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Xcode CLT                  | [`run_once_before_00-install-xcode.sh`](../../home/.chezmoiscripts/run_once_before_00-install-xcode.sh)                         |
| Homebrew install           | [`run_once_after_01-install-brew.sh`](../../home/.chezmoiscripts/run_once_after_01-install-brew.sh)                             |
| Fish install + login shell | [`run_once_after_02-install-fish.sh`](../../home/.chezmoiscripts/run_once_after_02-install-fish.sh)                             |
| Pass managers setup        | [`run_once_after_05-setup-pass-managers.fish.tmpl`](../../home/.chezmoiscripts/run_once_after_05-setup-pass-managers.fish.tmpl) |

## Packages

Each registry has a declarative list plus the hook that converges it. See [Packages](../topics/core/packages/index.md).

| Registry              | List source                                                                                                                                                                                          | Converge hook                                                                                                                               |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Homebrew              | [`home/.chezmoitemplates/brews/`](../../home/.chezmoitemplates/brews) (per-category, per-profile partials assembled into [`home/readonly_dot_Brewfile.tmpl`](../../home/readonly_dot_Brewfile.tmpl)) | [`run_onchange_after_03-install-brew-packages.fish.tmpl`](../../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl) |
| Fish plugins          | [`home/dot_config/fish/readonly_fish_plugins`](../../home/dot_config/fish/readonly_fish_plugins)                                                                                                     | [`run_onchange_after_04-update-fish-packages.fish.tmpl`](../../home/.chezmoiscripts/run_onchange_after_04-update-fish-packages.fish.tmpl)   |
| mise runtimes         | [`home/dot_config/mise/config.toml.tmpl`](../../home/dot_config/mise/config.toml.tmpl)                                                                                                               | [`run_onchange_after_05-install-mise-runtimes.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-install-mise-runtimes.sh.tmpl)     |
| Cargo crates          | [`home/readonly_dot_default-cargo-crates`](../../home/readonly_dot_default-cargo-crates)                                                                                                             | [`run_onchange_after_05-update-cargo-crates.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-update-cargo-crates.sh.tmpl)         |
| Go tools              | [`home/readonly_dot_default-golang-pkgs`](../../home/readonly_dot_default-golang-pkgs)                                                                                                               | [`run_onchange_after_05-update-golang-pkgs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-update-golang-pkgs.sh.tmpl)           |
| Ruby gems             | [`home/readonly_dot_default-gems`](../../home/readonly_dot_default-gems)                                                                                                                             | [`run_onchange_after_05-update-gems.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-update-gems.sh.tmpl)                         |
| Global yarn           | [`home/readonly_dot_default-yarn-pkgs`](../../home/readonly_dot_default-yarn-pkgs)                                                                                                                   | [`run_onchange_after_05-update-yarn-pkgs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-update-yarn-pkgs.sh.tmpl)               |
| uv python versions    | [`home/readonly_dot_python-version`](../../home/readonly_dot_python-version)                                                                                                                         | [`run_onchange_after_05-install-uv-versions.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl)         |
| uv tools              | [`home/readonly_dot_default-uv-tools.tmpl`](../../home/readonly_dot_default-uv-tools.tmpl)                                                                                                           | [`run_onchange_after_06-update-uv-tools.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_06-update-uv-tools.sh.tmpl)                 |
| Custom packages       | [`home/readonly_dot_default-custom-packages.tmpl`](../../home/readonly_dot_default-custom-packages.tmpl)                                                                                             | [`run_onchange_after_05-install-custom-packages.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl) |
| GitHub CLI extensions | (declared in hook)                                                                                                                                                                                   | [`run_onchange_after_05-install-gh-extensions.fish.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-install-gh-extensions.fish.tmpl) |
| llama.cpp GGUF models | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                                                           | [`run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl)     |

## Shell

| Component               | Source path                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------------- |
| Fish main config        | [`home/dot_config/fish/readonly_config.fish.tmpl`](../../home/dot_config/fish/readonly_config.fish.tmpl) |
| POSIX shellrc (alias)   | [`home/readonly_dot_shellrc`](../../home/readonly_dot_shellrc)                                           |
| Zsh completions         | [`home/dot_zsh/`](../../home/dot_zsh/)                                                                   |
| Starship prompt         | [`home/dot_config/readonly_starship.toml`](../../home/dot_config/readonly_starship.toml)                 |
| Shared ignores (fd/fzf) | [`home/dot_config/readonly_ignore-globs`](../../home/dot_config/readonly_ignore-globs)                   |

## Git + Identity

| Component                           | Source path                                                                                                                                                                        |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Git main config template            | [`home/private_readonly_dot_gitconfig.tmpl`](../../home/private_readonly_dot_gitconfig.tmpl)                                                                                       |
| Work override gitconfig             | [`home/work/private_dot_gitconfig.tmpl`](../../home/work/private_dot_gitconfig.tmpl)                                                                                               |
| SSH config (1Password agent socket) | [`home/private_dot_ssh/private_executable_config`](../../home/private_dot_ssh/private_executable_config)                                                                           |
| Allowed signers (SSH signing)       | [`home/private_dot_ssh/private_executable_allowed_signers.tmpl`](../../home/private_dot_ssh/private_executable_allowed_signers.tmpl)                                               |
| 1Password SSH agent config          | [`home/dot_config/exact_private_1Password/exact_ssh/readonly_agent.toml.tmpl`](../../home/dot_config/exact_private_1Password/exact_ssh/readonly_agent.toml.tmpl)                   |
| gh picker work config               | [`home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-work.yml`](../../home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-work.yml) |
| gh picker home config               | [`home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-home.yml`](../../home/dot_config/exact_tmux/exact_scripts/pickers/github/readonly_gh-picker-home.yml) |

## Editor

| Component | Source path                                                        |
| --------- | ------------------------------------------------------------------ |
| Neovim    | [`home/dot_config/exact_nvim/`](../../home/dot_config/exact_nvim/) |

## Terminal + Multiplexing

| Component       | Source path                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| tmux            | [`home/dot_config/exact_tmux/readonly_tmux.conf`](../../home/dot_config/exact_tmux/readonly_tmux.conf) |
| Ghostty         | [`home/dot_config/exact_ghostty/readonly_config`](../../home/dot_config/exact_ghostty/readonly_config) |
| bat             | [`home/dot_config/exact_bat/readonly_config`](../../home/dot_config/exact_bat/readonly_config)         |
| Yazi (file mgr) | [`home/dot_config/yazi/`](../../home/dot_config/yazi/)                                                 |
| lazygit         | [`home/dot_config/exact_lazygit/config.yml`](../../home/dot_config/exact_lazygit/config.yml)           |
| gitui           | [`home/dot_config/exact_gitui/`](../../home/dot_config/exact_gitui/)                                   |
| tig             | [`home/dot_config/exact_tig/readonly_config`](../../home/dot_config/exact_tig/readonly_config)         |
| btop            | [`home/dot_config/exact_btop/btop.conf`](../../home/dot_config/exact_btop/btop.conf)                   |
| gh-dash         | [`home/dot_config/exact_gh-dash/`](../../home/dot_config/exact_gh-dash/)                               |

## macOS Automation

| Component         | Source path                                                                                                                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Defaults scripts  | [`home/.osx.core`](../../home/.osx.core), [`home/.osx.extra`](../../home/.osx.extra)                                                                                                                      |
| Defaults hooks    | [`run_onchange_after_05-osx.core.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-osx.core.sh.tmpl), [`...05-osx.extra...`](../../home/.chezmoiscripts/run_onchange_after_05-osx.extra.sh.tmpl) |
| Hammerspoon       | [`home/dot_hammerspoon/`](../../home/dot_hammerspoon/)                                                                                                                                                    |
| Karabiner         | [`home/dot_config/exact_private_karabiner/`](../../home/dot_config/exact_private_karabiner/)                                                                                                              |
| App icons mapping | [`home/app_icons/readonly_icon_mapping.yaml`](../../home/app_icons/readonly_icon_mapping.yaml)                                                                                                            |
| App icons hook    | [`run_onchange_after_05-apply-app-icons.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-apply-app-icons.sh.tmpl)                                                                               |
| Crontab           | [`run_onchange_after_05-install-crontab.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_05-install-crontab.sh.tmpl)                                                                               |

## AI: governance + skills

See [The Agentic Operating System](../topics/ai-assistants/index.md).

| Component                 | Source path                                                                                                                                        |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Assistant SOP entrypoints | [`home/readonly_AGENTS.md`](../../home/readonly_AGENTS.md), [`home/readonly_CLAUDE.md`](../../home/readonly_CLAUDE.md)                             |
| Gemini SOP                | [`home/dot_gemini/readonly_GEMINI.md`](../../home/dot_gemini/readonly_GEMINI.md)                                                                   |
| Assistant skills          | [`home/exact_dot_agents/exact_skills/`](../../home/exact_dot_agents/exact_skills/)                                                                 |
| Cursor CLI hooks          | [`home/dot_cursor/hooks.json`](../../home/dot_cursor/hooks.json), [`home/exact_dot_agents/exact_hooks/`](../../home/exact_dot_agents/exact_hooks/) |

## AI: harness configs

Per-tool config sources and the `run_onchange_after_07-*` hooks that render them. See [Tool configs](../topics/ai-assistants/tool-configs.md).

| Tool        | Source                                                           | Merge hook                                                                                                                                        |
| ----------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code | [`home/dot_claude/`](../../home/dot_claude/)                     | [`run_onchange_after_07-merge-claude-code-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-claude-code-settings.sh.tmpl) |
| Codex       | [`home/dot_codex/`](../../home/dot_codex/)                       | [`run_onchange_after_07-merge-codex-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-codex-config.sh.tmpl)                 |
| Gemini      | [`home/dot_gemini/`](../../home/dot_gemini/)                     | [`run_onchange_after_07-merge-gemini-settings.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-gemini-settings.sh.tmpl)           |
| OpenCode    | [`home/dot_config/opencode/`](../../home/dot_config/opencode/)   | [`run_onchange_after_07-merge-opencode-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-opencode-config.sh.tmpl)           |
| Pi          | [`home/dot_pi/agent/`](../../home/dot_pi/agent/)                 | [`run_onchange_after_07-merge-pi-config.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-merge-pi-config.sh.tmpl)                       |
| Cursor      | [`home/dot_cursor/`](../../home/dot_cursor/)                     | (settings tracked directly)                                                                                                                       |
| Amp         | [`home/dot_config/exact_amp/`](../../home/dot_config/exact_amp/) | (settings tracked directly)                                                                                                                       |

## AI: model registry

Single source of truth for LiteLLM/Azure model definitions; per-tool model configs are generated from it. See [Model registry & routing](../topics/ai-assistants/model-registry.md).

| Component               | Source path                                                                            |
| ----------------------- | -------------------------------------------------------------------------------------- |
| Model definitions       | [`home/.chezmoidata/ai_models.yaml`](../../home/.chezmoidata/ai_models.yaml)           |
| YAML reader             | [`scripts/ai_models.py`](../../scripts/ai_models.py)                                   |
| Pi models generator     | [`scripts/generate_pi_models.py`](../../scripts/generate_pi_models.py)                 |
| OpenCode models merge   | [`scripts/merge_opencode_models.py`](../../scripts/merge_opencode_models.py)           |
| Display-name formatting | [`scripts/model_display.py`](../../scripts/model_display.py)                           |
| Prompt-cache probe      | [`scripts/probe_litellm_prompt_cache.py`](../../scripts/probe_litellm_prompt_cache.py) |

## AI: MCP

Canonical MCP registry plus the generator/injectors that fan it out per tool. See [MCP servers](../topics/ai-assistants/mcp.md).

| Component         | Source path                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| MCP registry      | [`home/.chezmoidata/mcp_servers.yaml`](../../home/.chezmoidata/mcp_servers.yaml)                                                      |
| Registry reader   | [`scripts/mcp_registry.py`](../../scripts/mcp_registry.py)                                                                            |
| Config generator  | [`scripts/generate_mcp_configs.py`](../../scripts/generate_mcp_configs.py)                                                            |
| Codex injector    | [`scripts/inject_mcp_into_codex_toml.py`](../../scripts/inject_mcp_into_codex_toml.py)                                                |
| OpenCode injector | [`scripts/inject_mcp_into_opencode_jsonc.py`](../../scripts/inject_mcp_into_opencode_jsonc.py)                                        |
| Claude MCP merge  | [`scripts/merge_claude_mcp.py`](../../scripts/merge_claude_mcp.py)                                                                    |
| Generate hook     | [`run_onchange_after_07-generate-mcp-configs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-generate-mcp-configs.sh.tmpl) |

## AI: memory

Two distinct memory layers. See [Agent memory](../topics/ai-assistants/knowledge-base.md).

| Component                     | Source path                                                                                                                                            |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| AI knowledge base (`,ai-kb`)  | [`home/exact_bin/executable_,ai-kb`](../../home/exact_bin/executable_,ai-kb), [`scripts/ai_kb.py`](../../scripts/ai_kb.py)                             |
| Embedding service             | [`scripts/embed.py`](../../scripts/embed.py), [`scripts/embed_runner.py`](../../scripts/embed_runner.py)                                               |
| Vector retrieval              | [`scripts/vec_runner.py`](../../scripts/vec_runner.py)                                                                                                 |
| Hook memory (`,agent-memory`) | [`home/exact_bin/executable_,agent-memory`](../../home/exact_bin/executable_,agent-memory), [`scripts/agent_memory.py`](../../scripts/agent_memory.py) |

## AI: Ralph orchestrator

See [Ralph orchestrator](../topics/ai-assistants/ralph.md).

| Component         | Source path                                                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------- |
| CLI entry         | [`home/exact_bin/executable_,ralph`](../../home/exact_bin/executable_,ralph)                                                |
| Orchestrator      | [`scripts/ralph.py`](../../scripts/ralph.py)                                                                                |
| Roles + diversity | [`home/dot_config/ralph/roles.json`](../../home/dot_config/ralph/roles.json)                                                |
| Role prompts      | [`home/dot_config/ralph/prompts/`](../../home/dot_config/ralph/prompts/)                                                    |
| Dashboard (TUI)   | [`tools/ralph-tui/`](../../tools/ralph-tui/)                                                                                |
| TUI build hook    | [`run_onchange_after_06-build-ralph-tui.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_06-build-ralph-tui.sh.tmpl) |

## AI: local inference

See [llama.cpp local inference](../topics/ai-assistants/llama-cpp.md).

| Component           | Source path                                                                                                                                                                                                                                                                                              |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GGUF model manifest | [`home/readonly_dot_default-llama-cpp-models.tmpl`](../../home/readonly_dot_default-llama-cpp-models.tmpl)                                                                                                                                                                                               |
| Router preset (INI) | [`home/dot_config/llama.cpp/models.ini.tmpl`](../../home/dot_config/llama.cpp/models.ini.tmpl)                                                                                                                                                                                                           |
| Chat template       | [`home/dot_config/llama.cpp/readonly_qwen3.6-chat-template.jinja`](../../home/dot_config/llama.cpp/readonly_qwen3.6-chat-template.jinja) (robust Unsloth template; `local-max` override for system-message ordering)                                                                                     |
| Sync hook + helper  | [`run_onchange_after_07-sync-llama-cpp-models.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_07-sync-llama-cpp-models.sh.tmpl), [`scripts/sync_llama_cpp_models.py`](../../scripts/sync_llama_cpp_models.py)                                                                                    |
| Control plane       | [`home/exact_bin/executable_,llama-cpp`](../../home/exact_bin/executable_,llama-cpp)                                                                                                                                                                                                                     |
| Claude launcher     | [`home/exact_bin/executable_,claude-llama-cpp`](../../home/exact_bin/executable_,claude-llama-cpp)                                                                                                                                                                                                       |
| Codex launcher      | [`home/exact_bin/executable_,codex-llama-cpp`](../../home/exact_bin/executable_,codex-llama-cpp), catalog shim [`home/exact_bin/executable_codex`](../../home/exact_bin/executable_codex)                                                                                                                |
| OpenCode launcher   | [`home/exact_bin/executable_,opencode-llama-cpp`](../../home/exact_bin/executable_,opencode-llama-cpp) (provider in [`opencode.personal.jsonc`](../../home/dot_config/opencode/readonly_opencode.personal.jsonc) / [`opencode.work.jsonc`](../../home/dot_config/opencode/readonly_opencode.work.jsonc)) |
| Pi provider         | [`home/dot_pi/agent/readonly_models.json`](../../home/dot_pi/agent/readonly_models.json) (`local` + `local-max`)                                                                                                                                                                                         |

## Scripts (`scripts/`)

Helper scripts called by hooks and commands (stdlib-only by convention).

| Script                              | Purpose                                                                                               |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `chezmoi_lib.sh`                    | Shared shell library for merge/apply hooks (source selection, atomic writes, checksums, LiteLLM base) |
| `verify_templates.py`               | Render every chezmoi `*.tmpl` via `execute-template` to catch errors early                            |
| `verify_mermaids.py`                | Check `.mermaids/` file-census counts against `git ls-files` (part of `make check`)                   |
| `yaml_parser.py`                    | Minimal dependency-free YAML parser for project data files                                            |
| `jsonc_dump.py`                     | JSONC serializer matching OpenCode's trailing-comma config style                                      |
| `mcp_registry.py`                   | Read/normalize the canonical MCP registry                                                             |
| `generate_mcp_configs.py`           | Generate tool-specific MCP configs from `mcp_servers.yaml`                                            |
| `inject_mcp_into_codex_toml.py`     | Inject MCP servers into Codex TOML at a marker line                                                   |
| `inject_mcp_into_opencode_jsonc.py` | Inject MCP servers into an OpenCode JSONC placeholder                                                 |
| `merge_claude_mcp.py`               | Surgically update only `mcpServers` in `~/.claude.json`                                               |
| `merge_claude_settings.py`          | Merge desired Claude settings, preserving runtime-written keys                                        |
| `merge_opencode_models.py`          | Merge LiteLLM/Azure models into OpenCode JSONC                                                        |
| `ai_models.py`                      | Parse the `litellm_models` / `azure_models` sections of `ai_models.yaml`                              |
| `generate_pi_models.py`             | Build Pi `models.json` from the shared base plus LiteLLM/Azure providers                              |
| `model_display.py`                  | Shared display-name formatting for LiteLLM model entries                                              |
| `probe_litellm_prompt_cache.py`     | Probe prompt-cache signals across LiteLLM models                                                      |
| `ai_kb.py`                          | Local markdown + SQLite FTS5/vector knowledge base for agent runs                                     |
| `embed.py`                          | Stdlib embedding-service abstraction that shells out to `embed_runner.py`                             |
| `embed_runner.py`                   | Isolated PEP 723 `fastembed` runner (`BAAI/bge-small-en-v1.5`, 384-d)                                 |
| `vec_runner.py`                     | Isolated PEP 723 `sqlite-vec` KNN/pairs runner for the KB                                             |
| `agent_memory.py`                   | Inspect/wipe hook memory under `/tmp/specs` for the current workspace                                 |
| `ralph.py`                          | Ralph orchestrator state machine (planner -> executor -> reviewer -> re_reviewer)                     |
| `sync_llama_cpp_models.py`          | Download missing GGUF files declared in the llama.cpp manifest                                        |
| `reconcile_custom_packages.py`      | Reconcile source-installed custom package artifacts                                                   |
| `yt_search.py`                      | YouTube search backend (powers `,youtube-search`)                                                     |
| `tests/`                            | Python test suite (`test_scripts.py`, agent-hook tests)                                               |

## Maintenance / cleanup hooks

Idempotent housekeeping that removes orphaned generated state on apply.

| Hook                                                                                                                                                                | Purpose                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| [`run_onchange_after_08-cleanup-orphaned-agent-skill-dirs.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_08-cleanup-orphaned-agent-skill-dirs.sh.tmpl)     | Drop skill dirs no longer in the source tree |
| [`run_onchange_after_08-cleanup-orphaned-ralph-fzf-scaffold.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_08-cleanup-orphaned-ralph-fzf-scaffold.sh.tmpl) | Remove stale Ralph fzf scaffold artifacts    |
| [`run_onchange_after_08-cleanup-orphaned-tmux-pick_session.sh.tmpl`](../../home/.chezmoiscripts/run_onchange_after_08-cleanup-orphaned-tmux-pick_session.sh.tmpl)   | Remove stale tmux `pick_session` artifacts   |

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

| Component       | Source path                                |
| --------------- | ------------------------------------------ |
| Commands source | [`home/exact_bin/`](../../home/exact_bin/) |
