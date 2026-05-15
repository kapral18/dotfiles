# Editor: Neovim

This page explains what the Neovim setup in this repo enables, how it is structured, and the workflows that are easy to miss if you only skim the config.

This page is written for IDE-first users (VSCode / JetBrains) who want to understand the practical benefits and adopt useful parts gradually.

## What You Get

- A keyboard-first editor with discoverable keymaps (most maps have `desc`)
- Fast repo search (files, grep, changed-lines grep)
- Tight test loops for JS/TS (Jest) in an editor split
- Git ergonomics (hunks, history search, diffs)
- A set of local plugins that solve specific daily problems
- Project-aware formatting for web files (JS/TS/JSON): prefer Oxfmt when the repo declares it, else Biome, else Prettier
- ESLint and Oxlint diagnostics can coexist; formatting remains single-tool to avoid conflicts
- Markdown and MDX: Prettier (via conform.nvim) is invoked with `--prose-wrap=preserve` so body text is not reflowed to `printWidth` from the editor, even when a project config sets `proseWrap: "always"`. For plain `markdown` (not `mdx`), `unwrap-md` runs after Prettier to unwrap hard-wrapped prose (see [`plugins/markdown.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_markdown.lua)). Editor soft-wrap uses `FileType` patterns `markdown*` / `mdx*` so compound types (e.g. `markdown.github`) are included, and options are applied per window via `win_findbuf` (see [`core/autocmds.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_autocmds.lua) and [`util/markdown_view.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_markdown_view.lua)). Sessions omit `localoptions` in `sessionoptions` so window/buffer options stay driven by config and filetypes, not replayed session state (see [`core/options.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua)). Default Neovim `viewoptions` does **not** include `options`, so `mkview` on `BufLeave` does not persist `wrap` (only folds/cursor).

## Where The Config Lives

- Source (in this repo): [`home/dot_config/exact_nvim/`](../../../home/dot_config/exact_nvim/)
- Install target (on disk): `~/.config/nvim/`

This setup uses `chezmoi` naming conventions where some directories are prefixed with `exact_` in the source but are installed without that prefix.

Examples (source -> installed):

- [`home/dot_config/exact_nvim/exact_lua/`](../../../home/dot_config/exact_nvim/exact_lua/) -> `~/.config/nvim/lua/`
- [`home/dot_config/exact_nvim/exact_after/`](../../../home/dot_config/exact_nvim/exact_after/) -> `~/.config/nvim/after/`

Leader keys:

