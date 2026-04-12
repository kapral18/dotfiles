# Formatting

Back: [`docs/categories/index.md`](index.md)

This repo uses per-language formatters to keep source files consistent. No `package.json` or npm — formatters are installed via Homebrew, except `unwrap-md` which is a repo-provided script deployed to `~/bin/unwrap-md` via chezmoi.

## Quick start

Format everything:

```bash
bin/fmt
```

Check without writing (CI-friendly):

```bash
bin/fmt --check
```

Format one language:

```bash
bin/fmt --type md
bin/fmt --type lua
```

Format specific files:

```bash
bin/fmt docs/categories/formatting.md home/dot_config/exact_nvim/init.lua
```

## Formatters

| Type                      | Formatter      | Config file                                               |
| ------------------------- | -------------- | --------------------------------------------------------- |
| Markdown, JSON, YAML      | `prettier`     | [`.prettierrc`](../../.prettierrc)                        |
| Markdown (lint)           | `markdownlint` | `~/.markdownlint.jsonc`                                   |
| Shell (`.sh`, `.sh.tmpl`) | `shfmt`        | [`.editorconfig`](../../.editorconfig) (`[*.sh]` section) |
| Lua (`.lua`)              | `stylua`       | [`.stylua.toml`](../../.stylua.toml)                      |
| Fish (`.fish`)            | `fish_indent`  | Built-in style                                            |
| Python (`.py`)            | `ruff format`  | [`ruff.toml`](../../ruff.toml)                            |

All formatters are declared in the Brewfile: [`home/readonly_dot_Brewfile.tmpl`](../../home/readonly_dot_Brewfile.tmpl) (under "BUILD SYSTEMS & DEVELOPMENT TOOLS").

## Editor integration

[`.editorconfig`](../../.editorconfig) provides baseline indent/whitespace rules that most editors (VSCode, Neovim, JetBrains, etc.) pick up automatically.

Neovim uses `conform.nvim` to run the same formatters on save. Both paths read from the same config files (`.prettierrc`, `.stylua.toml`, `ruff.toml`, `.editorconfig`) so editor formatting and `bin/fmt` always agree.

YAML uses a `printWidth: 200` override in `.prettierrc` so prettier handles indentation without wrapping long command strings that embed shell and Go template syntax.

Template files (`.fish.tmpl`, `.lua.tmpl`) are excluded from `bin/fmt` because standalone formatters cannot parse Go template syntax. In Neovim, these are handled by chezmoi-aware formatter wrappers that strip template directives before formatting and restore them after.

## Ignored paths

Vendored/third-party code is excluded from formatting:

- `home/Alfred.alfredpreferences/` — vendored Alfred workflows
- Prettier has its own ignore list in [`.prettierignore`](../../.prettierignore)

## Verification

```bash
bin/fmt --check
```

Exit 0 means all files are formatted. Exit 1 lists unformatted files.

## Related

- Packages: [`docs/categories/packages.md`](packages.md)
- Editor (Neovim): [`docs/categories/editor-neovim.md`](editor-neovim.md)
