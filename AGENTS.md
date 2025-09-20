# Repository Guidelines

## Project Structure & Module Organization

- Source state is in `home/`, mapping to `$HOME`.
- Prefixes: `dot_` → dotfiles (e.g., `home/dot_config/nvim` → `~/.config/nvim`), `private_` → secrets, `executable_` → scripts, `exact_` → exact dir mirroring (e.g., `home/exact_bin` → `~/bin`).
- Scripts live in `.chezmoiscripts/` using `run_[once|onchange]_[before|after]_NN-description.sh.tmpl`.
- Templates are `*.tmpl` with Go template syntax; use for conditional rendering.
- Brewfile template: `home/readonly_dot_Brewfile.tmpl` (organized sections, personal-only via `{{ if ne .isWork true }}`).

## Build, Test, and Development Commands

- Preview changes: `chezmoi diff` (no writes).
- Apply changes: `chezmoi apply`; force script reruns: `chezmoi apply --force`.
- Preview a rendered file: `chezmoi cat ~/.config/<file>`.
- Validate a template: `chezmoi execute-template < path/to/file.tmpl`.
- Neovim Lua format (run in `home/dot_config/exact_nvim`): `stylua .`.
- Shell format: shfmt via EditorConfig settings.
- History sync helper: `f-history-sync` (merges Fish history via 1Password).

## Coding Style & Naming Conventions

- Indentation: default 2 spaces, UTF-8, LF; trim trailing whitespace.
- Language specifics: Go/Makefiles use tabs; Python 4 spaces; Lua 2 spaces (120 cols via `stylua.toml`).
- Shell: use shfmt (no binary_next_line, no function_next_line); scripts must `set -euo pipefail` and validate deps.
- Naming: Fish functions snake_case; Lua module files lowercase-hyphen (e.g., `run-jest-in-split.lua`); shell scripts kebab-case.
- Chezmoi: prefer `dot_*/private_*/executable_*/exact_*`; templates end with `.tmpl`.
- Templates: use `{{ .isWork }}` for work/personal logic; quote strings (e.g., `{{ .email | quote }}`).

## Testing Guidelines

- Keep `chezmoi diff` focused and intentional before PRs.
- Validate templates with `chezmoi execute-template` and spot-check via `chezmoi cat`.
- Scripts: return non-zero on error; add clear messages; test with `chezmoi apply --force` and targeted runs.
- Formatting checks: `stylua .` for Lua; shfmt/EditorConfig for shell.
- Git diffs: prefer icdiff aliases (`git ddiff`, `git dshow`, `git dlog`).

## Commit & Pull Request Guidelines

- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`) as in repo history.
- PRs include: concise summary, rationale, `chezmoi diff` snippet, affected paths (e.g., `home/dot_config/...`).
- Link issues when applicable; attach screenshots/snippets for UX-facing changes (Hammerspoon, Neovim UI).

## Security & Configuration Tips

- Never commit secrets; use `private_` files and 1Password integration.
- Respect the work/personal split with `{{ .isWork }}`; guard machine-specific state behind conditionals.
