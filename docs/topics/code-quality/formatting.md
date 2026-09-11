# Formatting

This repo uses per-language formatters to keep source files consistent. The root `package.json` only shims the docs site scripts and pulls no formatter — formatters are installed via Homebrew, except `,format-md` which is a repo-provided script deployed to `~/bin/,format-md` via chezmoi.

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

The pre-commit hook uses this file-argument mode to repair only staged paths before it hands off to `bin/check --staged`.

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

`bin/fmt` runs the per-language formatter groups concurrently, since each group (except the markdown chain) operates on a disjoint set of files. The markdown chain (`,format-md` → `markdownlint --fix` → `prettier`) stays sequential internally because all three steps mutate the same `.md` files in a required order; `prettier` also handles JSON/YAML in that same bulk invocation.

`,format-md` leaves files outside recognized AI paths unchanged, including their existing prose wraps and frontmatter. In AI Markdown, it preserves authored sentence and clause breaks. It joins plain mid-sentence continuation lines only when their indentation matches and the complete joined line fits the soft 140-character boundary. Existing long lines can split at sentence or strong clause boundaries; an unsplittable sentence stays long. Paragraphs containing ambiguous markup such as inline code, links, or URLs retain their existing lines. Explicit Markdown line breaks, frontmatter, fenced and indented code, tables, headings, and blank lines are preserved. These guarantees describe this script; the other tools in the formatting chain still apply their own formatting.

AI detection covers `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `copilot-instructions.md`, and their chezmoi `readonly_` names. Directory detection covers shared `.agents/{skills,hooks,references}/`, `.github/instructions/`, managed skill and Markdown agent-profile directories for the configured harnesses, and Cursor's local `k-sop` rule. Chezmoi `exact_skills`, `exact_hooks`, `exact_references`, and `exact_agents` source directories use the same rule. The complete path list lives in `AI_INSTRUCTION_PATH_MARKERS` in [`home/exact_bin/executable_,format-md`](../../../home/exact_bin/executable_,format-md). Detection handles Conform's `.conform.<random>.<filename>` temporary names and Windows separators. It does not extend Markdown classification to `.md.tmpl`, TOML, or plain text files.

Each group's output is buffered and flushed in a fixed order after all groups finish, so logs stay readable rather than interleaving. The overall exit code is the OR of every group's status, so a failure (or a missing tool) in any group still fails the run.

## Editor integration

[`.editorconfig`](../../../.editorconfig) provides baseline indent/whitespace rules that most editors (VSCode, Neovim, JetBrains, etc.) pick up automatically.

Neovim uses `conform.nvim` to run the same formatters on save. Both paths read from the same config files (`.prettierrc`, `.stylua.toml`, `ruff.toml`, `.editorconfig`) so editor formatting and `bin/fmt` always agree. Go linting is separate: Neovim's `nvim-lint` registry key is `golangcilint`, while the installed executable/Mason package remains `golangci-lint`.

YAML uses a `printWidth: 200` override in `.prettierrc` so prettier handles indentation without wrapping long command strings that embed shell and Go template syntax.

Template files (`.fish.tmpl`, `.lua.tmpl`) are excluded from `bin/fmt` because standalone formatters cannot parse Go template syntax. In Neovim, these are handled by chezmoi-aware formatter wrappers that strip template directives before formatting and restore them after.

Extensionless shell and Python scripts are detected from a shebang only after a text-safe probe, so binary files without extensions are skipped instead of emitting null-byte warnings during `bin/fmt --check`.

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
