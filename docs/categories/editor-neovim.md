# Editor: Neovim

Back: [`docs/categories/index.md`](index.md)

This page explains what the Neovim setup in this repo enables, how it is
structured, and the workflows that are easy to miss if you only skim the config.

This page is written for IDE-first users (VSCode / JetBrains) who want to
understand the practical benefits and adopt useful parts gradually.

## What You Get

- A keyboard-first editor with discoverable keymaps (most maps have `desc`)
- Fast repo search (files, grep, changed-lines grep)
- Tight test loops for JS/TS (Jest) in an editor split
- Git ergonomics (hunks, history search, diffs)
- A set of local plugins that solve specific daily problems

## Where The Config Lives

- Source (in this repo): `home/dot_config/exact_nvim/`
- Install target (on disk): `~/.config/nvim/`

This setup uses `chezmoi` naming conventions where some directories are prefixed
with `exact_` in the source but are installed without that prefix.

Examples (source -> installed):

- `home/dot_config/exact_nvim/exact_lua/` -> `~/.config/nvim/lua/`
- `home/dot_config/exact_nvim/exact_after/` -> `~/.config/nvim/after/`

Leader keys:

- `mapleader` is space (`vim.g.mapleader = " "`)
- `maplocalleader` is `\`

See `home/dot_config/exact_nvim/exact_lua/exact_core/options.lua`.

Neovim itself is version-managed via ASDF:

- Plugins list: `home/asdf_plugins.tmpl`
- Version pin: `home/readonly_dot_tool-versions.tmpl`

## Quick Start

1. Apply dotfiles: `chezmoi apply`
2. Launch Neovim: `nvim`
3. Sync plugins: `:Lazy sync`

## Tree-sitter: Bundled Parsers And Startup Hangs

Neovim can load tree-sitter parsers from multiple places (runtimepath). In
practice, a broken parser under the user "site" directory can hang Neovim at
startup, especially if your last session opens a filetype that immediately
triggers that parser.

This config prefers Neovim's bundled parser for Markdown to reduce the chance
of a bad user-installed parser taking down the editor:

- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins/treesitter.lua`
- Helper: `home/dot_config/exact_nvim/exact_lua/exact_util/treesitter.lua`

Symptoms you might see:

- `nvim` appears to "freeze" (often when opening `*.md`)
- `nvim --clean` works but regular `nvim` does not

Local fix (if you hit this):

```bash
ls -la ~/.local/share/nvim/site/parser
rm -f ~/.local/share/nvim/site/parser/markdown.so
```

Note: the config also treats bundled/runtime parsers as "available" so
`nvim-treesitter` doesn't repeatedly try to auto-install languages that Neovim
already ships.

If you are IDE-first, start by learning:

- moving between files quickly
- searching within a repo
- running tests from inside the editor

## How To Discover Keymaps

This config installs `which-key`:

- Plugin: `home/dot_config/exact_nvim/exact_lua/exact_plugins/which-key.lua`

Most mappings are defined with descriptions in:

- `home/dot_config/exact_nvim/exact_lua/exact_core/keymaps.lua`

If you forget a shortcut, use `which-key` and your leader mappings as the
primary discovery mechanism.

## Customization Entry Points

Start here if you want to change behavior without spelunking the entire tree:

- Core options: `home/dot_config/exact_nvim/exact_lua/exact_core/options.lua`
- Core keymaps: `home/dot_config/exact_nvim/exact_lua/exact_core/keymaps.lua`
- Plugin configs: `home/dot_config/exact_nvim/exact_lua/exact_plugins/`

The corresponding installed paths are:

- `~/.config/nvim/lua/core/options.lua`
- `~/.config/nvim/lua/core/keymaps.lua`
- `~/.config/nvim/lua/plugins/`

How it's organized:

- `core/` is foundational editor behavior (options, keymaps, autocmds)
- `plugins/` is plugin configuration grouped by topic/language
- `plugins_local_src/` contains local plugins written specifically for this setup

Local plugins (written in this repo) live under:

