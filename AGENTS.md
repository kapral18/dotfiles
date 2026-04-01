# Dotfiles Project - Agent Instructions

## Chezmoi Source-of-Truth (Mandatory)

This is a **chezmoi-managed dotfiles repo**. Chezmoi deploys files from `home/`
in this repo to `$HOME`. The deployed copies are outputs — editing them directly
creates drift that `chezmoi apply` will silently overwrite.

**Any time you encounter, read, or are about to edit a dotfile — whether by
absolute path (`/Users/.../bin/utils/...`), tilde path (`~/bin/...`), or because
the user pointed you at it — you MUST check whether chezmoi manages it before
making changes:**

1. **Resolve symlinks first.** `chezmoi source-path` does not follow symlinks.
   Run `realpath <path>` (or `readlink -f`) to get the canonical path. Use that
   resolved path for all subsequent steps.
2. Run `chezmoi source-path <resolved-path>` to check.
3. If it returns a source path: edit **only** that source file (under `home/` in
   this repo). Then deploy with `chezmoi apply --no-tty <target>` and verify.
4. If the command fails (not managed) **and** the file is user-writable: edit
   the file directly.
5. If the command fails **but** the file is read-only (`r--r--r--`): **stop**.
   Read-only files under `$HOME` are likely deployed by chezmoi with a
   `readonly_` prefix. Investigate before editing — search the chezmoi source
   tree (`home/`) for the filename. Never `chmod` a read-only deployed file.

**This applies to every file under `$HOME`**, including but not limited to:
shell configs, scripts in `~/bin/`, app configs in `~/.config/`, SOP files,
skill files, tmux scripts, and anything else chezmoi might manage.

**Common mappings (not exhaustive):**

| Deployed path       | Chezmoi source                                |
| ------------------- | --------------------------------------------- |
| `~/bin/`            | `home/exact_bin/`                             |
| `~/bin/utils/`      | `home/exact_bin/utils/`                       |
| `~/.config/<app>/`  | `home/dot_config/<app>/`                      |
| `~/AGENTS.md`       | `home/readonly_AGENTS.md`                     |
| `~/CLAUDE.md`       | `home/readonly_CLAUDE.md`                     |
| `~/.agents/skills/` | `home/exact_dot_agents/exact_skills/`         |
| `~/.claude/skills`  | symlink → `~/.agents/skills` (resolve first!) |

**Chezmoi naming conventions:** `exact_` = exact directory, `readonly_` =
read-only, `executable_` = executable, `dot_` = dotfile (leading `.`), `.tmpl` =
template.

---

## Package/App/Formula/Cask Installation Priority

When user requests to "add X" (app, package, cask, formula, or CLI tool), follow
this priority order:

1. **Brewfile** (`home/readonly_dot_Brewfile.tmpl`) — macOS apps/formulas/casks
   via Homebrew
2. **Cargo** (`home/readonly_dot_default-cargo-crates`) — Rust packages
3. **Go** (`home/readonly_dot_default-golang-pkgs`) — Go packages
4. **Gems** (`home/readonly_dot_default-gems`) — Ruby packages
5. **npm** (`home/readonly_dot_default-npm-pkgs`) — Node.js/JavaScript packages
6. **uv** (`home/readonly_dot_default-uv-tools.tmpl`) — Python tools/packages
7. **Manual packages** (`home/readonly_dot_default-manual-packages.tmpl`) —
   DMGs + GitHub release CLI tools (installed by
   `home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`)

**Interpretation of the priority:**

- Prefer Homebrew first, even when the available Homebrew formula/cask is a
  verified name variation or acceptable alternative for the requested tool.
- Lower-priority package lists (`cargo`, `go`, `gems`, `npm`, `uv`, manual
  packages) are fallbacks only when Homebrew does not provide a suitable
  package.
- Do not drop to a lower-priority registry just because the exact upstream/repo
  slug is not the Homebrew formula name.

**Workflow:**

1. **Identify what X is** — app, CLI tool, library, or language-specific package
2. **Check GitHub first** — always search for official repository:
   - Search: `web_search` or `read_web_page` for the GitHub repo
   - Goal: Find where the project lives and what installation methods it
     recommends
   - Read INSTALL.md, README, or release notes to understand available
     installation options
   - Verify package name, repo owner, and latest version/status
3. **VERIFY IN PRIORITY ORDER** — based on GitHub findings, check registries:
   - **Homebrew first**: do not only test the exact upstream slug. Also check
     likely Homebrew name variations with `brew search <term>` and verify
     candidates with `brew info <formula-or-cask>`.
     - Common variations to test: repo name, normalized name, `<name>-cli`,
       collapsed owner/repo names, and official tap names.
   - **Cargo**: `cargo search <package> --limit 5` — for Rust packages
   - **Go**: `go get -u <import-path>` — search pkg.go.dev or verify from GitHub
   - **Gems**: `gem search <package>` — Ruby packages
   - **npm**: `npm search <package>` — Node.js/JavaScript packages
   - **uv**: `uv pip search <package>` — Python tools
   - **Manual (.dmg)**: `read_web_page` to GitHub releases — macOS apps
4. **Stop at the first suitable match in priority order** — add to that location
   only
5. **Never invent** package names, URLs, or sources — ask user if verification
   fails
6. **Use existing patterns** — follow code style and format for each file type

## Documentation Hygiene

- Any change to dotfiles (anything under `home/`, including templates, scripts,
  and app/package install logic) that affects behavior, commands, or workflows
  MUST be reflected in `docs/`.
- If a dotfiles change does not require a docs change, state why in the
  PR/commit context (briefly) so the docs/code divergence is explicit.

## Script Architecture: Shell vs Dedicated Languages

