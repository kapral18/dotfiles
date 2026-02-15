# Dotfiles Project - Agent Instructions

## Package/App/Formula/Cask Installation Priority

When user requests to "add X" (app, package, cask, formula, or CLI tool), follow this priority order:

1. **Brewfile** (`home/readonly_dot_Brewfile.tmpl`) — macOS apps/formulas/casks via Homebrew
2. **Cargo** (`home/readonly_dot_default-cargo-crates`) — Rust packages
3. **Go** (`home/readonly_dot_default-golang-pkgs`) — Go packages
4. **Gems** (`home/readonly_dot_default-gems`) — Ruby packages
5. **npm** (`home/readonly_dot_default-npm-pkgs`) — Node.js/JavaScript packages
6. **uv** (`home/readonly_dot_default-uv-tools.tmpl`) — Python tools/packages
7. **Manual packages** (`home/readonly_dot_default-manual-packages.tmpl`) — DMGs + GitHub release CLI tools (installed by `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`)

**Workflow:**

1. **Identify what X is** — app, CLI tool, library, or language-specific package
2. **Check GitHub first** — always search for official repository:
   - Search: `web_search` or `read_web_page` for the GitHub repo
   - Goal: Find where the project lives and what installation methods it recommends
   - Read INSTALL.md, README, or release notes to understand available installation options
   - Verify package name, repo owner, and latest version/status
3. **VERIFY IN PRIORITY ORDER** — based on GitHub findings, check registries:
   - **Homebrew**: `brew info <package>` — check for formula or cask
   - **Cargo**: `cargo search <package> --limit 5` — for Rust packages
   - **Go**: `go get -u <import-path>` — search pkg.go.dev or verify from GitHub
   - **Gems**: `gem search <package>` — Ruby packages
   - **npm**: `npm search <package>` — Node.js packages
   - **uv**: `uv pip search <package>` — Python tools
   - **Manual (.dmg)**: `read_web_page` to GitHub releases — macOS apps
4. **Stop at first match** — add to that location only
5. **Never invent** package names, URLs, or sources — ask user if verification fails
6. **Use existing patterns** — follow code style and format for each file type

---

## Homebrew Package Management

When adding formulas or casks to Brewfile:

- **Brewfile location**: `home/readonly_dot_Brewfile.tmpl` (use `glob "**/dot_Brewfile*"` if needed)
- **Verify on GitHub first**: Check the official repository's INSTALL.md, README, or releases page to verify Homebrew is recommended and identify the correct formula/tap name
- Prefer verification language; avoid adding "ask to confirm" patterns to this file.
- **Search GitHub**: Look for official Homebrew taps (e.g., `owner/homebrew-tap`) in the project
- **Verify locally**: Once you identify the formula/tap, test with `brew info <formula>` or `brew info <owner/tap>/<formula>` (works for both formulas and casks)
- **Validate registries**: Use `formulae.brew.sh` search as secondary verification
- **Never invent** package names, URLs, or tap information — always verify against official sources first
- **Correct sources**: homebrew-core (default, no tap needed), official project taps, or trusted community taps
- **Report failures**: If verification fails, report findings to user instead of guessing

## Manual App Installation (Non-Homebrew)

When a macOS app is not available via Homebrew but provides a .dmg release:

1. **Verify repository first**: Always search for official GitHub repo before adding
2. **Add to list**: Use `home/readonly_dot_default-manual-packages.tmpl`
3. **Use existing pattern**: `dmg|App Name|owner/repo|AppName.app|.dmg`
4. **Function handles**:
   - Latest release download from GitHub API
   - DMG mounting and app copy to /Applications
   - Already-installed checks
   - Cleanup on failure/success

**Example**:

```bash
# Squirrel Disk
install_dmg_app "Squirrel Disk" "adileo/squirreldisk" "SquirrelDisk.app"
```

**Best practices**:

- Verify repo owner/name via GitHub search
- Use exact .app bundle name from mounted volume
- Test in safe environment before production deployment

## CLI Tool Installation (Non-Homebrew, Non-DMG)

When a CLI tool is not available via Homebrew and distributed via GitHub releases:

1. **Add to list**: Use `home/readonly_dot_default-manual-packages.tmpl`
2. **Prefer release assets**: Use `file|...` (single binary asset) or `tar_gz_bin|...` (archive with a binary)
3. **Template variables**: Use `{{- if ne .isWork true }}` blocks when needed

**Example entry**:

```text
file|dug|unfrl/dug|dug-osx-x64|dug
tar_gz_bin|mdtt|szktkfm/mdtt|mdtt_Darwin_arm64.tar.gz|mdtt|mdtt
```

**Installer**: `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`

---

## Updating Home SOP Files

Home SOPs are installed into `$HOME` by chezmoi and are intentionally split into:

- Entrypoints: small files defining global rules + triggers (e.g. `~/AGENTS.md`).
- Modules: most of the detailed workflow playbooks live under `~/.agents/skills/` and are referenced by the entrypoints.

**Source-of-truth (edit these in this repo, not in `$HOME`):**

- Entrypoints:
  - `home/readonly_AGENTS.md` -> `~/AGENTS.md`
  - `home/readonly_CLAUDE.md` -> `~/CLAUDE.md`
  - `home/dot_gemini/readonly_GEMINI.md` -> `~/.gemini/GEMINI.md`
- Modules:
  - `home/exact_dot_agents/` -> `~/.agents/` (skills live under `~/.agents/skills/`)

**OpenCode wiring:**

- `home/dot_config/opencode/symlink_AGENTS.md` -> `~/.config/opencode/AGENTS.md` (symlink target `../../AGENTS.md`)

**Rules:**

1. Do not edit the rendered `$HOME` files directly; edit the corresponding `home/...` source file in this repo.
2. If an entrypoint references a skill/module path under `~/.agents/skills/`, keep the corresponding skill under `home/exact_dot_agents/skills/` in sync.
3. Keep OpenCode/Claude/Gemini entrypoints aligned for shared rules; keep tool-specific differences explicit.

**Workflow:**

1. Edit the relevant `home/...` source files.
2. Review rendered changes with `chezmoi diff`.
3. Apply locally with `chezmoi apply`.
4. Verify:
   - `~/AGENTS.md` contains the expected changes
   - `~/.config/opencode/AGENTS.md` still points at `~/AGENTS.md` (symlink)
