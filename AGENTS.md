# Dotfiles Project - Agent Instructions

## Architecture Map Preload (Mandatory, First Action)

At the start of **every** session in this repo, before planning or editing, preload the architecture map in `.mermaids/`.
It is the navigation cloud for the whole solution — the concepts, invariants, data flows, and state machines of every subsystem.
It has two layers: a **semantic cloud** (how it works together) and a **catalog** (where every file lives). Read the semantic layer first.

1. Read [`.mermaids/README.md`](.mermaids/README.md) for the read order and the concept → catalog map.
2. Read [`.mermaids/S0-concepts.mmd`](.mermaids/S0-concepts.mmd) — the 13 core concepts (C1–C13) and their invariants.
   This is the model the whole repo is built on.
3. Read [`.mermaids/00-overview.mmd`](.mermaids/00-overview.mmd) (master map: semantic layer + catalog index).
4. Before editing any file, consult [`.mermaids/SR-index.mmd`](.mermaids/SR-index.mmd) (reverse index).
   Use it to find the concept the file serves, what breaks if changed, and its co-edit set.
5. Load the deeper flow/catalog diagram(s) for whatever the task touches: `S1-flow-apply-reconcile.mmd`, `S3-flow-pickers-handoff.mmd`, or the catalog file named by `SR-index.mmd`.

These diagrams are documentation.
When a change under `home/`, `scripts/`, or `tools/` alters a flow, command, or state shown in a `.mmd` file, update that file in the same change (see Documentation Hygiene below).

## Chezmoi Source-of-Truth (Mandatory)

This is a **chezmoi-managed dotfiles repo**. Chezmoi deploys files from `home/` in this repo to `$HOME`.
The deployed copies are outputs — editing them directly creates drift that `chezmoi apply` will silently overwrite.

**Any time you encounter, read, or are about to edit a dotfile, you MUST check whether chezmoi manages it before making changes.**
This applies whether the path is absolute (`/Users/.../bin/utils/...`), tilde-based (`~/bin/...`), or provided by the user.

1. **Resolve symlinks first.** `chezmoi source-path` does not follow symlinks.
   Run `realpath <path>` (or `readlink -f`) to get the canonical path. Use that resolved path for all subsequent steps.
2. Run `chezmoi source-path <resolved-path>` to check.
3. If it returns a source path: edit **only** that source file (under `home/` in this repo).
   Then deploy with `chezmoi apply --no-tty <target>` and verify.
4. If the command fails (not managed) **and** the file is user-writable: edit the file directly.
5. If the command fails **but** the file is read-only (`r--r--r--`): **stop**.
   Read-only files under `$HOME` are likely deployed by chezmoi with a `readonly_` prefix.
   Investigate before editing — search the chezmoi source tree (`home/`) for the filename. Never `chmod` a read-only deployed file.

**This applies to every file under `$HOME`**.
Examples include shell configs, scripts in `~/bin/`, app configs in `~/.config/`, SOP files, skill files, tmux scripts, and anything else chezmoi might manage.

**Common mappings (not exhaustive):**

| Deployed path       | Chezmoi source                                |
| ------------------- | --------------------------------------------- |
| `~/bin/`            | `home/exact_bin/`                             |
| `~/lib/`            | `home/exact_lib/`                             |
| `~/.config/<app>/`  | `home/dot_config/<app>/`                      |
| `~/.agents/skills/` | `home/exact_dot_agents/exact_skills/`         |
| `~/.claude/skills`  | symlink → `~/.agents/skills` (resolve first!) |

**Chezmoi naming conventions:** `exact_` = exact directory, `readonly_` = read-only, `executable_` = executable.
`dot_` = dotfile (leading `.`), `.tmpl` = template.

---

## Project Validation

- After each change/task in this repo, run `make check` followed by `make fmt`.
- `make check` is affected-only (`bin/check` vs dirty paths).
- Agents must not run `make check-full`, `bin/check --full`, or `make test`; those are human-only.
  Pre-commit runs `bin/check --staged` and must not run the full suite.
- When adding or renaming production code or tests, keep them on the affected map in the same change.
  Name tests so `scripts/check.py` convention hits, or add a `TEST_RULES` row.
  Convention: `scripts/foo.py` / `foo.sh` → `test_foo.py` or `tests/test_foo.py`; `home/exact_lib/exact_,name/` → `tests/test_name.py`.
  Do not leave a new shard reachable only by `make check-full`.
