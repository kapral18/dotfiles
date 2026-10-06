---
title: Dotfiles agent recipes
---

# Dotfiles agent recipes

Task-triggered project instructions moved from `AGENTS.md`. Load this complete page before adding packages, changing shell/helper architecture, or adding/updating deployed commands. These recipes preserve the existing installation priority, source ownership, documentation and completion requirements.

## Package/App/Formula/Cask Installation Priority

When user requests to "add X" (app, package, cask, formula, or CLI tool), follow this priority order:

1. **Brewfile** (per-category partials under `home/.chezmoitemplates/brews/`, assembled into `home/readonly_dot_Brewfile.tmpl`) —
   macOS apps/formulas/casks via Homebrew
2. **Cargo** (`home/readonly_dot_default-cargo-crates`) — Rust packages
3. **Go** (`home/readonly_dot_default-golang-pkgs.tmpl`) — Go packages
4. **Gems** (`home/readonly_dot_default-gems`) — Ruby packages
5. **pnpm** (`home/readonly_dot_default-pnpm-pkgs`) — Node.js/JavaScript packages
6. **uv** (`home/readonly_dot_default-uv-tools.tmpl`) — Python tools/packages
7. **Custom packages** (`home/readonly_dot_default-custom-packages.tmpl`) — DMGs + GitHub release CLI tools + source builds.
   Installed by `home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`.

**Interpretation of the priority:**

- A `# @install-priority-exception: prefer=<manager>; skip=<manager>; reason=<reason>` comment immediately preceding a package entry overrides the default priority for that entry.
  Keep the package in the `prefer` manager and bypass each `skip` manager.
  Re-evaluate the directive only when the user explicitly requests it.
- When no exception directive applies, prefer Homebrew first when a formula/cask is verified to install the requested upstream project.
  This applies even if the Homebrew package name differs from the repo slug.
- When no exception directive applies, lower-priority package lists (`cargo`, `go`, `gems`, `pnpm`, `uv`, manual packages) are fallbacks only.
  Use them only when Homebrew does not provide a suitable package.
- Choose the verified Homebrew package when only its name differs from the upstream/repo slug.

**Workflow:**

1. **Identify X** — app, CLI tool, library, or language-specific package.
2. **Check for an exception first** — search the package lists for the canonical package/project and honor any `@install-priority-exception` directive immediately preceding its entry.
3. **Check GitHub** — find the official repo when one exists; read README, INSTALL, and releases to learn supported installs;
   verify package name, owner, version, and status.
4. **Check registries in priority order**:
   - **Homebrew first**: search likely names with `brew search <term>` and verify candidates with `brew info <formula-or-cask>`.
     Test repo name, normalized name, `<name>-cli`, collapsed owner/repo names, and official tap names.
   - **Cargo**: `cargo search <package> --limit 5` — for Rust packages
   - **Go**: verify the import path on pkg.go.dev or the official repository; for installability, use `go install <import-path>@latest` or a versioned equivalent.
   - **Gems**: `gem search <package>` — Ruby packages
   - **pnpm**: `pnpm view <package>` — Node.js/JavaScript packages
   - **uv**: verify the package on PyPI or the official repository; for tool installability, use `uv tool install <package>`.
     Do not use `uv pip search`; current `uv` does not support that command.
   - **Manual (.dmg / release asset)**: verified GitHub releases
5. **Stop at the first suitable match** and add it to that location only.
6. **Use verified package names, URLs, and sources.** Ask the user when verification cannot resolve them.
7. **Use existing patterns** for the target file.

## Script Architecture: Shell vs Dedicated Languages

Shell scripts (`.sh` / `.sh.tmpl`) in this repo must stay **thin orchestrators**.
Non-trivial logic belongs in colocated scripts written in an appropriate language (Python, etc.) under `scripts/`.

**Rules:**

- **Shell is for glue only**: sourcing `chezmoi_lib.sh`, resolving paths, evaluating chezmoi template variables, and calling external programs.
  It may also wire inputs/outputs between those programs.
- **Move logic out of shell when it involves**: data transformation (JSON, YAML, TOML parsing/generation), string manipulation beyond simple variable expansion, or conditional structures more than a few lines deep.
  Also move anything that would benefit from real data structures, error types, or testability.
- **Colocate helper scripts in `scripts/`**: name them after the data or task they handle (e.g., `scripts/generate_mcp_configs.py`, `scripts/merge_claude_mcp.py`).
  The shell `.tmpl` script calls them, passing file paths or piped data.
- **No external dependencies in helper scripts**: use only the standard library of the chosen language.
  The existing `scripts/yaml_parser.py` and `scripts/generate_mcp_configs.py` hand-parse YAML without PyYAML — follow that precedent.
- **Existing precedent**: `scripts/chezmoi_lib.sh` (shared shell helpers), `scripts/generate_mcp_configs.py`, and `scripts/merge_claude_mcp.py`.

**When writing or modifying a chezmoi script** (`home/.chezmoiscripts/`):

1. If the script is already pure shell glue calling a `scripts/` helper, keep it that way.
2. If the change would add more than ~10 lines of non-trivial logic to the shell script, extract it into a new or existing `scripts/` helper instead.
3. When creating a new `scripts/` helper, follow the existing style: shebang, docstring/usage, and `sys.exit` on bad args.
   Read from file paths passed as arguments, and write to stdout or a target path.

