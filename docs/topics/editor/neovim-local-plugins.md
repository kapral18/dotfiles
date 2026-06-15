---
sidebar_position: 2
---

# Neovim local plugins

This config ships a set of small in-repo Lua plugins — loaders live in [`exact_plugins_local/`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/), and the heavier ones keep their implementation in `exact_plugins_local_src/`. They cover testing, git, ownership, refactors, the tmux bridge, screenshots, and quickfix/window ergonomics.

For the rest of the Neovim setup (structure, plugin manager, LSP, keymaps), see [Editor: Neovim](neovim.md).

## Testing: Jest In A Split (Local Plugin)

This is one of the most valuable "hidden" workflows.

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_run-jest-in-split.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_run-jest-in-split.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_run-jest-in-split.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_run-jest-in-split.lua)

Keymaps:

- `leader-tt` run nearest test
- `leader-tT` run entire file
- `leader-td` debug nearest test
- `leader-tD` debug entire file
- `leader-tu` update snapshots (nearest)
- `leader-tU` update snapshots (file)
- `leader-tq` close the test terminal

## Git: Commit Message Summarizer (Local Plugin)

In a `gitcommit` buffer, generate a Conventional Commit message from the staged diff (`git diff --cached`).

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_summarize-commit.lua.tmpl`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_summarize-commit.lua.tmpl)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_summarize-commit.lua)

Keymaps:

- `leader-aisc` summarize via Cloudflare Workers AI
- `leader-aiso` summarize via OpenRouter

Output format notes:

- Header: `type(scope?): summary`
- Bullet points: one bullet per changed functionality (or per distinct logical change)

Environment variables:

| Provider   | Required                                                            | Optional                                                                                                                                                                                                 |
| ---------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cloudflare | `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY` | `CLOUDFLARE_WORKERS_AI_MODEL` (default `@cf/moonshotai/kimi-k2.6`), `CLOUDFLARE_THINKING` (default `false`), `CLOUDFLARE_REASONING_EFFORT`                                                               |
| OpenRouter | `OPENROUTER_API_KEY`                                                | `OPENROUTER_MODEL` (default `moonshotai/kimi-k2.6`, routed as `moonshotai/kimi-k2.6:nitro`), `OPENROUTER_NITRO` (default `true`), `OPENROUTER_THINKING` (default `false`), `OPENROUTER_REASONING_EFFORT` |
| Gemini     | `GEMINI_API_KEY`                                                    | `GEMINI_MODEL` (default `gemini-flash-latest`), `GEMINI_MAX_OUTPUT_TOKENS`                                                                                                                               |

Transport failures are reported directly in the Neovim notification. For example, `curl exit 28` means the provider request reached the configured timeout; inspect `:messages` for the captured curl stderr/body preview.

## Ownership / CODEOWNERS Workflows (Local Plugins)

Show owner of the current file:

- Keymap: `leader-0`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua)

Search only paths owned by a team/owner:

- Keymaps: `leader-rg`, `leader-rG`, `leader-fd`, `leader-fD`
- Commands: `:OwnerCodeGrep`, `:OwnerCodeFd`, `:ListOwners`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua)

## Refactors: Move TS Exports (Local Plugin)

Select one or more exported declarations in visual mode, enter a target path (relative to the current file), and the plugin moves the selection into that file and re-wires every importer to point at the new location.

- Visual mode mapping: `leader-]`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_ts-move-exports.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_ts-move-exports.lua)

How it works:

1. Treesitter collects the exported binding names in the selection (`const`/`function`/`class`/`type`).
2. `textDocument/references` records every file that imports them.
3. Each export is renamed to a temporary placeholder, then the lines are moved into the target file (parent dirs are created; appended after a blank line if the file already exists).
4. Each referencing file is opened, and `typescript-tools`' add-missing-imports re-imports the placeholder from the new file.
5. The placeholder is renamed back to the original name from the new file; the LSP rename propagates the original name through every importer.

Requirements:

- Depends on the `typescript-tools` LSP client (`pmizio/typescript-tools.nvim`) being attached — it drives references, rename, and add-missing-imports. See [Editor: Neovim](neovim.md) for the TypeScript LSP setup.

## tmux Bridge: Send Text To The Right Pane (Local Plugin)

If you run a REPL/test watcher in tmux, you can send data from Neovim to the pane to the right.

- `leader-ad` send diagnostics
- `leader-al` send current line
- `leader-av` send selection
- `leader-ah` send git hunk
- `leader-ag` send git diff (file)

Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-tmux-right-pane.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_send-to-tmux-right-pane.lua)

## Jump Between Source And Test Files (Local Plugin)

If you keep `foo.ts` and `foo.test.ts` (or `.spec`, `_test`, etc) side-by-side, this mapping toggles between them.

- Keymap: `Ctrl-^`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_switch-src-test.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_switch-src-test.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_switch-src-test.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_switch-src-test.lua)

It supports extension fallbacks (ts <-> tsx <-> js <-> jsx) when the exact match does not exist.

## Open ESLint Config References (Local Plugin)

When your cursor is on an ESLint `extends`/plugin reference, this opens the actual file on disk (from `node_modules`).

- Keymap: `leader-sfe`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_open-eslint-path.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_open-eslint-path.lua)

## Copy Current Buffer To Quickfix Directories (Local Plugin)

If your quickfix list includes matches across multiple directories, this helper can copy the current file into each of those directories (useful for applying a file-based fix across multiple worktrees/sandboxes).

- Keymap: `leader-cb` (copy)
- Keymap: `leader-cB` (copy forced)
- Command: `:CopyBufferToQfDirs` (optional `force`)
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_copy-to-qf.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_copy-to-qf.lua)

## Code Screenshots (Local Plugin): `freeze`

Generate an image of code directly from Neovim using the `freeze` CLI.

- Homebrew formula (already managed by this repo's Brewfile): `brew "charmbracelet/tap/freeze"` in [`home/readonly_dot_Brewfile.tmpl`](../../../home/readonly_dot_Brewfile.tmpl)
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_freeze.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_freeze.lua)
- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_freeze.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_freeze.lua)

Commands:

- `:Freeze` - capture the whole buffer (or a range, e.g. `:10,40Freeze`)
- `:FreezeLine` - capture the current line

Behavior:

- Writes `~/Downloads/screenshots/freeze.png`
- Copies the PNG to clipboard (macOS) and opens the image after generation

## Toggle Window Width (Local Plugin)

Toggles the current window width between the previous value and a "fit to content" width.

- Keymap: `leader-=`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_toggle-win-width.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_toggle-win-width.lua)

## Winbar: Show Remainder Path (Local Plugin)

This config sets a custom winbar that shows the remainder of the current path in a compact way.

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_winbar.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_winbar.lua)

## Quickfix Ergonomics (Local Plugin)

Quickfix is treated as a first-class workflow. Add-ons:

- `:QFDedupe` dedupe entries
- `leader-rqi` filter include pattern
- `leader-rqx` filter exclude pattern
- inside quickfix window: `dd` removes an entry

Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_qf.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_qf.lua)

## Related

- [Editor: Neovim](neovim.md) — structure, plugin manager, LSP, keymaps
- [tmux Bridge target: tmux](../workflow/tmux/index.md)