- `mapleader` is space (`vim.g.mapleader = " "`)
- `maplocalleader` is `\`

See [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua).

Neovim itself is version-managed via mise:

- Runtime config: [`home/dot_config/mise/config.toml.tmpl`](../../../home/dot_config/mise/config.toml.tmpl) (`neovim = "0.12.2"`)

## Quick Start

1. Install the pinned Neovim version: `mise install neovim@0.12.2`
2. Apply dotfiles: `chezmoi apply`
3. Launch Neovim: `nvim`
4. Open plugin dashboard: `:PackDashboard` (or use `:PackSync` for raw report)

## Plugin Manager On 0.12

This config now uses Neovim's built-in `vim.pack`.

Plugin specs are still declared in lazy-style tables, but loading is now trigger-aware in `core/plugins.lua`: `cmd`, `event`, `ft`, and key-triggered plugins are deferred until first use while always-on specs load at startup.

**Note:** `inc-rename.nvim` is loaded on `LspAttach` rather than `cmd = IncRename`. The deferred `cmd` stub in `core/plugins.lua` re-executes commands with `vim.cmd()`, which breaks Neovim's command-preview API that `inc-rename` relies on (you may see `E32: No file name` or preview errors otherwise).

**Pack retention:** Orphan cleanup only removes directories for plugins that are no longer present in the merged Lua specs. Plugins skipped at startup because `cond` is false (for example, when the first buffer is outside a git work tree) still count as managed packs so their install is not deleted and re-fetched on the next session.

Version policy (fast startup): startup does **not** probe remotes. Instead, `PackSync` / `PackStatus` refresh a cached heuristic map under `stdpath("state")` that decides per-plugin whether to follow release tags or branch tip.

**Per-spec `version` field (lazy.nvim-compatible):**

- `version = "*"` → latest semver tag (translates to `vim.version.range("*")`; resolves to the greatest tag, regardless of major)
- `version = "^1.0"` / `"~1.2"` / `">=2.3"` → semver range (resolves to the greatest matching tag)
- `version = "v1.2.3"` → exact tag
- `version = "<commit-sha>"` → exact commit
- `version = false` → default branch tip, skip tag resolution entirely
- `version = nil` (field omitted) → use the cached heuristic below
- `commit` / `tag` / `branch` top-level fields take priority over `version` (same spec format as lazy.nvim)

**Heuristic default** (when `version` is unset): three gates drive the auto-decision between tags and branch tip:

1. **Minimum release history**: repos with fewer than 3 semver tags can't form a reliable average — if more than 30 commits have landed since the last tag, fall back to branch tip.
2. **Commit ratio**: if the number of commits since the latest tag exceeds the average commits per release (x1.5), fall back to branch tip.
3. **Absolute cap**: more than 150 unreleased commits always means branch tip.

The heuristic is a convenience default for plugins whose spec omits `version`. To override per-plugin, set `version` explicitly in the spec — this wins over the heuristic without any global configuration. Run `:PackPolicyRebuild` (optionally with a plugin name) to clear and recompute the cached heuristic after the plugin set changes or after upstream adds/removes tags; tab-completion suggests managed plugin names.

Practical commands:

- `:PackDashboard` -> compact floating plugin dashboard with:
  - per-plugin update status
  - orphan flag (`O` / trash icon) for installed packs that are no longer declared by any spec; press `C` to clean them (selected orphans first, else all orphans, with confirmation)
  - breaking-risk hint (best-effort) from semver delta (`major`/`minor`/`patch`) plus commit-message signals in the cumulative `rev_before..rev_after` range (for example `BREAKING`, `feat`, `fix`, `refactor`, `perf`)
  - icon-based links column (`diff` / `repo`) with direct compare URL for pending updates
  - single update (`<CR>`), multi-select update (`u`), update all pending (`U`)
  - inline selection/filter/sort/search and details popup (`?` for full key help)
  - opens from cache/known state by default (no implicit online check)
- `:PackSync` -> raw online `vim.pack` report (fetch remotes first)
- `:PackStatus` -> raw offline `vim.pack` report (local refs only)
- `:PackDashboardStats` -> print last raw check counters (`update/same/error`) and check timestamps
- `:PackTrace [plugin-name]` -> show current load state, trigger metadata, and load reason
- `:PackLoad <plugin-name>` -> force-load one plugin by name (useful for debugging)
- `:PackLockInfo` -> show `nvim-pack-lock.json` path, plugin count, mtime (the lockfile is maintained by `vim.pack` itself)
- `:PackLockExport <path>` -> copy the lockfile to any path (for syncing across machines via `chezmoi re-add` or similar)
- `:PackLockImport <path>` -> overwrite the lockfile from a path; restart or `:PackSync` to apply pinned revisions
- `:PackPolicyRebuild [plugin-name]` -> clear and recompute the cached tag/branch heuristic (omit the name for a full rebuild)
- `<localleader>ss` or `:AutoSession save` -> save the current session

Dashboard/trace popup buffers are treated as transient and excluded from session persistence to avoid polluting `auto-session` restores. Session search integrations are loaded on demand to keep startup leaner. Use `r` (or `:PackDashboard!`) for explicit online refresh checks. Dashboard check/apply timestamps and last plugin status/version snapshot are persisted under `stdpath("state")` so they survive Neovim restart. The dashboard header also shows last raw check counters from the most recent explicit check, plus `checked` and `applied` stamps. Filter/sort, search text, and selected plugin rows are also restored on the next dashboard open. Use `o` to open a plugin diff link (with repository fallback), and `O` for repository-only open.

### Dashboard Tuning (Optional)

The dashboard defaults to an icon-first compact view and can be tuned with globals:

- `vim.g.pack_dashboard_width_ratio` (default `0.68`)
- `vim.g.pack_dashboard_height_ratio` (default `0.68`)
- `vim.g.pack_dashboard_min_width` (default `84`)
- `vim.g.pack_dashboard_min_height` (default `18`)
- `vim.g.pack_dashboard_margin` (default `6`)
- `vim.g.pack_dashboard_fast_scroll` (default `true`)
- `vim.g.pack_dashboard_ascii` (default `false`; when `true`, use ASCII labels/icons)
- `vim.g.pack_dashboard_autocheck_on_open` (default `false`; when `true`, first dashboard open may bootstrap cache with a check)
- `vim.g.pack_dashboard_skip_risk_confirm` (default `false`; when `true`, `u`/`U`/`<CR>` skip the risk confirmation for plugins flagged with a major-bump or breaking-signal)
- `vim.g.pack_dashboard_skip_clean_confirm` (default `false`; when `true`, `C` cleans orphan plugins without asking for confirmation)

Repeated `:PackDashboard` calls reuse the existing floating window instead of stacking multiple instances; add `!` (i.e. `:PackDashboard!`) to force-close and re-scan. Stale cache/UI entries for plugins that were removed from the config are purged automatically on every dashboard open.

Orphan plugins (packs on disk that are no longer declared by any spec) are surfaced as `orphan` rows in the dashboard rather than silently deleted at startup. This mirrors the `lazy.nvim` UX: you review what will be removed, then press `C` to clean. The only auto-mutation that still happens at startup is re-cloning a plugin whose `src` changed (same name, new remote) — that's a legitimate move, not an orphan.

Initial version-policy generation and 3-day TTL refresh are deferred to `VimEnter + 200ms` and processed one plugin per scheduled tick, so neither the first launch after adding plugins nor a cold cache blocks the editor. The sync path used by `:PackSync` / `:PackStatus` runs incrementally: only new or missing plugin entries are recomputed when the existing cache is otherwise valid.

Current links column behavior is compact availability:

- `diff` marker when a compare URL exists
- otherwise `repo` marker when a repository URL exists
- `-` when no URL is available

## Tree-sitter: Bundled Parsers And Startup Hangs

Neovim can load tree-sitter parsers from multiple places (runtimepath). In practice, a broken parser under the user "site" directory can hang Neovim at startup, especially if your last session opens a filetype that immediately triggers that parser.

This config prefers Neovim's bundled parser for Markdown to reduce the chance of a bad user-installed parser taking down the editor:

- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_treesitter.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_treesitter.lua)
- Helper: [`home/dot_config/exact_nvim/exact_lua/exact_util/readonly_treesitter.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_util/readonly_treesitter.lua)