## Bin Commands & Shell Completions (Mandatory)

Repo-owned standalone user commands MUST use the comma namespace.

- Source files live in `home/exact_bin/executable_,<name>` and deploy to `~/bin/,<name>`; the leading comma is part of the command name.
- Do not add unprefixed standalone commands under `~/bin`.

Commands are self-contained across deployed `$HOME` surfaces.
`~/bin/` scripts cannot call repo-only `scripts/` helpers because `scripts/` is not deployed to `$HOME`.
For commands over ~200 lines or with multiple logical subsystems, keep `~/bin/,<name>` as a thin launcher.
Move internals into `home/exact_lib/exact_,<name>/` (deployed to `~/lib/,<name>/`).
`home/exact_lib/` intentionally owns the sibling `~/lib` command-internals tree.
Small single-purpose commands may stay directly in `home/exact_bin/`.

**Whenever you add or update a `~/bin/` command, you MUST add/update its shell completion in the same change:**

- **Fish (primary, required):** `home/dot_config/fish/completions/readonly_,<name>.fish` → `~/.config/fish/completions/,<name>.fish`.
  Declare every flag (`complete -c ,<name> -s o -l output -d "…" -r`) and positional/argument completion.
  Mirror the script's actual interface (`--help` output is the source of truth).
  Follow existing files like `home/dot_config/fish/completions/readonly_,pdf-diff.fish` (flags + positional) and `home/dot_config/fish/completions/readonly_,appid.fish` (dynamic `-a` argument list).
- **Zsh (only when warranted):** `home/dot_zsh/completions/readonly__comma_<name>` (`#compdef ,<name>`).
  Only complex commands (e.g. `,w`, `,wh`) carry a zsh completion; do not add one unless the command needs zsh-specific completion.
- **Keep completions in sync on updates:** when a command's flags or arguments change, update the completion file in the same change.
  A `~/bin/` command added or changed without its completion is incomplete.

When adding a new `~/bin/` command or `home/exact_lib/exact_,<name>/` command library, also update its catalog row under `docs/topics/workflow/custom-commands/`.
This follows Documentation Hygiene.

## Homebrew Package Management

When adding formulas or casks:

- **Brewfile location**: per-category partials live under `home/.chezmoitemplates/brews/{shared,personal,work}/NN-<category>.brewfile`.
  `home/.chezmoitemplates/brews/_assemble.brewfile` assembles them into the single deployed `home/readonly_dot_Brewfile.tmpl`.
  Add the `brew`/`cask` line to the matching category file.
  `shared/` = every machine, `personal/` = `.isWork` false, `work/` = `.isWork` true;
  profile membership is the directory, not an inline `{{ if }}`.
  Create the category file under the right profile dir if it does not exist yet and add a matching `includeTemplate` line in `home/.chezmoitemplates/brews/_assemble.brewfile`.
- **Verify on GitHub first**: read the official repo's README, INSTALL, or releases to confirm Homebrew support and identify the correct formula/tap.
- **Search GitHub**: look for official Homebrew taps such as `owner/homebrew-tap` when a tap is needed.
- Verify locally with `brew info <formula>` or `brew info <owner/tap>/<formula>` before editing the Brewfile.
- Check name variations with `brew search <term>` before falling back to lower-priority registries.
- Use homebrew-core, official project taps, or a community tap only after verifying its repository and formula source.
- If verification fails, report findings instead of guessing.

## Manual App Installation (Non-Homebrew)

When a macOS app is not available via Homebrew but provides a .dmg release:

1. **Verify DMG source**: Confirm the official GitHub repo and `.dmg` release asset.
2. **Add registry entry**: Use `home/readonly_dot_default-custom-packages.tmpl`.
3. **Use DMG format**: `dmg|App Name|owner/repo|release-tag|AppName.app|asset-pattern`.
4. **Installer handles**:
   - Latest release download from GitHub API
   - DMG mounting and app copy to /Applications
   - Already-installed checks
   - Cleanup on failure/success

**Example**:

```text
dmg|Squirrel Disk|adileo/squirreldisk|latest|SquirrelDisk.app|.dmg
```

**Best practices**:

- Use exact .app bundle name from mounted volume
- Run the relevant installer/apply check before relying on the entry.

## CLI Tool Installation (Non-Homebrew, Non-DMG)

When a CLI tool is not available through higher-priority package managers and is distributed via GitHub releases:

1. **Verify CLI source**: Confirm the official GitHub repo and the binary/archive asset for the target OS and architecture.
2. **Add registry entry**: Use `home/readonly_dot_default-custom-packages.tmpl`
3. **Prefer release assets**: Use `file|...` (single binary), `tar_gz_bin|...` (archive with a binary), or `zip_opt|...` (zip that must keep sibling dylibs under `~/.local/opt`)
4. **Template variables**: Use `{{- if ne .isWork true }}` blocks when needed

**Example entry**:

```text
file|dug|unfrl/dug|0.0.94|dug-osx-x64|dug
tar_gz_bin|mdtt|szktkfm/mdtt|v0.3.1|mdtt_Darwin_arm64.tar.gz|mdtt|mdtt
zip_opt|sd-cli|leejet/stable-diffusion.cpp|master-820-de298c2|sd-*-bin-Darwin-macOS-*-arm64.zip|sd-cli|sd-cli
```

**Installer**: `home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`
