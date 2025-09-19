# AGENTS.md - Dotfiles Development Guide for AI Agents

## Build/Test/Lint Commands
- **Apply changes**: `chezmoi apply` (applies all dotfile changes)
- **Dry run**: `chezmoi diff` (preview changes before applying)
- **Test single file**: `chezmoi cat ~/.config/file` (preview rendered template)
- **Validate templates**: `chezmoi execute-template < file.tmpl`
- **Lua formatting**: `stylua .` (in nvim config directory)
- **Shell formatting**: Uses shfmt via EditorConfig settings

## Code Style Guidelines

### File Organization
- Use chezmoi prefixes: `dot_` for dotfiles, `private_` for sensitive files, `executable_` for scripts
- Templates end with `.tmpl` and use Go template syntax
- Scripts in `.chezmoiscripts/` follow naming: `run_[once|onchange]_[before|after]_NN-description.sh.tmpl`

### Formatting
- **Default**: 2 spaces, UTF-8, LF line endings, trim trailing whitespace
- **Lua**: 2 spaces, 120 column width (stylua.toml)
- **Shell**: shfmt formatting (no binary_next_line, no function_next_line)

### Templates & Variables
- Use `{{ .isWork }}` for work/personal conditional logic
- Quote string values: `{{ .email | quote }}`
- Test template rendering before applying

### Error Handling
- Fish functions: return non-zero on error, use descriptive error messages
- Shell scripts: use `set -euo pipefail` for strict error handling
- Always validate required dependencies before use