Symptoms you might see:

- `nvim` appears to "freeze" (often when opening `*.md`)
- `nvim --clean` works but regular `nvim` does not

Local fix (if you hit this):

```bash
ls -la ~/.local/share/nvim/site/parser
rm -f ~/.local/share/nvim/site/parser/markdown.so
```

Note: the config also treats bundled/runtime parsers as "available" so `nvim-treesitter` doesn't repeatedly try to auto-install languages that Neovim already ships.

## Filetype: `*.tmpl` Belongs To Chezmoi, Not Go

`alker0/chezmoi.vim` detects files under `$CHEZMOI_SOURCE_DIR` and sets composite filetypes like `gitconfig.chezmoitmpl`, `toml.chezmoitmpl`, `sh.chezmoitmpl`, etc. This is what enables the inner-language syntax plus Go-template awareness and is what tree-sitter queries expect.

`ray-x/go.nvim` ships an `ftdetect/filetype.vim` that blanket-claims every `.tmpl` file as Go text-template:

```vim
au BufRead,BufNewFile *.tmpl set filetype=gotexttmpl
```

Our plugin manager sources every plugin's `ftdetect/` eagerly at startup (even for lazy-loaded plugins like go.nvim), so that autocmd is already registered the first time a `.tmpl` buffer is read. Depending on registration order, the `gotexttmpl` autocmd can win on either the initial `BufRead` or subsequent `:e`/`:edit!`. The resulting `gotexttmpl` filetype pulls in `syntax/go.vim`, which defines `goCharacter` as a `'...'` region — so a stray apostrophe in a comment (`git's`) paints everything up to the next `'` (often many lines away) as `Character`.

The defense is intentionally scoped: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_chezmoi.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_chezmoi.lua) installs an eager `FileType` autocmd at startup. Whenever a buffer under the chezmoi source tree is set to a known hijacking filetype (`gotexttmpl`, `gohtmltmpl`), it restores the composite filetype that `chezmoi.vim` already detected (`<ft>.chezmoitmpl`, stored as `b:chezmoi_original_filetype`) or falls back to plain `chezmoitmpl` when there is no inner filetype.

