# CRUSH.md - Dotfiles Development Guide

## Build/Test/Lint Commands

- **Apply changes**: `chezmoi apply` (applies all dotfile changes)
- **Dry run**: `chezmoi diff` (preview changes before applying)
- **Re-run scripts**: `chezmoi apply --force` (force re-run of scripts)
- **Test single file**: `chezmoi cat ~/.config/file` (preview rendered template)
- **Validate templates**: `chezmoi execute-template < file.tmpl`
- **Lua formatting**: `stylua .` (in nvim config directory)
- **Shell formatting**: Uses shfmt via EditorConfig settings
- **History sync**: `fish-history-merge.py` (custom 1Password-based sync)

## Code Style Guidelines

### File Organization

- Use chezmoi prefixes: `dot_` for dotfiles, `private_` for sensitive files, `executable_` for scripts
- Templates end with `.tmpl` and use Go template syntax
- Scripts in `.chezmoiscripts/` follow naming: `run_[once|onchange]_[before|after]_NN-description.sh.tmpl`

### Formatting & Indentation

- **Default**: 2 spaces, UTF-8, LF line endings, trim trailing whitespace
- **Go/Makefiles**: tabs, 4 spaces
- **Python**: 4 spaces
- **Lua**: 2 spaces, 120 column width (stylua.toml)
- **Shell**: shfmt formatting (no binary_next_line, no function_next_line)

### Naming Conventions

- Fish functions: snake_case with descriptive names
- Lua modules: lowercase with hyphens (e.g., `run-jest-in-split.lua`)
- Shell scripts: kebab-case with descriptive prefixes
- Config files: follow tool conventions

### Templates & Variables

- Use `{{ .isWork }}` for work/personal conditional logic
- Use `{{ .chezmoi.* }}` for system-specific values
- Quote string values in templates: `{{ .email | quote }}`
- Test template rendering before applying

### Error Handling

- Fish functions: return non-zero on error, use descriptive error messages
- Shell scripts: use `set -euo pipefail` for strict error handling
- Lua: use pcall for error-prone operations
- Always validate required dependencies before use

### Brewfile Management

- **Location**: `home/readonly_dot_Brewfile.tmpl`
- **Structure**: Highly organized with detailed categorization and consistent formatting
- **Section Format**:
  ```
  # ==============================================================================
  # SECTION NAME IN ALL CAPS
  # Brief description of what this section contains
  # ==============================================================================
  ```
- **Entry Format**: Each brew/cask entry includes a descriptive comment with URL
- **Categories**: Core dependencies, shell tools, editors, file operations, git tools, security, media, applications, etc.
- **Conditional Logic**: Uses `{{ if ne .isWork true }}` for personal-only packages
- **Adding Entries**: Place in appropriate existing category or create new section following same format

### History Management (Custom 1Password Sync)

- **Implementation**: `~/.config/fish/my/history-sync/fish-history-merge.py`
- **Purpose**: Merges local and remote fish history files chronologically
- **Features**: Deduplicates commands, keeps most recent timestamps, preserves paths
- **Usage**: `fish-history-merge.py <local_history> <remote_history> <output_file>`
- **Integration**: Designed to work with 1Password for secure history synchronization