- Source: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/`

These are the most workflow-specific parts of the config and usually the best
place to look when you want to understand *why* something exists.

The load list is explicitly declared in:

- `home/dot_config/exact_nvim/exact_lua/exact_core/init.lua`

## Starter Keymaps (High Signal)

Window navigation:

- `Ctrl-h/j/k/l` moves between splits
- `leader-|` split right, `leader--` split below

Buffers:

- `leader-bb` or `leader-<backtick>` toggles last buffer
- `[b` and `]b` prev/next buffer

Search:

- `leader-Space` files (fzf)
- `leader-sg` live grep (fzf)
- `leader-/` grep current buffer

Explorer:

- `leader-e` Neo-tree explorer (cwd)
- `leader-ge` Neo-tree git status

Diagnostics / quickfix:

- `leader-cd` line diagnostics
- `[d` and `]d` prev/next diagnostic
- `leader-xq` toggle quickfix, `leader-xl` toggle location list

Git:

- `[h` and `]h` prev/next hunk
- `leader-ghp` preview hunk inline

## Search And Navigation Workflows

Repo search is centered around `fzf-lua`:

- Config: `home/dot_config/exact_nvim/exact_lua/exact_plugins/fzf.lua`

Useful mappings (all are defined in that file):

- `leader-sg` live grep in cwd
- `leader-se` grep in changed lines (git status)
- `leader-sE` grep in changed lines (branch)
- `leader-sf` grep in changed files (git status)
- `leader-sF` grep in changed files (branch)

File explorers:

- Neo-tree: `home/dot_config/exact_nvim/exact_lua/exact_plugins/neo-tree.lua`
- Yazi: same file (`mikavilpas/yazi.nvim`)
- Oil: same file (`stevearc/oil.nvim`)

Neo-tree has a couple of "workflow" mappings inside the tree:

- `leader-nf` find in selected directory
- `leader-ng` grep in selected directory
- `leader-yp` copy relative path

## Testing: Jest In A Split (Local Plugin)

This is one of the most valuable "hidden" workflows.

- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/run-jest-in-split.lua`
- Source: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/run-jest-in-split.lua`

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

- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/summarize-commit.lua`
- Source: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/summarize-commit.lua`

Keymaps:

- `leader-aisl` summarize via Ollama (local)
- `leader-aisc` summarize via Cloudflare Workers AI
- `leader-aiso` summarize via OpenRouter

Env (for hosted providers):

- Cloudflare: `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY`
- OpenRouter: `OPENROUTER_API_KEY` (optional: `OPENROUTER_MODEL`)

## Git Workflows

Hunks, blame, and history search are configured here:

- `home/dot_config/exact_nvim/exact_lua/exact_plugins/git.lua`

Highlights:

- gitsigns hunk navigation (`[h` / `]h`) and stage/reset hunk mappings under `leader-gh*`
- Diffview mappings under `leader-df*`
- History search (`AdvancedGitSearch`) under `leader-ga*`

## Ownership / CODEOWNERS Workflows (Local Plugins)

Show owner of the current file:

- Keymap: `leader-0`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/show-file-owner.lua`

Search only paths owned by a team/owner:

- Keymaps: `leader-rg`, `leader-rG`, `leader-fd`, `leader-fD`
- Commands: `:OwnerCodeGrep`, `:OwnerCodeFd`, `:ListOwners`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/owner-code-search.lua`

## Refactors: Move TS Exports (Local Plugin)

- Visual mode mapping: `leader-]`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/ts-move-exports.lua`

## AI Data Capture (Local Plugin)

This config includes a local helper to build a curated `~/ai_data.txt`.

- Keymaps: `leader-ais` (append buffer), `leader-aiS` (replace)
- Neo-tree integration: save/remove selected path from the tree
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/save-ai-data.lua`

## tmux Bridge: Send Text To The Right Pane (Local Plugin)

If you run a REPL/test watcher in tmux, you can send data from Neovim to the
pane to the right.

- `leader-ad` send diagnostics
- `leader-al` send current line
- `leader-av` send selection
- `leader-ah` send git hunk
- `leader-ag` send git diff (file)

Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/send-to-tmux-right-pane.lua`