- If either command fails, fix the issue when it is in scope; otherwise report the failure and the relevant output.

---

## AI Setup Contribution Boundary

When changing AI functionality in this chezmoi repo, keep generic mechanics and domain policy separate.

- **Generic surfaces:** portable behavior such as global SOP mechanics, shared skills, generic subagent/runtime profiles, hooks, model/MCP/package generators, and registries.
  Cross-repo AI workflow docs are also generic surfaces.
- **Domain surfaces:** repo/org/product policy such as `k-elastic-domain`, `k-kibana-*`, Elastic/Kibana labels, ownership, Buildkite routing, and bot allowlists.
  PR templates, live-UI targets, endpoints, and data setup are also domain surfaces.
- **Future domains:** any future repo/org/product overlay with comparable policy.

Rules:

1. Generic surfaces may verify the target, load the matching overlay, and pass through overlay results or concrete packets;
   they must not inline Elastic/Kibana defaults, examples, allowlists, labels, hosts, target packets, templates, or fallback behavior.
2. Domain overlays add policy to a primary generic workflow.
   They must not duplicate or replace generic routing, review methodology, publication gates, side-effect gates, memory, or verification discipline.
3. When an interaction changes, update both sides.
   The generic side documents the dispatch/packet boundary, and the domain side owns the concrete policy/data.
4. Treat existing domain-specific content in generic surfaces as non-precedent.
   If a task touches it, move it behind a verified overlay or domain skill instead of expanding it.
5. If no verified domain overlay applies, generic workflows should block or report `Unknown` rather than borrow Elastic/Kibana behavior.
6. Keep documentation aligned: cross-repo mechanics belong in generic AI docs;
   Elastic/Kibana specifics belong in `docs/topics/ai-assistants/skills/elastic-and-kibana.md` or the relevant domain page.

---

## Package/App/Formula/Cask Installation Priority

When user requests to "add X" (app, package, cask, formula, or CLI tool), follow this priority order:

1. **Brewfile** (per-category partials under `home/.chezmoitemplates/brews/`, assembled into `home/readonly_dot_Brewfile.tmpl`) —
   macOS apps/formulas/casks via Homebrew
2. **Cargo** (`home/readonly_dot_default-cargo-crates`) — Rust packages
3. **Go** (`home/readonly_dot_default-golang-pkgs.tmpl`) — Go packages
4. **Gems** (`home/readonly_dot_default-gems`) — Ruby packages
5. **yarn** (`home/readonly_dot_default-yarn-pkgs`) — Node.js/JavaScript packages
6. **uv** (`home/readonly_dot_default-uv-tools.tmpl`) — Python tools/packages
7. **Custom packages** (`home/readonly_dot_default-custom-packages.tmpl`) — DMGs + GitHub release CLI tools + source builds.
   Installed by `home/.chezmoiscripts/run_onchange_after_05-install-custom-packages.sh.tmpl`.

**Interpretation of the priority:**

- A `# @install-priority-exception: prefer=<manager>; skip=<manager>; reason=<reason>` comment immediately preceding a package entry overrides the default priority for that entry.
  Keep the package in the `prefer` manager and bypass each `skip` manager.
  Re-evaluate the directive only when the user explicitly requests it.
- When no exception directive applies, prefer Homebrew first when a formula/cask is verified to install the requested upstream project.
  This applies even if the Homebrew package name differs from the repo slug.
- When no exception directive applies, lower-priority package lists (`cargo`, `go`, `gems`, `yarn`, `uv`, manual packages) are fallbacks only.
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
   - **yarn**: `yarn info <package>` — Node.js/JavaScript packages
   - **uv**: verify the package on PyPI or the official repository; for tool installability, use `uv tool install <package>`.
     Do not use `uv pip search`; current `uv` does not support that command.
   - **Manual (.dmg / release asset)**: verified GitHub releases
5. **Stop at the first suitable match** and add it to that location only.
6. **Use verified package names, URLs, and sources.** Ask the user when verification cannot resolve them.
7. **Use existing patterns** for the target file.

## Documentation Hygiene

