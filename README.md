![image](./banner.png)

# 🚀 kapral18/dotfiles

Personal macOS development environment managed with Chezmoi. Keyboard-centric
workflow with extensive automation and tool integration.

New here? Start with [`docs/index.md`](docs/index.md).

## 📋 Table of Contents

- [Key Features](#-key-features)
- [Installation](#%EF%B8%8F-installation)
- [Chezmoi & ASDF](#%EF%B8%8F-chezmoi--asdf)
- [Shell Environment](#-shell-fish)
- [Git & 1Password](#-git--1password)
- [Terminal Tools](#-terminals--multiplexers)
- [AI & LLM Integration](#-ai--llm-tools)
- [Neovim](#-neovim)
- [macOS Automation](#%EF%B8%8F-macos-automation)
- [Package Management](#-package-management)
- [Workflow](#-workflow)
- [Further Reading](#-further-reading)

## ✨ Key Features

| Feature                | Description                                      |
| ---------------------- | ------------------------------------------------ |
| 🤖 **Agent Memory**    | Beads integration for AI task tracking           |
| 🔐 **Secure Identity** | 1Password SSH agent with work/personal switching |
| 🌳 **Git Worktrees**   | Worktree management with PR integration          |
| 💎 **Neovim**          | Custom LSP, AI commits, refactoring tools        |
| 🐚 **Fish Shell**      | 30+ custom productivity functions                |
| 📦 **Brewfile**        | 250+ formulas and casks                          |
| ⚙️ **ASDF**            | Version manager with automatic switching         |

---

## 🛠️ Installation

### Prerequisites

1. **Install 1Password**: Required for SSH agent and secret management.

### Bootstrap

```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

### What Happens?

1. Chezmoi installs and initializes from this repository
2. Prompts for:
   - Primary email and SSH public key
   - Secondary credentials (if personal machine)
   - Work machine confirmation
   - PGP cache TTL preference
3. Applies all dotfiles, scripts, and configs
4. Installs Homebrew packages
5. Installs/updates language tools (ASDF, cargo, go, gems, npm, uv)
6. Installs GitHub CLI extensions and manual packages (GitHub releases / DMGs)
7. Applies macOS system preferences and other automation hooks

---

## 🏛️ Chezmoi & ASDF

### Chezmoi

Configuration management with templates and scripts.

**Key Concepts:**

- **Conditional Logic (`.isWork`)**: Templates use `{{ .isWork }}` to handle:
  - Different Git identities and SSH keys
  - Work-specific ASDF plugins
  - Separate Homebrew cask installations
  - Different PGP cache timeouts

- **Executable Scripts**: Files with `executable_` prefix go to `~/bin`:

  ```text
  home/exact_bin/executable_,w → ~/bin/,w
  ```

- **Automated Hooks**: Scripts in `.chezmoiscripts/` run automatically:
  - `run_once_before_*` - One-time setup (e.g., Xcode installation)
  - `run_once_after_*` - One-time post-install (e.g., Homebrew setup)
  - `run_onchange_after_*` - Run when template changes (e.g., package updates)

- **External Assets**: `home/.chezmoiexternal.toml` pulls a few third-party
  dependencies so they stay up-to-date without being vendored here (e.g. tmux
  `tpm`, Hammerspoon `EmmyLua.spoon`, `lowfi` data files, `bat` themes).

### ASDF

Version manager for languages and tools.

**How it works:**

1. **Declarative Plugins** (`home/asdf_plugins.tmpl`): Conditionally install plugins

   ```text
   nodejs
   ruby
   {{ if ne .isWork true }}lua{{ end }}
   ```

2. **Version Pinning** (`home/readonly_dot_tool-versions.tmpl`): Pin tool versions

   ```text
   nodejs 20.11.0
   ruby 3.2.2
   ```

3. **Automatic Switching**: `cd` into a project and the right versions
   activate via ASDF shims.

---

## 🐚 Shell: Fish

Fish is the primary shell, with Zsh and Bash also configured.

### Git Worktree Management

Git worktree helpers for easier branch management.

#### `,w add <branch> [base_branch]`

Create worktrees from:

- Existing local branches
- Remote branches (`origin`, `upstream`)
- Fork branches (`,w add user/branch`)
- New branches from `HEAD`
- Nested directories for `feature/new-ui` → `../feature/new-ui/`

#### `,w prs <pr_numbers_or_search>`

PR reviewer workflow:

1. Search by PR number or keywords
2. Select with `fzf` (shows diff, description, CI status)
3. Fetch PR metadata via GitHub API
4. Add contributor's fork temporarily
5. Create worktree for PR branch
6. Launch named tmux session

#### `,w remove`

Interactive cleanup:

- Removes worktree directories
- Deletes local branches
- Cleans up fork remotes
- Removes empty parent directories
- Purges paths from zoxide
- Kills tmux sessions

### Custom Functions

Custom commands are shipped as scripts installed to `~/bin` (source: `home/exact_bin/`). Fish completions live in `home/dot_config/fish/completions/`. A few helpers are defined directly in Fish config (`home/dot_config/fish/config.fish.tmpl`).

- **Name:** `,w`
  - **Description:** Manage git worktrees with a consistent, tmux-friendly
    workflow (add/list/switch/open/remove) so you can keep branches isolated
    without losing context.
  - **Examples:** `,w add feat/my-change main`; `,w prs 12345`
- **Name:** `,add-patch-to-prs`
  - **Description:** Apply a local `fix.patch` onto one or more of your PR
    branches, commit, and push—useful for “same fix across multiple PRs”.
  - **Examples:** `,add-patch-to-prs 12345`; `,add-patch-to-prs "is:open author:@me label:backport"`
- **Name:** `,appid`
  - **Description:** Print the bundle identifier for a macOS app name/path
    (useful for scripting macOS automation).
  - **Examples:** `,appid "Google Chrome"`; `,appid "Safari"`
- **Name:** `,apply-app-icons`
  - **Description:** Apply custom app icons declared in
    `home/app_icons/icon_mapping.yaml` to `/Applications/*.app` using
    `fileicon`.
  - **Examples:** edit `home/app_icons/icon_mapping.yaml` then run
    `,apply-app-icons`; add a PNG under `home/app_icons/assets/…` then run
    `,apply-app-icons`
- **Name:** `,bat-preview`
  - **Description:** Smart preview for `fzf`/terminal workflows: images via
    `chafa`, binaries via `hexyl`, directories via `ls -la`, and text via `bat`.
  - **Examples:** `,bat-preview README.md --style=numbers`; `,bat-preview path/to/image.png`
- **Name:** `,check-backport-progress`
  - **Description:** Inspect PRs via `gh` to find missing backports and/or
    missing required labels across target branches.
  - **Examples:** `,check-backport-progress --merged-label "Critical Fixes" --required-labels "backport-v8.18 backport-v8.19" --branches "8.x 8.18" --upstream origin`; `,check-backport-progress --merged-label "needs-backport" --required-labels "backport-v1 backport-v2" --branches "main release-1.0" --upstream upstream`
- **Name:** `,cp-files-for-llm`
  - **Description:** Copy the text contents of a directory tree to the
    clipboard with file headers (skips non-text), so you can paste a curated
    snapshot into an assistant.
  - **Examples:** `,cp-files-for-llm .`; `,cp-files-for-llm src -E node_modules -E dist`
- **Name:** `,disable-auto-merge`
  - **Description:** Turn off auto-merge for all open PRs targeting a base
    branch (optionally skipping specific PRs).
  - **Examples:** `,disable-auto-merge main`; `,disable-auto-merge 8.18 12345 23456`
- **Name:** `,dumputi`
  - **Description:** Dump the system’s registered Uniform Type Identifiers
    (UTIs), useful when debugging file associations.
  - **Examples:** `,dumputi | rg -n "public\\.json"`; `,dumputi | rg -n "com\\.adobe"`
- **Name:** `,enable-auto-merge`
  - **Description:** Re-enable auto-merge for all open PRs targeting a base
    branch (also leaves a comment).
  - **Examples:** `,enable-auto-merge main`; `,enable-auto-merge 8.18`
- **Name:** `,fuzzy-brew-search`
  - **Description:** Fuzzy search Homebrew descriptions with preview, then
    drive an “add this to Brewfile” workflow.
  - **Examples:** `,fuzzy-brew-search ripgrep`; `,fuzzy-brew-search "postgres"`
- **Name:** `,fzf-git-changed-lines`
  - **Description:** Emit “changed lines” for your working tree as grep-like
    entries so you can search within just the diff.
  - **Examples:** `,fzf-git-changed-lines --mode status | rg -n "TODO"`; `,fzf-git-changed-lines --mode range --range "main..HEAD" | ,fzf-rg-multiline | fzf --read0`
- **Name:** `,fzf-preview-follow`
  - **Description:** Preview helper that centers the view around the match
    line (works well with `,fzf-rg-multiline`).
  - **Examples:** `,fzf-preview-follow --file README.md --line 120`; `rg -n --column --no-heading --color=never PATTERN | ,fzf-rg-multiline | fzf --read0 --delimiter '\t' --with-nth 1 --preview ',fzf-preview-follow --file {2} --line {3}'`
- **Name:** `,fzf-rg-multiline`
  - **Description:** Convert ripgrep output into NUL-delimited multi-line fzf
    entries so wrapped text doesn’t break actions/preview.
  - **Examples:** `rg -n --column --no-heading --color=never PATTERN | ,fzf-rg-multiline | fzf --read0`; `,fzf-git-changed-lines --mode status | rg -n PATTERN | ,fzf-rg-multiline | fzf --read0`
- **Name:** `,generate-git-sandbox`
  - **Description:** Create a throwaway git repo with branches/commits for
    testing rebases/merges/scripts without touching real repos.
  - **Examples:** `,generate-git-sandbox`; `cd git-sandbox-* && git log --oneline --graph --decorate --all`
- **Name:** `,get-age-buckets`
  - **Description:** Compute file “age buckets” from git history (last true
    content change) for path patterns, which helps spot stale areas.
  - **Examples:** `,get-age-buckets --pattern "src/**/*.ts"`; `,get-age-buckets --pattern "docs/**/*.md,*.mdx" --format json`
- **Name:** `,get-risky-tests`
  - **Description:** Run Jest and report tests whose runtime exceeds a
    threshold (helps target slow tests).
  - **Examples:** `,get-risky-tests "src/plugins/data"`; `,get-risky-tests "src/core/server" | jq -r '.fullName'`
- **Name:** `,gh-prw`
  - **Description:** Open the PR for the current branch (or a given PR number)
    in the browser, or print its number/URL for scripting.
  - **Examples:** `,gh-prw`; `,gh-prw 12345`; `,gh-prw --number`; `,gh-prw --url`
- **Name:** `,gh-tfork`
  - **Description:** Fork + clone a repo into `./<repo>/main`, then create/focus
    a tmux session named `<repo>|main` with a 2-window layout (each window split
    vertically).
  - **Examples:** `,gh-tfork elastic/integrations`
- **Name:** `,gh-subissues-create`
  - **Description:** Draft multiple sub-issues in your editor, create them,
    and attach them to a parent issue via GitHub’s sub-issue GraphQL API.
  - **Examples:** `,gh-subissues-create`; re-run `,gh-subissues-create` to reuse defaults from `/tmp/github-sub-issue-creator-session.json`
- **Name:** `,grepo`
  - **Description:** Find files containing a pattern and open the selected
    file in `$EDITOR` at the next match.
  - **Examples:** `,grepo "owner:"`; `,grepo "TODO"`
- **Name:** `,hey-branch`
  - **Description:** Quick “am I in sync with upstream?” status for the
    current branch (ahead/behind + missing remote).
  - **Examples:** `,hey-branch`; run `,hey-branch` after `git fetch`
- **Name:** `,history-sync`
  - **Description:** Merge local Fish history with a 1Password document and
    push the merged result back, so multiple machines stay in sync.
  - **Examples:** `,history-sync`; run `,history-sync` on each machine periodically
- **Name:** `,install-npm-pkgs`
  - **Description:** Install global npm packages listed in
    `home/readonly_dot_default-npm-pkgs` and re-shim via ASDF.
  - **Examples:** update `home/readonly_dot_default-npm-pkgs` then run `,install-npm-pkgs`; run `,install-npm-pkgs` on a new machine
- **Name:** `,jest-test-title-report`
  - **Description:** Compare Jest test titles between two worktrees and emit a
    CSV (useful for refactors/migrations and review diffs).
  - **Examples:** `,jest-test-title-report --before ~/work/repo/main --after ~/work/repo/feat --scope src/plugins/data --out /tmp/data-tests.csv`; `,jest-test-title-report --before ~/work/repo/main --after ~/work/repo/feat --scope src/plugins/data --out /tmp/data-tests.csv --gist`
- **Name:** `,list-prs`
  - **Description:** Print PR numbers + titles (optionally with a search
    query) for quick piping into `fzf`/scripts.
  - **Examples:** `,list-prs`; `,list-prs "is:open label:bug"`
- **Name:** `,pdf-diff`
  - **Description:** Visual diff two PDFs by compositing pages and opening the
    output.
  - **Examples:** `,pdf-diff left.pdf right.pdf`; `,pdf-diff -d 200 -o /tmp/diff.pdf left.pdf right.pdf`
- **Name:** `,pull-rebase`
  - **Description:** Pull and rebase your current branch onto the branch it
    was created from (or its remote equivalent), with a confirmation prompt.
  - **Examples:** `,pull-rebase`; run `,pull-rebase` before pushing
- **Name:** `,remove-comment`
  - **Description:** Delete a comment from the current PR by selecting it via
    `fzf` (uses `gh api`).
  - **Examples:** `,remove-comment`; use `,remove-comment` after posting a mistaken comment
- **Name:** `,search-brew-desc`
  - **Description:** Search installed Homebrew formula descriptions and emit
    JSON (name/desc/homepage).
  - **Examples:** `,search-brew-desc "json" | jq -r '.[].name'`; `,search-brew-desc "kubernetes"`
- **Name:** `,search-gh-topic`
  - **Description:** Search GitHub repos by topic (default: `gh-extension`)
    with preview, then open the selected repo.
  - **Examples:** `,search-gh-topic "mcp"`; `,search-gh-topic "kibana" "kibana"`
- **Name:** `,start-feat-kbn`
  - **Description:** Kibana helper that boots ES (snapshot) and then starts
    Kibana in a tmux pane when bootstrap completes.
  - **Examples:** `,start-feat-kbn feat-cluster`; `,start-feat-kbn -E xpack.security.enabled=false`
- **Name:** `,start-main-kbn`
  - **Description:** Same as `,start-feat-kbn`, but for the “main” cluster
    defaults/ports.
  - **Examples:** `,start-main-kbn main-cluster`; `,start-main-kbn -E xpack.security.enabled=false`
- **Name:** `,tmux-lowfi`
  - **Description:** Control/launch `lowfi` in a dedicated tmux session for
    quick play/pause/skip and tracklist switching.
  - **Examples:** `,tmux-lowfi play`; `,tmux-lowfi next-tracklist`
- **Name:** `,tmux-run-all`
  - **Description:** Run a command across multiple tmux sessions matching a pattern (optionally excluding a pattern).
  - **Examples:** `,tmux-run-all "work-*" "git status"`; `,tmux-run-all --all "dev-*" "*test*" "npm test"`
- **Name:** `,to-gif`
  - **Description:** Convert a video clip to a GIF using an ffmpeg palette
    workflow (tunable duration/scale/fps).
  - **Examples:** `,to-gif -i in.mp4 -o out.gif`; `,to-gif -i in.mp4 -o out.gif -t 10 -s 900 -f 15`
- **Name:** `,trace-string-pr`
  - **Description:** Search git history for when a regex was introduced in a
    path, then open the PR referenced by the selected commit.
  - **Examples:** `,trace-string-pr "mySymbol" src/`; `,trace-string-pr "TODO\\(" .`
- **Name:** `,vid-ipad`
  - **Description:** Re-encode a video with audio normalization/compression/EQ
    so it’s more “iPad friendly”.
  - **Examples:** `,vid-ipad in.mov out.mp4`; `,vid-ipad recording.mp4 ipad.mp4`
- **Name:** `,view-my-issues`
  - **Description:** Show your assigned issues via `fzf` and open the selected
    one in a browser.
  - **Examples:** `,view-my-issues`; use `,view-my-issues` as a quick “what
    should I do next?” launcher
- **Name:** `bdlocal`
  - **Description:** Beads wrapper that pins a per-repo local DB (based on
    your current directory’s git remote/repo name).
  - **Examples:** `bdlocal status --no-activity --json`; `bdlocal ready --json`
- **Name:** `wpass` (non-work)
  - **Description:** Point `PASSWORD_STORE_DIR` to the work password-store.
  - **Examples:** `wpass; pass ls`; `wpass; pass show some/entry`
- **Name:** `ppass` (non-work)
  - **Description:** Reset `PASSWORD_STORE_DIR` back to the default
    password-store.
  - **Examples:** `ppass; pass ls`; `ppass; pass show some/entry`

---

## 🔐 Git & 1Password

### 1Password SSH Identity

Manage separate Git identities (personal/work) automatically.

#### How It Works

1. Global config sets `sshCommand = ssh -o IdentityFile="~/.ssh/primary_public_key.pub"`
2. Points to **public key** (safe on disk)
3. 1Password SSH agent fetches matching **private key** from vault
4. Conditional include `[includeIf "gitdir:~/work/"]` loads work config
5. Work config points to `secondary_public_key.pub` for different private key

Result: Automatic identity switching based on directory, no private keys on disk.

### Git Configuration

**Aliases:**

- `git wtgrab <worktree>` - Transfer uncommitted changes between worktrees
- `git squash <n>` - Interactive squash
- `git u` - Fetch, rebase, and prune
- `git hide` / `unhide` - Ignore local changes to tracked files

**Defaults:**

- `rerere` - Auto-resolve repeated conflicts
- `rebase.autoSquash = true`
- `rebase.updateRefs = true`
- `diff.algorithm = histogram`
- `merge.conflictStyle = zdiff3`
- `feature.manyFiles = true`

### Git Tools

**gh-dash**: Terminal UI for GitHub PRs and issues

- Separate views for work/personal repos
- Custom filters and layouts
- Config: `home/dot_config/exact_gh-dash/config.yml`
- GitHub CLI (`gh`) config: `home/dot_config/exact_private_gh/`

**TUIs:**

- **gitui** - Fast keyboard-driven UI
- **lazygit** - Simple terminal interface
- **tig** - History viewer

---

## 💻 Terminals & Multiplexers

### Tmux

**Prefix**: `C-Space`

Config: `home/dot_config/tmux/tmux.conf`

**Plugins:**

| Plugin                              | Function                       |
| ----------------------------------- | ------------------------------ |
| `tpm`                               | Plugin manager                 |
| `tmux-resurrect` + `tmux-continuum` | Auto-save sessions every 15min |
| `tmux-pain-control`                 | Pane resize/swap               |
| `tmux-sessionist`                   | Session switching              |
| `tmux-fzf-url`                      | Extract URLs from scrollback   |
| `tmux-theme-catppuccin`             | Theme                          |

**Neovim Integration:**

- `Ctrl-Shift-h/j/k/l` - Passthrough to Neovim
- Vi mode for navigation and copy

### Ghostty

Default terminal emulator (GPU-accelerated).

Config (`home/dot_config/exact_ghostty/config`):

- Hidden titlebar, no shadows
- JetBrainsMono Nerd Font 14pt
- Copy-on-select
- Shell integration

### Fish LSP

Language server for Fish scripts:

- Completions
- Syntax checking
- Go-to-definition
- Diagnostics

---

## 🤖 AI & LLM Tools

AI tools for CLI and editor. Credentials in 1Password, configs in repo.

| Tool           | Purpose                 | Config                                                            |
| -------------- | ----------------------- | ----------------------------------------------------------------- |
| **Crush**      | Terminal AI assistant   | Charmbracelet tap                                                 |
| **Ollama**     | Local LLM runtime       | `home/.chezmoiscripts/run_onchange_after_05-add-ollama-models.sh` |
| **Amp**        | AI coding tool with MCP | `home/dot_config/amp/private_settings.json`                       |
| **Codex CLI**  | Terminal coding agent   | `home/dot_codex/private_config.toml`                              |
| **OpenCode**   | Terminal agent runner   | `home/dot_config/opencode/opencode.jsonc`                         |
| **Cursor**     | AI code editor (work)   | `home/dot_cursor/mcp.json` (`.isWork` conditional)                |
| **Gemini CLI** | Terminal AI assistant   | `home/dot_gemini/settings.json`                                   |

**Ollama Models**:

- `gpt-oss`
- `deepseek-r1`

### Assistant Instructions & SOPs

This repo ships "how I want assistants to operate" as files installed to your
home directory:

- `home/readonly_AGENTS.md` → `~/AGENTS.md`
- `home/readonly_CLAUDE.md` → `~/CLAUDE.md`
- `home/dot_gemini/readonly_GEMINI.md` → `~/.gemini/GEMINI.md`

### Playbooks

Playbooks are reusable workflow modules referenced by the SOP entrypoints (for
example: "When X happens, use playbook Y").

**Source of truth** (chezmoi-managed, real files):

- `home/exact_dot_agents/exact_playbooks/` → `~/.agents/playbooks/`

## 💎 Neovim

Config lives in `home/dot_config/exact_nvim/` (installed to `~/.config/nvim/`).

### Local Plugins (written here)

Local plugins are implemented in `home/dot_config/exact_nvim/exact_lua/exact_plugins_local_src/` and loaded via `home/dot_config/exact_nvim/exact_lua/exact_plugins_local/`.

- **Name:** `run-jest-in-split`
  - **Description:** Run the nearest Jest test (or entire file) in a split
    terminal, with debug and snapshot modes; `q` closes the terminal buffer.
  - **Examples:** `<leader>tt` run test under cursor; `<leader>tD` debug whole
    file
- **Name:** `summarize-commit`
  - **Description:** Generate a conventional-commit message from the staged
    diff and insert it into the `gitcommit` buffer.
  - **Examples:** `<leader>aisl` (Ollama); `<leader>aiso` (OpenRouter)
- **Name:** `save-ai-data`
  - **Description:** Build a curated `~/ai_data.txt` by appending/replacing
    the current buffer or a selected path (and removing entries by
    pattern/type).
  - **Examples:** `<leader>ais` append current buffer; `:RemoveAIFileEntries <pattern>`
- **Name:** `ts-move-exports`
  - **Description:** Move selected TypeScript exports to a new file path and
    update imports.
  - **Examples:** Visual-select exports → `<leader>]`; repeat until file is
    clean
- **Name:** `switch-src-test`
  - **Description:** Jump between source and test files (supports common
    `test/spec` suffixes and JS/TS extension variants).
  - **Examples:** `<C-^>` toggle; run from either file direction
- **Name:** `owner-code-search`
  - **Description:** CODEOWNERS-aware search helpers (ripgrep/fd) scoped to
    paths owned by a team or regex.
  - **Examples:** `:OwnerCodeGrep <team> <pattern>`; `<leader>rg` interactive
    prompt
- **Name:** `show-file-owner`
  - **Description:** Show the owner(s) of the current file from
    `.github/CODEOWNERS` (with caching + specificity sorting).
  - **Examples:** `<leader>0`; `:ShowFileOwner`
- **Name:** `open-eslint-path`
  - **Description:** In an ESLint config, open the on-disk file behind the
    `extends`/`plugins`/`rules` entry under the cursor (from `node_modules`).
  - **Examples:** Put cursor on a value → `<leader>sfe`; pick from multiple
    matches when prompted
- **Name:** `send-to-tmux-right-pane`
  - **Description:** Send diagnostics/current line/selection/git hunk/diff to
    the Tmux pane to the right (useful for pasting into a REPL, Slack, etc.).
  - **Examples:** `<leader>ad` send diagnostics; `<leader>av` send selection
- **Name:** `copy-to-qf`
  - **Description:** Copy the current buffer file into each unique directory
    referenced by the current quickfix list (optionally forcing overwrites).
  - **Examples:** `<leader>cb` copy; `:CopyBufferToQfDirs force`
- **Name:** `qf`
  - **Description:** Quickfix ergonomics: dedupe, path-copy, reverse `:cdo`,
    plus interactive include/exclude filtering.
  - **Examples:** `:QFDedupe`; `<leader>rqi` include-filter quickfix items
- **Name:** `toggle-win-width`
  - **Description:** Toggle the current window width between the previous
    value and the longest visible line width in the buffer.
  - **Examples:** `<leader>=` expand-to-content; `<leader>=` restore
- **Name:** `winbar`
  - **Description:** Winbar shows the “remainder” of the current path
    (components not already shown by bufferline), with truncation.
  - **Examples:** Open a deep path; resize the window and it reflows

### Core Commands & Tweaks (written here)

- **Name:** `:LargeFiles [min_lines] [max_lines]`
  - **Description:** Populate quickfix with tracked files exceeding a
    line-count threshold (filters out image files).
  - **Examples:** `:LargeFiles 5000`; `:LargeFiles 2000 10000`
- **Name:** `:UndoHashedPrune [max_age_days] [max_total_mb]`
  - **Description:** Prune the custom hashed-undo store by age/size.
  - **Examples:** `:UndoHashedPrune`; `:UndoHashedPrune 14 256`
- **Name:** `:CpFromDownloads`
  - **Description:** Neo-tree helper that builds a `cp ~/Downloads/ …` command
    targeting the selected directory.
  - **Examples:** In Neo-tree: `:CpFromDownloads`; `<leader>cp` (Neo-tree
    buffer)
- **Name:** `:WW` / `:WWW`
  - **Description:** Write (or write-all) without triggering write autocmds.
  - **Examples:** `:WW`; `:WWW`
- **Name:** `:MakeTags`
  - **Description:** Generate `ctags` respecting `.gitignore`.
  - **Examples:** `:MakeTags`; `<leader>mt`

### Filetype & Tree-sitter Customization (written here)

- Filetype detection for Helm chart YAML/templates, Docker Compose YAML, and
  `.http` files: `home/dot_config/exact_nvim/exact_ftdetect/filetypes.lua`
- Tree-sitter query overrides/injections for several languages (e.g.
  Astro/TSX/MDX/Markdown):
  `home/dot_config/exact_nvim/exact_after/exact_queries/`

---

## 🖥️ macOS Automation

### Hammerspoon

Lua-based automation.

Defaults scripts:

- `home/.osx.core` + `home/.chezmoiscripts/run_onchange_after_05-osx.core.sh.tmpl`
- `home/.osx.extra` + `home/.chezmoiscripts/run_onchange_after_05-osx.extra.sh.tmpl`

#### Grid Mouse (`gridmouse.lua`)

Keyboard mouse control:

- `h/j/k/l` to move cursor
- Grid mode for precise positioning

#### Window Management (`window.lua`)

Hyper key + movement:

- `Hyper + h` - Snap left
- `Hyper + l` - Snap right
- `Hyper + k` - Snap top
- `Hyper + j` - Snap bottom
- `Hyper + m` - Maximize

### Custom App Icons

Script: `,apply-app-icons`

1. YAML mapping (`home/app_icons/icon_mapping.yaml`)
2. Uses `fileicon` to apply icons
3. Assets in `home/app_icons/assets/`

### Alfred

Alfred preferences and workflows live in `home/Alfred.alfredpreferences/`.

### Karabiner

Karabiner-Elements rules live in `home/dot_config/private_karabiner/karabiner.json`.

---

## 📦 Package Management

| System       | File                                             | Purpose                      |
| ------------ | ------------------------------------------------ | ---------------------------- |
| **Homebrew** | `home/readonly_dot_Brewfile.tmpl`                | macOS apps, CLI tools, fonts |
| **Cargo**    | `home/readonly_dot_default-cargo-crates`         | Rust packages                |
| **Go**       | `home/readonly_dot_default-golang-pkgs`          | Go tools                     |
| **Gems**     | `home/readonly_dot_default-gems`                 | Ruby packages                |
| **npm**      | `home/readonly_dot_default-npm-pkgs`             | Node.js globals              |
| **uv**       | `home/readonly_dot_default-uv-tools.tmpl`        | Python tools                 |
| **Manual**   | `home/readonly_dot_default-manual-packages.tmpl` | DMGs + GitHub releases       |

Install scripts run via chezmoi hooks when files change.

Note: this setup is intentionally declarative. For example:

- Homebrew sync runs `brew bundle cleanup --global --force` via
  `home/.chezmoiscripts/run_onchange_after_03-install-brew-packages.fish.tmpl`
  (so formulas/casks not in the Brewfile can be removed).
- ASDF sync removes unwanted plugins/versions based on `home/asdf_plugins.tmpl` and
  `home/readonly_dot_tool-versions.tmpl` via
  `home/.chezmoiscripts/run_onchange_after_05-install-asdf-plugins.sh.tmpl`.

---

## 🔄 Workflow

### Typical Day

1. Tmux sessions auto-restore
2. `,w add feature/new-ui` - new worktree + tmux session
3. `,w prs 12345` - checkout PR
4. Jest runner in Neovim
5. AI-generated commit
6. `,w remove` - cleanup

### Update Packages

```bash
brew update && brew upgrade
chezmoi apply
```

### Sync to New Machine

```bash
sh -c "$(curl -fsLS get.chezmoi.io/lb)" -- init --apply kapral18
```

---

## 📚 Further Reading

- Docs: [`docs/index.md`](docs/index.md)
- Chezmoi configs: `home/`
- Chezmoi data prompts: `home/.chezmoi.toml.tmpl`
- Chezmoi externals: `home/.chezmoiexternal.toml`
- Chezmoi hooks: `home/.chezmoiscripts/`
- Neovim: `home/dot_config/exact_nvim/`
- Fish: `home/dot_config/fish/`
- Scripts: `home/exact_bin/`
- Brewfile: `home/readonly_dot_Brewfile.tmpl`
- Assistant playbooks: `home/exact_dot_agents/exact_playbooks/`
- Codex CLI config: `home/dot_codex/`
- OpenCode config: `home/dot_config/opencode/`
- Alfred: `home/Alfred.alfredpreferences/`
- Karabiner: `home/dot_config/private_karabiner/`
- Hammerspoon: `home/dot_hammerspoon/`

See also: `AGENTS.md` for AI agent instructions
