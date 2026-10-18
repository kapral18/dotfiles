---
sidebar_position: 2
title: LSP and source jumps
---

# LSP and source jumps

## Configuration schemas

JSON/JSONC (`jsonls`), YAML (`yamlls`), and TOML (`tombi`) use schemas for option completion, `K` hover documentation, and validation. Schema references live in the configuration files: a top-level `$schema` field for JSON/JSONC, a `# yaml-language-server: $schema=URL` comment for YAML, or a `#:schema URL` header followed by a blank line for TOML. Chezmoi preserves these references when it deploys the files, so hints work while editing either copy without a registry of source filenames.

JSON and YAML use the installed SchemaStore catalog for standard filenames; Tombi retains its standard catalog. YAML keeps the existing custom associations and Kubernetes detection. Schema-companion's LSP source remains available for manual selection, but automatic LSP matching is disabled: yamlls already applies its own associations, and reapplying them through schema-companion replaces shared filename patterns with one buffer URI.

| Configuration family in this repo                                                                                                         | Schema coverage                                                                               |
| ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Claude settings and llama.cpp settings templates                                                                                          | Claude Code Settings, via `$schema` in settings and templates                                 |
| Claude plugin manifests                                                                                                                   | Claude Code Plugin Manifest, via `$schema` in each manifest                                   |
| Pi settings and model definitions                                                                                                         | Pi's published `settings.schema.json` and `models.schema.json`, for source and deployed files |
| OpenCode                                                                                                                                  | OpenCode's config schema; its existing `$schema` also applies                                 |
| Markdownlint                                                                                                                              | Markdownlint schema via `$schema`                                                             |
| GitHub CLI config and hosts, lazygit, gh-dash                                                                                             | Each application's schema, including gh-dash's shared YAML fragment and config template       |
| Codex                                                                                                                                     | Codex config schema via its existing `#:schema` header                                        |
| Chezmoi config, mise, Starship, StyLua                                                                                                    | Their published schemas, including renamed source files and config templates                  |
| Yazi config and theme                                                                                                                     | Separate official Yazi and theme schemas for source and deployed files                        |
| `package.json`, `tsconfig.json`, `pyrightconfig.json`, `.prettierrc`, `pnpm-workspace.yaml`, GitHub workflows, skill `agents/openai.yaml` | Standard filenames already match SchemaStore; YAML now loads these catalog associations too   |
| `ruff.toml`, `.stylua.toml` and other standard TOML configs                                                                               | Tombi's standard catalog                                                                      |

