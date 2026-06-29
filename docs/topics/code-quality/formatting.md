# Formatting

This repo uses per-language formatters to keep source files consistent. No `package.json` or yarn — formatters are installed via Homebrew, except `,unwrap-md` which is a repo-provided script deployed to `~/bin/,unwrap-md` via chezmoi.

## Quick start

Format everything:

```bash
bin/fmt
```

With no file arguments, `bin/fmt` covers tracked files plus untracked, non-ignored files so new command libraries and docs are checked before staging.

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
bin/fmt docs/topics/code-quality/formatting.md home/dot_config/exact_nvim/readonly_init.lua
```

## Formatters

| Type                      | Formatter               | Config file                                                                                                                  |
| ------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Markdown, JSON, YAML      | `prettier`              | [`.prettierrc`](../../../.prettierrc)                                                                                        |
| Markdown (lint)           | `markdownlint`          | `~/.markdownlint.jsonc`                                                                                                      |
| Shell (`.sh`, `.sh.tmpl`) | `shfmt`                 | [`.editorconfig`](../../../.editorconfig) (`[*.sh]` section)                                                                 |
| Lua (`.lua`)              | `stylua`                | [`.stylua.toml`](../../../.stylua.toml)                                                                                      |
| Fish (`.fish`)            | `fish_indent`           | Built-in style                                                                                                               |
| Python (`.py`)            | `ruff format`           | [`ruff.toml`](../../../ruff.toml)                                                                                            |
| Go (`.go`)                | `goimports` + `gofumpt` | (matches Neovim conform "goimports","gofumpt" + gopls; `bin/fmt` uses the same pair, falls back to `gofmt` only when absent) |

All formatters are declared in the Brewfile: [`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl) (under "BUILD SYSTEMS & DEVELOPMENT TOOLS").

## Concurrency

`bin/fmt` runs the per-language formatter groups concurrently, since each group (except the markdown chain) operates on a disjoint set of files. The markdown chain (`,unwrap-md` → `markdownlint --fix` → `prettier`) stays sequential internally because all three steps mutate the same `.md` files in a required order; `prettier` also handles JSON/YAML in that same bulk invocation.

`,unwrap-md` preserves deliberate hard wraps in AI-facing instruction files: SOP entrypoints (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md` and their chezmoi `readonly_*` sources) and Markdown under managed agent/skill directories, including hook and reference files. These files use line breaks as prompt-ingestion affordances; ordinary docs still unwrap to one physical line per logical paragraph.

Each group's output is buffered and flushed in a fixed order after all groups finish, so logs stay readable rather than interleaving. The overall exit code is the OR of every group's status, so a failure (or a missing tool) in any group still fails the run.

## Editor integration

[`.editorconfig`](../../../.editorconfig) provides baseline indent/whitespace rules that most editors (VSCode, Neovim, JetBrains, etc.) pick up automatically.

Neovim uses `conform.nvim` to run the same formatters on save. Both paths read from the same config files (`.prettierrc`, `.stylua.toml`, `ruff.toml`, `.editorconfig`) so editor formatting and `bin/fmt` always agree.

YAML uses a `printWidth: 200` override in `.prettierrc` so prettier handles indentation without wrapping long command strings that embed shell and Go template syntax.

Template files (`.fish.tmpl`, `.lua.tmpl`) are excluded from `bin/fmt` because standalone formatters cannot parse Go template syntax. In Neovim, these are handled by chezmoi-aware formatter wrappers that strip template directives before formatting and restore them after.

## Ignored paths

Vendored/third-party code is excluded from formatting:

- `home/Alfred.alfredpreferences/` — vendored Alfred workflows
- chezmoi `symlink_*` sources (e.g. `symlink_AGENTS.md`) hold a symlink target path rather than content, so they are skipped by the markdown linters
- Prettier has its own ignore list in [`.prettierignore`](../../../.prettierignore)

## Verification

```bash
bin/fmt --check
```

Exit 0 means all files are formatted. Exit 1 lists unformatted files.

## Related

- [Contributing](../../../CONTRIBUTING.md) — repo validation, pre-commit hook, docs hygiene
- [Packages](../core/packages/index.md)
- [Editor: Neovim](../editor/neovim/index.md)