Shell scripts (`.sh` / `.sh.tmpl`) in this repo must stay **thin
orchestrators**. Non-trivial logic belongs in colocated scripts written in an
appropriate language (Python, etc.) under `scripts/`.

**Rules:**

- **Shell is for glue only**: sourcing `chezmoi_lib.sh`, resolving paths,
  evaluating chezmoi template variables, calling external programs, and wiring
  inputs/outputs between them.
- **Move logic out of shell when it involves**: data transformation (JSON, YAML,
  TOML parsing/generation), string manipulation beyond simple variable
  expansion, conditional structures more than a few lines deep, or anything that
  would benefit from real data structures, error types, or testability.
- **Colocate helper scripts in `scripts/`**: name them after the data or task
  they handle (e.g., `generate_mcp_configs.py`, `merge_claude_mcp.py`). The
  shell `.tmpl` script calls them, passing file paths or piped data.
- **No external dependencies in helper scripts**: use only the standard library
  of the chosen language (the existing `litellm_models.py` and
  `generate_mcp_configs.py` hand-parse YAML without PyYAML — follow that
  precedent).
- **Existing precedent**: `scripts/chezmoi_lib.sh` (shared shell helpers),
  `scripts/generate_mcp_configs.py`, `scripts/merge_claude_mcp.py`,
  `scripts/generate_pi_models.py`, `scripts/litellm_models.py`.

**When writing or modifying a chezmoi script** (`home/.chezmoiscripts/`):

1. If the script is already pure shell glue calling a `scripts/` helper, keep it
   that way.
2. If the change would add more than ~10 lines of non-trivial logic to the shell
   script, extract it into a new or existing `scripts/` helper instead.
3. When creating a new `scripts/` helper, follow the existing style: shebang,
   docstring/usage, `sys.exit` on bad args, read from file paths passed as
   arguments, write to stdout or a target path.

---

## Homebrew Package Management

When adding formulas or casks to Brewfile:

- **Brewfile location**: `home/readonly_dot_Brewfile.tmpl` (use
  `glob "**/dot_Brewfile*"` if needed)
- **Verify on GitHub first**: Check the official repository's INSTALL.md,
  README, or releases page to verify Homebrew is recommended and identify the
  correct formula/tap name
- Prefer verification language; avoid adding "ask to confirm" patterns to this
  file.
- **Search GitHub**: Look for official Homebrew taps (e.g.,
  `owner/homebrew-tap`) in the project
- **Verify locally**: Once you identify the formula/tap, test with
  `brew info <formula>` or `brew info <owner/tap>/<formula>` (works for both
  formulas and casks)
- **Check variations before falling back**: use `brew search <term>` and verify
  reasonable candidate names before moving to Cargo/Go/Gems/npm/uv/manual
  packages
- **Validate registries**: Use `formulae.brew.sh` search as secondary
  verification
- **Never invent** package names, URLs, or tap information — always verify
  against official sources first
- **Correct sources**: homebrew-core (default, no tap needed), official project
  taps, or trusted community taps
- **Report failures**: If verification fails, report findings to user instead of
  guessing

## Manual App Installation (Non-Homebrew)

When a macOS app is not available via Homebrew but provides a .dmg release:

1. **Verify repository first**: Always search for official GitHub repo before
   adding
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

When a CLI tool is not available via Homebrew and distributed via GitHub
releases:

1. **Add to list**: Use `home/readonly_dot_default-manual-packages.tmpl`
2. **Prefer release assets**: Use `file|...` (single binary asset) or
   `tar_gz_bin|...` (archive with a binary)
3. **Template variables**: Use `{{- if ne .isWork true }}` blocks when needed

**Example entry**:

```text
file|dug|unfrl/dug|dug-osx-x64|dug
tar_gz_bin|mdtt|szktkfm/mdtt|mdtt_Darwin_arm64.tar.gz|mdtt|mdtt
```

**Installer**:
`home/.chezmoiscripts/run_onchange_after_05-install-manual-packages.sh.tmpl`

---

## Updating Home SOP Files

Home SOPs are installed into `$HOME` by chezmoi and are intentionally split
into:

- Entrypoints: small files defining global rules + triggers (e.g.
  `~/AGENTS.md`).
- Modules: skills (`~/.agents/skills/`) are referenced by the entrypoints.

**Source-of-truth (edit these in this repo, not in `$HOME`):**

- Entrypoints:
  - `home/readonly_AGENTS.md` -> `~/AGENTS.md`
  - `home/readonly_CLAUDE.md` -> `~/CLAUDE.md`
  - `home/dot_gemini/readonly_GEMINI.md` -> `~/.gemini/GEMINI.md`
- Modules:
  - `home/exact_dot_agents/exact_skills/` -> `~/.agents/skills/`

**OpenCode wiring:**

- `home/dot_config/opencode/symlink_AGENTS.md` -> `~/.config/opencode/AGENTS.md`
  (symlink target `../../AGENTS.md`)

**Rules:**

1. Do not edit the rendered `$HOME` files directly; edit the corresponding
   `home/...` source file in this repo.
2. If an entrypoint references a path under `~/.agents/skills/`, keep the
   corresponding file under `home/exact_dot_agents/` in sync.
3. Keep OpenCode/Claude/Gemini entrypoints aligned for shared rules; keep
   tool-specific differences explicit.

**Workflow:**

1. Edit the relevant `home/...` source files.
2. Review rendered changes with `chezmoi diff`.
3. Apply locally with `chezmoi apply`.
4. Verify:
   - `~/AGENTS.md` contains the expected changes
   - `~/.config/opencode/AGENTS.md` still points at `~/AGENTS.md` (symlink)
