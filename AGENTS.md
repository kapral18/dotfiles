# Dotfiles Project - Agent Instructions

## Package/App/Formula/Cask Installation Priority

When user requests to "add X" (app, package, cask, formula, or CLI tool), follow this priority order:

1. **Brewfile** (`home/readonly_dot_Brewfile.tmpl`) — macOS apps/formulas/casks via Homebrew
2. **Cargo** (`home/readonly_dot_default-cargo-crates`) — Rust packages
3. **Go** (`home/readonly_dot_default-golang-pkgs`) — Go packages
4. **Gems** (`home/readonly_dot_default-gems`) — Ruby packages
5. **npm** (`home/readonly_dot_default-npm-pkgs`) — Node.js/JavaScript packages
6. **uv** (`home/readonly_dot_default-uv-tools.tmpl`) — Python tools/packages
7. **Manual packages** (`home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh`) — .dmg or custom installers
8. **eget** (`home/readonly_dot_default-eget-packages.tmpl`) — GitHub-released CLI tools

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
   - **eget**: Verify GitHub releases structure — binary CLI tools
4. **Stop at first match** — add to that location only
5. **Never invent** package names, URLs, or sources — ask user if verification fails
6. **Use existing patterns** — follow code style and format for each file type

---

## Homebrew Package Management

When adding formulas or casks to Brewfile:

- **Brewfile location**: `home/readonly_dot_Brewfile.tmpl` (use `glob "**/dot_Brewfile*"` if needed)
- **Verify on GitHub first**: Check the official repository's INSTALL.md, README, or releases page to confirm Homebrew is recommended and identify the correct formula/tap name
- **Search GitHub**: Look for official Homebrew taps (e.g., `owner/homebrew-tap`) in the project
- **Verify locally**: Once you identify the formula/tap, test with `brew info <formula>` or `brew info <owner/tap>/<formula>` (works for both formulas and casks)
- **Validate registries**: Use `formulae.brew.sh` search as secondary confirmation
- **Never invent** package names, URLs, or tap information — always verify against official sources first
- **Correct sources**: homebrew-core (default, no tap needed), official project taps, or trusted community taps
- **Report failures**: If verification fails, report findings to user instead of guessing

## Manual App Installation (Non-Homebrew)

When a macOS app is not available via Homebrew but provides a .dmg release:

1. **Verify repository first**: Always search for official GitHub repo before adding
2. **Add to script**: Use `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh`
3. **Use existing pattern**:
   ```bash
   install_dmg_app "App Name" "owner/repo" "AppName.app"
   ```
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

1. **Prefer `eget`**: Use template file `home/readonly_dot_default-eget-packages.tmpl`
2. **Add to template**: Include URL, description, and binary name following existing format
3. **Template variables**:
   - `{{- if ne .isWork true }}` sections for work-specific tools
   - Standard format: `description` + `URL` + `binary-name`
4. **Installation handled by**: chezmoi script `run_onchange_after_05-install-eget-packages.sh.tmpl`

**Example entry**:

```yaml
# Description: DNS propagation checker
# URL: https://github.com/unfrl/dug
dug unfrl/dug
```

**Process flow**:

- ChezMoi processes the template during apply
- Script downloads binary and makes executable
- No need for custom installation functions

**For DMG apps**: Continue using `install_dmg_app` function in manual packages script
**For CLI tools**: Use eget template approach
