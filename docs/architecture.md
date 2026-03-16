# Architecture

Back: [`docs/index.md`](index.md)

This setup is a `chezmoi` source directory. `chezmoi` renders templates and
copies files into your `$HOME`.

## Repository Layout

- [`home/`](../home/) is the source-of-truth for files that end up in your home
  directory.
- [`home/.chezmoiscripts/`](../home/.chezmoiscripts/) contains automation hooks
  that run during apply.
- [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl) defines interactive
  prompts and computed values.
- [`home/.chezmoiexternal.toml`](../home/.chezmoiexternal.toml) pulls a few
  external assets (git repos/archives).

## Documentation Hygiene

This repo treats `docs/` as part of the configuration:

- If you change dotfiles behavior (anything under [`home/`](../home/) that
  affects commands or workflows), update `docs/` in the same change.
- If a change truly has no user-facing impact, record that in the PR/commit
  context so the docs/code divergence is explicit.

## Repo-Only Assets (Not Installed Into `$HOME`)

Some directories in [`home/`](../home/) are intentionally ignored by `chezmoi`
and are used as "repo-local data" for scripts.

Ignore rules live in:

- [`home/.chezmoiignore`](../home/.chezmoiignore)

Examples in this setup:

- [`home/app_icons/`](../home/app_icons/) is used by the `,apply-app-icons`
  script, but it is not installed into `$HOME`.
- [`home/Alfred.alfredpreferences/`](../home/Alfred.alfredpreferences/) is
  stored in the repo, but not automatically applied.

## Chezmoi Naming Conventions (How Source Maps To Installed Files)

Chezmoi uses filename conventions to decide where things land.

Common patterns in this setup:

- [`home/dot_config/...`](../home/dot_config/...) -> `~/.config/...`
- [`home/dot_*`](../home/dot_*) -> `~/.<name>` (for example:
  [`home/dot_zsh/`](../home/dot_zsh/) -> `~/.zsh/`)
- [`home/private_dot_ssh/...`](../home/private_dot_ssh/...) -> `~/.ssh/...` (and
  treated as private by chezmoi)
- `executable_foo` -> installs as an executable file named `foo`
- `readonly_foo` -> installs as `foo` with `0444` permissions (read-only); used
  for config files that should not be modified by external tools at runtime
- `exact_` prefix in a directory name means "exact directory" (chezmoi does not
  merge it with existing contents)

This is why you may see paths like:

- [`home/dot_config/exact_nvim/exact_lua/`](../home/dot_config/exact_nvim/exact_lua/)
  in the repo
- but `~/.config/nvim/lua/` on disk

## The Data Flow

This setup is intentionally declarative:

1. You answer prompts in
   [`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl).
2. Templates in [`home/`](../home/) render differently depending on those
   values.
3. Hooks in [`home/.chezmoiscripts/`](../home/.chezmoiscripts/) install / update
   tools based on the rendered config.
4. Re-running `chezmoi apply` converges you back to the intended state.

## Dynamic AI Context Merging

Because AI tools (like OpenCode, Cursor, Gemini, and Pi) often rewrite their
config files during runtime, rendering templates directly into those files
causes conflicts. Instead, this architecture uses **Profile-Based Merging**:

- MCP server definitions for Cursor, Claude Code, and Pi share a single
  canonical registry at
  [`home/.chezmoidata/mcp_servers.yaml`](../home/.chezmoidata/mcp_servers.yaml).
  Each entry declares a `work_only` flag so work-specific servers are filtered
  at generation time.
- During `chezmoi apply`, the unified script
  `run_onchange_after_07-generate-mcp-configs.sh.tmpl` calls
  [`scripts/generate_mcp_configs.py`](../scripts/generate_mcp_configs.py) once
  and writes the result to all three tools (Cursor, Claude Code, Pi).
- Other tools with different MCP schemas (Gemini) keep their own source files
  but follow the same work/personal profile-based merging via separate scripts.
- This creates a hard boundary between work contexts (which load work-specific
  MCP servers) and personal contexts.

### Shared Library (`scripts/chezmoi_lib.sh`)

All `run_onchange_after_07-merge-*` scripts source a shared shell library at
[`scripts/chezmoi_lib.sh`](../scripts/chezmoi_lib.sh) for common operations:

| Function                       | Purpose                                               |
| ------------------------------ | ----------------------------------------------------- |
| `chezmoi_pick_src`             | Resolve work vs personal source path                  |
| `chezmoi_write_if_changed`     | Atomic string write, skip if content unchanged        |
| `chezmoi_install_if_changed`   | File copy via `install(1)`, skip if content unchanged |
| `chezmoi_get_litellm_api_base` | Fetch and normalize LiteLLM URL from `pass`           |
| `chezmoi_record_checksum`      | Record file sha256 in the managed-configs manifest    |

After each write, the helpers record the target file's sha256 checksum in
`~/.local/state/chezmoi/managed_configs.tsv`. The `,doctor` command reads this
manifest to detect config drift — files modified externally by AI tools at
runtime.

To add a new AI tool config, create work/personal source files and a merge
script that sources the library — typically 5–10 lines of tool-specific logic.

## Hooks (Automation)

The most important concept for understanding "what happens" is the hook naming:

- `run_once_before_*` runs once before apply work.
- `run_once_after_*` runs once after apply work.
- `run_onchange_after_*` runs after apply _when the tracked inputs change_.

Examples in this repo:

| Hook                                                                                                                                                          | Purpose                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| [`home/.chezmoiscripts/run_once_before_00-install-xcode.sh`](../home/.chezmoiscripts/run_once_before_00-install-xcode.sh)                                     | Xcode CLT               |
| [`home/.chezmoiscripts/run_once_after_01-install-brew.sh`](../home/.chezmoiscripts/run_once_after_01-install-brew.sh)                                         | Homebrew install        |
| [`home/.chezmoiscripts/run_once_after_02-install-fish.sh`](../home/.chezmoiscripts/run_once_after_02-install-fish.sh)                                         | Fish install            |
| [`home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`](../home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl) | Brew bundle             |
| [`home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl`](../home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl)       | ASDF plugins + versions |
| [`home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl`](../home/.chezmoiscripts/run_onchange_after_05-install-uv-versions.sh.tmpl)         | UV Python versions      |

Many hooks embed `sha256sum` comments that reference template content. That is
how the "run on change" behavior is tied to specific files.

## Work vs Personal Split

The primary decision point is the `isWork` prompt in
[`home/.chezmoi.toml.tmpl`](../home/.chezmoi.toml.tmpl). It is used to:

- conditionally include certain tools/plugins
- choose which identity config is rendered
- choose which secrets/setup steps run

## External Assets

[`home/.chezmoiexternal.toml`](../home/.chezmoiexternal.toml) is used for things
you want updated regularly but don't want to vendor into your dotfiles repo.

Current externals:

| External           | Purpose                     |
| ------------------ | --------------------------- |
| `tpm`              | tmux plugin manager         |
| `EmmyLua.spoon`    | Hammerspoon Lua annotations |
| `lowfi` data files | Background music tracklists |
| `bat` themes       | Syntax highlighting themes  |