- Any change to dotfiles that affects behavior, commands, or workflows MUST be reflected in `docs/`.
  Dotfiles include anything under `home/`, including templates, scripts, and app/package install logic.
- If a dotfiles change does not require a docs change, state why in the PR/commit context (briefly) so the docs/code divergence is explicit.

## AI-Facing Text Formatting

Use these rules when editing LLM-guidance text: text whose purpose is to steer model behavior.
Examples include SOPs, skills, prompts, agent profiles, hooks docs, and instruction/reference `.md` or `.txt` files.
Do not apply this rule to arbitrary prose or data solely because it may be passed to an LLM as context.

**Instruction boundaries (mandatory for instruction text):** when adding, generating, or rewording any LLM instruction, load `home/exact_dot_agents/exact_skills/exact_k-instruction-boundaries/readonly_SKILL.md` (deployed: `~/.agents/skills/k-instruction-boundaries/SKILL.md`) and apply it: default to hard standalone prohibitions for forbidden behavior; add affirmative wording only when it sharpens execution.
The skill also owns the fidelity boundaries — factual negations, quoted examples, enumerated gate contracts, and complete standalone prohibitions stay as written.

- Treat line breaks as prompt-ingestion affordances, not as a fixed-width prose formatter.
- Do not hard-wrap mid-sentence just to satisfy a target column. A line around 140 characters is a soft boundary, not a target.
- Keep a sentence intact by default. Move the next sentence to a new line when appending it would cross the soft boundary.
- When a line exceeds roughly 150 characters, review it manually.
  Split or reword it into separate complete sentences only when doing so preserves every condition, qualifier, and example.
- Do not force every long line under 150 characters.
  Leave dense single-sentence rules, exact gate contracts, command examples, URLs, paths, tables, frontmatter, and code blocks long when splitting would weaken precision or continuity.
- If a single sentence is too long, prefer a meaning-preserving rewrite into two complete sentences.
  If no safe rewrite exists, keep the long sentence rather than cutting it at connector words or whitespace.
- Never drop modal strength (`MUST`, `MAY`, `do not`, `only when`), scope qualifiers, examples, paths, flags, commands, or exception clauses to make a line shorter.
- For Markdown, rely on `bin/fmt` / `,unwrap-md` after editing. For plain text files, apply the same policy manually and inspect the diff.

## Script Architecture: Shell vs Dedicated Languages

Shell scripts (`.sh` / `.sh.tmpl`) in this repo must stay **thin orchestrators**.
Non-trivial logic belongs in colocated scripts written in an appropriate language (Python, etc.) under `scripts/`.

**Rules:**

- **Shell is for glue only**: sourcing `chezmoi_lib.sh`, resolving paths, evaluating chezmoi template variables, and calling external programs.
  It may also wire inputs/outputs between those programs.
- **Move logic out of shell when it involves**: data transformation (JSON, YAML, TOML parsing/generation), string manipulation beyond simple variable expansion, or conditional structures more than a few lines deep.
  Also move anything that would benefit from real data structures, error types, or testability.
- **Colocate helper scripts in `scripts/`**: name them after the data or task they handle (e.g., `generate_mcp_configs.py`, `merge_claude_mcp.py`).
  The shell `.tmpl` script calls them, passing file paths or piped data.
- **No external dependencies in helper scripts**: use only the standard library of the chosen language.
  The existing `ai_models.py` and `generate_mcp_configs.py` hand-parse YAML without PyYAML — follow that precedent.
- **Existing precedent**: `scripts/chezmoi_lib.sh` (shared shell helpers), `scripts/generate_mcp_configs.py`, and `scripts/merge_claude_mcp.py`.
  Also see `scripts/generate_agent_bands.py` and `scripts/ai_models.py`.

**When writing or modifying a chezmoi script** (`home/.chezmoiscripts/`):

1. If the script is already pure shell glue calling a `scripts/` helper, keep it that way.
2. If the change would add more than ~10 lines of non-trivial logic to the shell script, extract it into a new or existing `scripts/` helper instead.
3. When creating a new `scripts/` helper, follow the existing style: shebang, docstring/usage, and `sys.exit` on bad args.
   Read from file paths passed as arguments, and write to stdout or a target path.

