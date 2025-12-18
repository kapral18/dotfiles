# Dotfiles Project - Agent Instructions

## Homebrew Package Management

When adding formulas or casks to Brewfile:

- **Brewfile location**: `home/readonly_dot_Brewfile.tmpl` (use `glob "**/dot_Brewfile*"` if needed)
- **Always verify existence** against formulae.brew.sh or GitHub repos before adding (follow § 6.2 web search priority).
- Use search queries: `"homebrew <package-name>"`, `"brew formulae <package-name>"`.
- Once you identify a package name, verify locally with `brew info <formula|cask>` (works for both formulas and casks).
- Never invent package names, URLs, or tap information. When uncertain, ask the user.
- Correct sources: homebrew-core (default, no tap needed), official taps (e.g., `charliebruce/tap`), or community taps.
- If verification fails, report findings to user instead of guessing.

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