`readonly_dot_Brewfile.tmpl` is intentionally reclaimed to plain `conf`, not `conf.chezmoitmpl`, because the Brewfile source is managed as configuration text in this setup.

It does **not** delete the global `*.tmpl` detector. Non-chezmoi `.tmpl` files can still become `gotexttmpl`, and `.gotext` / `.gohtml` handlers from go.nvim remain.

If you are IDE-first, start by learning:

- moving between files quickly
- searching within a repo
- running tests from inside the editor

## How To Discover Keymaps

This config installs `which-key`:

- Plugin: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_which-key.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_which-key.lua)

Most mappings are defined with descriptions in:

- [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua)

If you forget a shortcut, use `which-key` and your leader mappings as the primary discovery mechanism.

## Customization Entry Points

Start here if you want to change behavior without spelunking the entire tree:

- Core options: [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_options.lua)
- Core keymaps: [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua)
- Core autocmds: [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_autocmds.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_autocmds.lua) (Markdown and `mdx` use `wrap` + `linebreak` + `breakindent` for readable prose)
- Plugin configs: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/)

The corresponding installed paths are:

- `~/.config/nvim/lua/core/options.lua`
- `~/.config/nvim/lua/core/keymaps.lua`
- `~/.config/nvim/lua/core/autocmds.lua`
- `~/.config/nvim/lua/plugins/`

How it's organized:

- `core/` is foundational editor behavior (options, keymaps, autocmds)
- `plugins/` is plugin configuration grouped by topic/language
- `plugins_local_src/` contains local plugins written specifically for this setup

Local plugins (written in this repo) live under:

- Source: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/)
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/)

These are the most workflow-specific parts of the config and usually the best place to look when you want to understand _why_ something exists.

The load list is explicitly declared in:

- [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_init.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_init.lua)

## LSP Code Actions (`<leader>ca`)

Code actions are shown with **fzf-lua**, not Neovim’s default `vim.ui.select` prompt. The `fzf-lua` plugin is loaded on demand (key triggers); its config registers `vim.ui.select` globally only after that first load. The `<leader>ca` / `<leader>cA` mappings therefore call `fzf-lua`’s `lsp_code_actions` helper (with `packadd` when needed) so the fzf picker is used even if you have not used another fzf mapping yet in that session.

## Lua LS Workspace Scope

`lua_ls` root detection is intentionally narrowed for chezmoi paths: when no Lua project markers (`.luarc*`, `stylua.toml`, `selene.toml`) are present, files under `$CHEZMOI_SOURCE_DIR` use the file directory as root instead of the repo `.git` root. This avoids full-repo scans and the "More than 100000 files have been scanned" startup warning in large dotfiles trees.

## LSP Progress In Lualine

Lualine renders native Neovim `LspProgress` events through a local plugin: loader [`plugins_local/lsp-progress.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_lsp-progress.lua), implementation [`plugins_local_src/lsp-progress.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/readonly_lsp-progress.lua), and component wiring in [`plugins/lualine.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_lualine.lua). The statusline shows the client name, an animated spinner, the latest title/message, optional server-provided percentage, and a derived completed-token counter such as `(0/1)` or `(1/1) - done`. This replaces `lsp-progress.nvim` without emitting terminal/tmux OSC progress bars.

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

GitHub (Octo):

- `leader-goa` open Octo actions
- `leader-goil` / `leader-gois` list/search issues
- `leader-gopl` / `leader-gops` list/search pull requests
- `leader-godl` list discussions
- `leader-gonl` list notifications
- `leader-gos` run GitHub search in Octo

## Search And Navigation Workflows

Repo search is centered around `fzf-lua`:

- Config: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_fzf.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_fzf.lua)

Useful mappings (all are defined in that file):

- `leader-sg` live grep in cwd
- `leader-se` grep in changed lines (git status)
- `leader-sE` grep in changed lines (branch)
- `leader-sf` grep in changed files (git status)
- `leader-sF` grep in changed files (branch)

File explorers:

- Neo-tree: [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_neo-tree.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_neo-tree.lua)
- Yazi: same file (`mikavilpas/yazi.nvim`)
- Oil: same file (`stevearc/oil.nvim`)

Neo-tree has a couple of "workflow" mappings inside the tree:

- `leader-nf` find in selected directory
- `leader-ng` grep in selected directory
- `leader-yp` copy relative path

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

- `leader-aisl` summarize via Ollama (local)
- `leader-aisc` summarize via Cloudflare Workers AI
- `leader-aiso` summarize via OpenRouter

Output format notes:

- Header: `type(scope?): summary`
- Bullet points: one bullet per changed functionality (or per distinct logical change)

Environment variables:

| Provider   | Required                                                            | Optional                                                     |
| ---------- | ------------------------------------------------------------------- | ------------------------------------------------------------ |
| Cloudflare | `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY` | `CLOUDFLARE_WORKERS_AI_MODEL`, `CLOUDFLARE_REASONING_EFFORT` |
| OpenRouter | `OPENROUTER_API_KEY`                                                | `OPENROUTER_MODEL`, `OPENROUTER_REASONING_EFFORT`            |
| Ollama     | —                                                                   | `OLLAMA_MODEL`, `OLLAMA_THINK`, `OLLAMA_TEMPERATURE`         |
| Gemini     | `GEMINI_API_KEY`                                                    | `GEMINI_MODEL`, `GEMINI_MAX_OUTPUT_TOKENS`                   |

## Git Workflows

Hunks, blame, and history search are configured here:

- [`home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_git.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins/readonly_git.lua)