Pi publishes its schemas with the coding-agent package; Yazi publishes [configuration schemas](https://yazi-rs.github.io/docs/configuration/overview/). [Tombi's schema support](https://tombi-toml.github.io/tombi/docs/configuration/) accepts per-file headers and project-specific schemas. Published schemas can lag an installed application's options. The language servers fetch schema documents and need network access when a document is not cached.

Chezmoi JSON, JSONC, YAML, and TOML templates retain their compound `*.chezmoitmpl` filetypes and now attach the corresponding language server. Automatic formatting skips those raw templates. The server still parses the source as the underlying language: standalone `{{ if ... }}` blocks can produce syntax diagnostics or limit completion near the directive. Schemas do not evaluate templates. Comment-wrapped directives that already retain a native filetype keep their existing behavior.

The remaining files have syntax support or native language tooling, but no verified matching option schema is configured:

| Configuration family                                                                                                                                             | Current boundary                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| OMP `config.yml.tmpl`, `models.yml`, `WATCHDOG.yml`                                                                                                              | Runtime definitions exist, but no matching published JSON Schema was found in the installed package                  |
| 1Password SSH agent                                                                                                                                              | SchemaStore lists a schema, but its published URL returned HTTP 404 on 2026-10-19; no schema reference is added      |
| Karabiner, lgtm, tuicr, redtab                                                                                                                                   | No matching published schema was verified; JSON/TOML syntax tooling remains available                                |
| pnpm global `config.yaml.tmpl`                                                                                                                                   | This is a different configuration surface from `pnpm-workspace.yaml`; the workspace schema is not assigned to it     |
| `.chezmoiexternal.toml`                                                                                                                                          | External-source declarations have a different format from chezmoi's own config                                       |
| Neovim `.neoconf.json`                                                                                                                                           | Neoconf generates schemas at runtime; that plugin is not active in this config                                       |
| Claude `hooks.json` with `modules`, Codex model catalogs, Pi subagent extension config, sem telemetry                                                            | Custom or internal formats; their parent application's settings schema does not describe them                        |
| MCP registry, app-icon mapping, tmux GitHub picker YAML, artifact theme JSON, Docusaurus `_category_.json`                                                       | Repo-specific data or metadata without a verified schema association                                                 |
| Lockfiles                                                                                                                                                        | Generated data; no settings schema is applied                                                                        |
| Lua, TypeScript/JavaScript, Python, shell/Fish, Ruby/Brewfiles                                                                                                   | Existing language tooling; application APIs depend on the types or annotations available to that tooling             |
| INI, `.editorconfig`, llama.cpp model presets, tmux/Ghostty/btop/bat/tig configs, SSH/GPG/Git/readline/curl/ripgrep configs, `.gemrc`, package lists and crontab | Application-specific syntax or plain text, without an option schema integration                                      |
| Crush `crushrc`                                                                                                                                                  | Shell-like configuration DSL, not a JSON config                                                                      |
| KDL and XML                                                                                                                                                      | Existing syntax tooling; XML's LemMinX can use a declared schema, but no additional repo-specific schema is assigned |

## LSP code actions

`<leader>ca` and `<leader>cA` show code actions with `fzf-lua`, not Neovim's default `vim.ui.select`.

`fzf-lua` is key-triggered and registers `vim.ui.select` globally only after first load, so these mappings call `fzf-lua`'s `lsp_code_actions` helper directly. That keeps the code-action picker consistent even early in a session.

## TypeScript tools

[`plugins/typescript-tools.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_typescript-tools.lua) disables the generic `ts_ls` client and uses `pmizio/typescript-tools.nvim` for JS/TS buffers. Mason installs `typescript-language-server` because that package vendors `node_modules/typescript/lib/tsserver.js`, which `typescript-tools` uses when the project and global npm installs do not provide `typescript`. The same config narrowly filters known false-positive diagnostics for managed Pi/OMP runtime extensions: their package and Node types come from the consuming runtime, not from a local chezmoi `node_modules`.

## Rust analyzer

[`plugins/rust.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_rust.lua) configures rustaceanvim with:

- `cargo.allFeatures = true`
- `check.command = "clippy"`
- `checkOnSave = true`

Rustaceanvim is the only rust-analyzer client. [`plugins/lsp.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lsp.lua) excludes the generic `nvim-lspconfig` `rust_analyzer` server from Mason-lspconfig auto-enable while Mason still installs the binary. That avoids duplicate definition/reference rows from two clients.

## Lua LS workspace scope

`lua_ls` root detection is narrowed for chezmoi paths. A file under the chezmoi source tree uses its own directory as the workspace root instead of the repo `.git` root, avoiding full-tree scans and the "More than 100000 files have been scanned" warning.

Root resolution priority in [`plugins/lua.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lua.lua):

1. Real lua_ls project markers: `.luarc.json` / `.luarc.jsonc`.
2. Chezmoi source-tree file directory.
3. Formatter/linter markers such as `.stylua.toml`, `stylua.toml`, `selene.toml`.
4. `.git`.

The chezmoi check must precede formatter markers because `.stylua.toml` lives at the chezmoi repo root.

Two Neovim 0.11+ details matter:

- Native LSP `root_dir` signature is `fun(bufnr, on_dir)`: the chosen root is passed to `on_dir`, not returned.
- lazydev's lspconfig integration is disabled so it does not override `root_dir` with `.git` root detection. Its library/annotation injection still works.

## Jump to source, not target

When editing chezmoi source files, language servers often resolve symbols against deployed copies under `$HOME`. A plain `gd` or `gr` from `home/dot_config/exact_nvim/...` could jump to `~/.config/nvim/...`, which `chezmoi apply` overwrites.

[`util/chezmoi_lsp.lua`](../../../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_chezmoi_lsp.lua) wraps `vim.lsp.buf_request{,_sync}` and rewrites location results so managed targets map back to their source path via `chezmoi source-path`.

Scope:

- only when the originating buffer is a chezmoi source file.
- only location methods: definition, declaration, type definition, implementation, references.
- hover, formatting, and code actions pass through untouched.
- plugin/runtime paths are skipped before any `chezmoi` probe.
- resolutions, including misses, are cached.

Line/column are preserved. For templates, rows may drift but the source file is still correct.