## Jump Between Source And Test Files (Local Plugin)

If you keep `foo.ts` and `foo.test.ts` (or `.spec`, `_test`, etc) side-by-side,
this mapping toggles between them.

- Keymap: `Ctrl-^`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/switch-src-test.lua`
- Source: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/switch-src-test.lua`

It supports extension fallbacks (ts <-> tsx <-> js <-> jsx) when the exact match
does not exist.

## Open ESLint Config References (Local Plugin)

When your cursor is on an ESLint `extends`/plugin reference, this opens the
actual file on disk (from `node_modules`).

- Keymap: `leader-sfe`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/open-eslint-path.lua`

## Copy Current Buffer To Quickfix Directories (Local Plugin)

If your quickfix list includes matches across multiple directories, this helper
can copy the current file into each of those directories (useful for applying a
file-based fix across multiple worktrees/sandboxes).

- Keymap: `leader-cb` (copy)
- Keymap: `leader-cB` (copy forced)
- Command: `:CopyBufferToQfDirs` (optional `force`)
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/copy-to-qf.lua`

## Toggle Window Width (Local Plugin)

Toggles the current window width between the previous value and a "fit to
content" width.

- Keymap: `leader-=`
- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/toggle-win-width.lua`

## Winbar: Show Remainder Path (Local Plugin)

This config sets a custom winbar that shows the remainder of the current path
in a compact way.

- Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/winbar.lua`

## Quickfix Ergonomics (Local Plugin)

Quickfix is treated as a first-class workflow. Add-ons:

- `:QFDedupe` dedupe entries
- `leader-rqi` filter include pattern
- `leader-rqx` filter exclude pattern
- inside quickfix window: `dd` removes an entry

Loader: `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/qf.lua`

## Small Quality-Of-Life Commands

Defined in `home/dot_config/exact_nvim/exact_lua/exact_core/keymaps.lua`:

- `:LargeFiles` populate quickfix with very large tracked files
- `:WW` / `:WWW` write without triggering autocmds
- `:MakeTags` generate ctags respecting `.gitignore`
- `leader-yp` / `leader-yP` copy path to clipboard (relative / absolute)

## What Problems This Setup Focuses On

- Fast navigation and editing with a consistent keyboard-first model
- Tight test loops (run tests, rerun, jump to failures) without leaving editor
- Repeatable refactors that update imports/exports predictably
- Working in large repos (ownership, ripgrep/fzf tooling, git ergonomics)

## IDE Translation (Mental Model)

- VSCode/JetBrains tabs map more closely to Neovim buffers.
- IDE "Problems" panel maps well to Neovim's quickfix list.
- Multi-cursor exists, but composition (motions + operators + textobjects) is
  the main scaling strategy.

If you are used to clicking around panels in an IDE, your first bridge skill is
to rely on:

- fzf pickers for file/search navigation
- quickfix for diagnostics and search results
- a file explorer for local context (Neo-tree/Yazi/Oil)

## Verification And Troubleshooting

High-signal checks:

```bash
nvim --version
nvim "+Lazy! sync" +qa
nvim "+checkhealth" +qa
```

Inside Neovim, verify key workflows:

- run `:map <leader>tt` and confirm Jest mapping exists.
- open quickfix and test `:QFDedupe`.
- open a git repo file and test gitsigns navigation (`[h` / `]h`).

If keymaps/plugins seem missing:

- confirm `chezmoi apply` succeeded for `home/dot_config/exact_nvim/`.
- confirm plugin install completed (`:Lazy` UI / sync output).
- confirm you are running the expected Neovim binary/version from ASDF.

## Related

- Repo overview and install: [`README.md`](../../README.md)
- Neovim local README (short pointer): [`home/dot_config/exact_nvim/README.md`](../../home/dot_config/exact_nvim/README.md)
- Terminals + tmux: [`docs/categories/terminals-and-tmux.md`](terminals-and-tmux.md)