---

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
  Follow existing files like `readonly_,pdf-diff.fish` (flags + positional) and `readonly_,appid.fish` (dynamic `-a` argument list).
- **Zsh (only when warranted):** `home/dot_zsh/completions/readonly__comma_<name>` (`#compdef ,<name>`).
  Only complex commands (e.g. `,w`, `,wh`) carry a zsh completion; do not add one unless the command needs zsh-specific completion.
- **Keep completions in sync on updates:** when a command's flags or arguments change, update the completion file in the same change.
  A `~/bin/` command added or changed without its completion is incomplete.

When adding a new `~/bin/` command or `home/exact_lib/exact_,<name>/` command library, also update its catalog row under `docs/topics/workflow/custom-commands/`.
Also update the `.mermaids/07c-bin-commands.mmd` node, plus the relevant census count in `scripts/verify_mermaids.py` and the diagram/README anchors.
This follows Documentation Hygiene.

---

## Agent Skill Naming (Mandatory)

Repo-owned skills MUST use the `k-` namespace.
Source directories live under `home/exact_dot_agents/exact_skills/exact_k-<name>/`, and the skill entrypoint frontmatter `name` MUST be `k-<name>`.
References to those skills MUST use the deployed path `~/.agents/skills/k-<name>/SKILL.md`.
Do not add unprefixed repo-owned skill directories, frontmatter names, or skill references.

---

## Homebrew Package Management

When adding formulas or casks:

- **Brewfile location**: per-category partials live under `home/.chezmoitemplates/brews/{shared,personal,work}/NN-<category>.brewfile`.
  `home/.chezmoitemplates/brews/_assemble.brewfile` assembles them into the single deployed `home/readonly_dot_Brewfile.tmpl`.
  Add the `brew`/`cask` line to the matching category file.
  `shared/` = every machine, `personal/` = `.isWork` false, `work/` = `.isWork` true;
  profile membership is the directory, not an inline `{{ if }}`.
  Create the category file under the right profile dir if it does not exist yet and add a matching `includeTemplate` line in `_assemble.brewfile`.
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

---

## Updating Home SOP Files

Home SOPs are installed into `$HOME` by chezmoi. `home/readonly_AGENTS.md` is the generated core SOP.
Native global entrypoints link to it; `~/CLAUDE.md` uses Claude's native `@AGENTS.md` import to avoid a second full body in Cursor's ancestor scan.
`~/.claude/CLAUDE.md` is Claude's global entrypoint. This repository's `CLAUDE.md` imports its project `AGENTS.md`.
The compiled ownership model lives in `docs/topics/ai-assistants/system-prompt/source-of-truth.md`.

| Source                                                     | Target                               |
| ---------------------------------------------------------- | ------------------------------------ |
| `home/readonly_AGENTS.md`                                  | `~/AGENTS.md`                        |
| `home/readonly_CLAUDE.md`                                  | `~/CLAUDE.md`                        |
| `home/dot_claude/symlink_CLAUDE.md`                        | `~/.claude/CLAUDE.md`                |
| `home/dot_gemini/config/symlink_AGENTS.md`                 | `~/.gemini/config/AGENTS.md`         |
| `home/dot_cursor/symlink_AGENTS.md`                        | `~/.cursor/AGENTS.md`                |
| `home/dot_codex/symlink_AGENTS.md`                         | `~/.codex/AGENTS.md`                 |
| `home/dot_config/opencode/symlink_AGENTS.md`               | `~/.config/opencode/AGENTS.md`       |
| `home/dot_omp/private_agent/symlink_AGENTS.md`             | `~/.omp/agent/AGENTS.md`             |
| `home/private_dot_copilot/symlink_copilot-instructions.md` | `~/.copilot/copilot-instructions.md` |
| `home/exact_dot_agents/exact_skills/`                      | `~/.agents/skills/`                  |

Rules:

1. Edit the compiled source set: `home/readonly_AGENTS.md` for core text, plus disposition/consumer files for moved rules.
2. Run `python3 scripts/compile_ai_policy.py generate` and `make verify-agent-policy` after policy edits.
3. Keep referenced skill files under `home/exact_dot_agents/` in sync.
4. Review with `chezmoi diff`, apply with `chezmoi apply`, and verify only the rendered content or runtime behavior relevant to the change.
