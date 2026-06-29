# Architecture Map (`.mermaids/`)

A navigation cloud for this chezmoi dotfiles repo, in **two layers**:

- **Semantic cloud** (`S0`, `S1`–`S3`, `SR`) — how the system _thinks_: the 13 concepts and invariants it is built on, the cross-cutting flows that wire subsystems together, and a reverse index from any file to its concept, blast radius, and co-edit set. **Read this first** — it makes the catalog legible.
- **Catalog** (`00`–`13`) — how the system is _laid out_: exhaustive coverage of every one of the 1187 tracked files, named or grouped by exact chezmoi source path. Use it to drill from a concept to the precise file.

Together they let an agent understand the whole solution in one pass and then map straight down to any particle. They complement the prose in `docs/` and the rules in `AGENTS.md` / `CLAUDE.md`.

Each file is a standalone [Mermaid](https://mermaid.js.org/) diagram (`.mmd`), left unwrapped so `bin/fmt` never rewrites them (the `.mmd` extension matches no formatter). Render in any Mermaid-aware viewer, GitHub, the Mermaid Live Editor, or a markdown preview.

## Semantic layer (read first)

- [`S0-concepts.mmd`](S0-concepts.mmd) — the 13 core concepts (C1–C13), each with its **invariant** (the rule that must hold) and the files that realize it. This is the heart of the cloud; everything else is an instance.
- [`S1-flow-apply-reconcile.mmd`](S1-flow-apply-reconcile.mmd) — flow: source + data + `isWork` → template + hash-gated hooks → `$HOME` build → runtime consumers. The idempotent reconcile (C1–C6).
- [`S2-flow-agent-runtime.mmd`](S2-flow-agent-runtime.mmd) — flow: one governed agent turn (session memory → SOP/skill load → verify loop → evidence ledger → human-visible gate), plus the Ralph diversity/resume sub-loop (C7, C8, C11–13).
- [`S3-flow-pickers-handoff.mmd`](S3-flow-pickers-handoff.mmd) — flow: stale-while-revalidate UX and the file-based handoff bus that lets the gh / ralph / session / worktree pickers cooperate (C9, C10).
- [`SR-index.mmd`](SR-index.mmd) — reverse index: pick the row for the file you are about to touch → concept it serves → what breaks → minimum co-edit set → which catalog diagram holds the exhaustive view.

## Catalog layer (exhaustive per-file drill-down)

1. [`00-overview.mmd`](00-overview.mmd) — master map (semantic + catalog) + file census; start here.
2. [`01-chezmoi-pipeline.mmd`](01-chezmoi-pipeline.mmd) — `chezmoi apply` lifecycle; every `.chezmoiscripts/` hook (31) + data/external/ignore inputs.
3. [`02-package-management.mmd`](02-package-management.mmd) — the "add X" ladder and every `default-*` package list + sync hook (incl. runtimes, local AI, system hooks).
4. [`03-agentic-os.mmd`](03-agentic-os.mmd) — governance + context + execution layers (SOP entrypoints, MCP/model registries, per-tool generation).
5. [`03b-agent-skills-hooks.mmd`](03b-agent-skills-hooks.mmd) — every file under `exact_dot_agents/` (38 skills + 8 hooks + references).
6. [`04-ralph-state-machine.mmd`](04-ralph-state-machine.mmd) — Ralph's resumable planner → executor → reviewer → re-reviewer state machine.
7. [`04b-ralph-control-plane.mmd`](04b-ralph-control-plane.mmd) — Ralph CLI, workflows, run state, ralph-tui (15 Go pkgs), tmux wiring, AI KB.
8. [`05-tmux-pickers.mmd`](05-tmux-pickers.mmd) — every file under `exact_tmux/` (119): conf.d loader, GitHub picker, session picker, handoff, sessions, palettes, resurrect.
9. [`06-worktree-workflow.mmd`](06-worktree-workflow.mmd) — `,w` subcommands, `,gh-tfork`, gh-dash, and 1Password identity switching.
10. [`07-shell-editor-macos.mmd`](07-shell-editor-macos.mmd) — fish/zsh/bash, terminals, and macOS automation (Hammerspoon, Karabiner, Alfred, icons, osx defaults).
11. [`07b-neovim.mmd`](07b-neovim.mmd) — every file under `exact_nvim/` (157): core, 57 plugin specs, 14 local plugins, util, queries, syntax.
12. [`07c-bin-commands.mmd`](07c-bin-commands.mmd) — every thin command in `exact_bin/` (70) grouped by purpose + deployed command/shared internals in `home/exact_lib/` (40 command/shared library files).
13. [`08-security-and-dotfiles.mmd`](08-security-and-dotfiles.mmd) — SSH/GPG identity, 1Password agent, git signing, pass stores, and every shell/tool rc dotfile.
14. [`09-repo-validation.mmd`](09-repo-validation.mmd) — `make check` / `make fmt`, hygiene gates, and every repo-side config/meta file.
15. [`10-docs-and-repo-meta.mmd`](10-docs-and-repo-meta.mmd) — the Docusaurus site (`website/` + `docs/`) and GitHub Pages CI; every page named.
16. [`11-scripts-helpers.mmd`](11-scripts-helpers.mmd) — every file in `scripts/` (43): shared parsers, MCP/model generators, AI KB, tests.
17. [`12-ai-tool-configs.mmd`](12-ai-tool-configs.mmd) — every per-tool AI config (Cursor, Claude, Codex, Gemini, OpenCode, Pi, tuicr).
18. [`13-app-configs.mmd`](13-app-configs.mmd) — remaining app configs (lazygit, gitui, tig, gh, bat, btop, yazi, ghostty, starship, llama.cpp, karabiner, ralph).

## Concept → catalog map (semantic to particle)

| Concept (S0)                 | Invariant in one line                                                           | Catalog  |
| ---------------------------- | ------------------------------------------------------------------------------- | -------- |
| C1 source vs output          | edit `home/**`, never `$HOME` targets                                           | 01       |
| C2 one registry per concern  | declare once, generate per tool                                                 | 02,12    |
| C3 `isWork` duality          | one bool forks identity/keys/models                                             | 01,12,13 |
| C4 idempotent reconcile      | hash-gate + write-if-changed + manifest                                         | 01,02    |
| C5 secrets at runtime        | configs reference, never store, secrets                                         | 08,12    |
| C6 thin shell / typed core   | shell is glue; logic lives in `scripts/` or `home/exact_lib/` command internals | 11, 07c  |
| C7 governed agents           | SOP + skills + fail-closed gates                                                | 03,03b   |
| C8 evidence ledger           | claims anchored or demoted to Unknown                                           | 03b      |
| C9 stale-while-revalidate    | cached first paint, bg refetch, no block                                        | 05       |
| C10 handoff bus              | cooperate via pin/sentinel cache files                                          | 05,06    |
| C11 adversarial diversity    | reviewer ≠ re-reviewer family                                                   | 04,04b   |
| C12 resumable state machines | crash parks phase, resume continues                                             | 04,12    |
| C13 intent memory            | sessions rehydrate from `/tmp/specs`                                            | 03b      |

## Coverage map (where each top-level area lives)

| Area (`git ls-files`)               | Diagram(s) |
| ----------------------------------- | ---------- |
| `home/.chezmoiscripts/`, data       | 01, 02     |
| `home/readonly_dot_default-*`       | 02         |
| `home/exact_dot_agents/`            | 03, 03b    |
| `scripts/ralph.py`, ralph config    | 04, 04b    |
| `tools/ralph-tui/`                  | 04b        |
| `home/dot_config/exact_tmux/`       | 05         |
| `home/exact_bin/` (incl. `,w`)      | 06, 07c    |
| `home/exact_lib/` command internals | 07c        |
| shell/terminal/macOS configs        | 07         |
| `home/Alfred.alfredpreferences/`    | 07         |
| `home/dot_config/exact_nvim/`       | 07b        |
| `home/private_dot_ssh/gnupg/`       | 08         |
| `home/readonly_dot_*` rc files      | 08         |
| repo meta, Makefile, CI             | 09         |
| `website/`, `docs/`                 | 10         |
| `scripts/` (helpers + tests)        | 11         |
| AI tool configs (`dot_*`)           | 12         |
| other `dot_config/*` apps           | 13         |

## Maintenance

These diagrams describe behavior, so they fall under the repo's documentation hygiene rule: when a change under `home/`, `scripts/`, or `tools/` alters a flow, command, state, or adds/removes a file, update the affected `.mmd` file in the same change. Keep them structural — defer exhaustive option lists and prose to `docs/` and source.

The per-subtree file-census counts (`Every file under X (N)` and the total tracked-file count) are enforced by `make verify-mermaids` ([`scripts/verify_mermaids.py`](../scripts/verify_mermaids.py), part of `make check`): it recomputes each count from the effective git file set (tracked files that still exist plus untracked, non-ignored files) and fails on drift, so a count change must update both the diagram prose and the script's census table.