Highlights:

- gitsigns hunk navigation (`[h` / `]h`) and stage/reset hunk mappings under `leader-gh*`
- Diffview mappings under `leader-df*`
- History search (`AdvancedGitSearch`) under `leader-ga*`

## Ownership / CODEOWNERS Workflows (Local Plugins)

Show owner of the current file:

- Keymap: `leader-0`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_show-file-owner.lua)

Search only paths owned by a team/owner:

- Keymaps: `leader-rg`, `leader-rG`, `leader-fd`, `leader-fD`
- Commands: `:OwnerCodeGrep`, `:OwnerCodeFd`, `:ListOwners`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_owner-code-search.lua)

## Refactors: Move TS Exports (Local Plugin)

- Visual mode mapping: `leader-]`
- Loader: [`home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_plugins_local/readonly_ts-move-exports.lua)

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

## Small Quality-Of-Life Commands

Defined in [`home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua`](../../../home/dot_config/exact_nvim/exact_lua/exact_core/readonly_keymaps.lua):

- `:LargeFiles` populate quickfix with very large tracked files
- `:WW` / `:WWW` write without triggering autocmds
- `leader-yp` / `leader-yP` copy path to clipboard (relative / absolute)

## What Problems This Setup Focuses On

- Fast navigation and editing with a consistent keyboard-first model
- Tight test loops (run tests, rerun, jump to failures) without leaving editor
- Repeatable refactors that update imports/exports predictably
- Working in large repos (ownership, ripgrep/fzf tooling, git ergonomics)

## IDE Translation (Mental Model)

- VSCode/JetBrains tabs map more closely to Neovim buffers.
- IDE "Problems" panel maps well to Neovim's quickfix list.
- Multi-cursor exists, but composition (motions + operators + textobjects) is the main scaling strategy.

If you are used to clicking around panels in an IDE, your first bridge skill is to rely on:

- fzf pickers for file/search navigation
- quickfix for diagnostics and search results
- a file explorer for local context (Neo-tree/Yazi/Oil)

## Verification And Troubleshooting

High-signal checks:

```bash
nvim --version
mise ls --current | rg neovim
nvim "+PackSync" +qa
nvim "+checkhealth" +qa
```

Inside Neovim, verify key workflows:

- run `:map <leader>tt` and confirm Jest mapping exists.
- open quickfix and test `:QFDedupe`.
- open a git repo file and test gitsigns navigation (`[h` / `]h`).

If keymaps/plugins seem missing:

- confirm `chezmoi apply` succeeded for [`home/dot_config/exact_nvim/`](../../../home/dot_config/exact_nvim/).
- confirm plugin sync completed (`:PackSync` / `:PackStatus` output).
- confirm you are running the expected Neovim binary/version from mise.

## Related

- Repo overview and install: [`README.md`](../../../README.md)
- Neovim local README (short pointer): [`home/dot_config/exact_nvim/README.md`](../../../home/dot_config/exact_nvim/README.md)
- Terminals: [`docs/categories/terminals/index.md`](../workflow/terminals.md)
- Tmux: [`docs/categories/tmux/index.md`](../workflow/tmux/index.md)
