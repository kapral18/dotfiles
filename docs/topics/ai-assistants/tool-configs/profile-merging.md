---
sidebar_position: 2
title: Config merging
---

# Config file merging

Some assistant tools rewrite their config files at runtime, so chezmoi does not treat the deployed target as the source of truth. The repo keeps one source file per harness, and `run_onchange` scripts render it into the live target only when content differs.

This avoids complex templates and comment filters. Mixed-ownership targets pass through typed reconcilers that know which runtime fields may survive.

## Mental model

| Step | What happens                                                                                                                                |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | The merge script reads its one source file.                                                                                                 |
| 2    | Mixed-ownership targets pass through a typed ownership-aware reconciler.                                                                    |
| 3    | It writes the final destination only when content differs and updates both the generic checksum manifest and the AI effective-state ledger. |
| 4    | Tool-specific formats stay decoupled.                                                                                                       |

All merge scripts live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/) and source [`scripts/chezmoi_lib.sh`](../../../../scripts/chezmoi_lib.sh).

## Reference matrix

| Tool                 | Source files                                                                                                                                                                                                          | Target                               | Merge script                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.personal.json`](../../../../home/dot_claude/settings.personal.json)                                                                                                                        | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| OpenCode config+MCP  | [`home/dot_config/opencode/readonly_opencode.personal.jsonc`](../../../../home/dot_config/opencode/readonly_opencode.personal.jsonc)                                                                                  | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP     | [`home/dot_codex/private_config.personal.toml`](../../../../home/dot_codex/private_config.personal.toml)                                                                                                              | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models   | [`home/dot_pi/agent/readonly_settings.personal.json`](../../../../home/dot_pi/agent/readonly_settings.personal.json) + [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |

## Using it

Pi targets are installed readonly. Both shared write helpers enforce the requested file mode even when content already matches, without rewriting matching bytes. The string helper compares the exact bytes it would write (`desired` plus one newline), so missing or extra trailing newlines are corrected.

Codex rebuilds from its source base and reattaches only MCP approvals, hook trust, valid project trust, and valid TUI counters. Trailing comments on TOML table headers preserve the same runtime state as equivalent uncommented headers.

MCP-server injection for each tool is covered in [MCP servers](../mcp.md).

## Internals (for maintainers)

### Effective-state trace

Each successful 07-hook write records one schema-v1 artifact row under `~/.local/state/chezmoi/generated_artifacts.v1.json`.

The row carries:

- producer
- complete repo-local input/transform hashes
- target
- ownership adapter
- expected owned semantic hash
- consumer
- local consumer probe (defaults to `--version`; `record --probe-arg` overrides its arguments)

Claude settings provenance includes the selected settings file and the owning merge-hook template. Settings-file changes report `input-drift`; changes to the hook itself report `transform-drift`, even before target bytes change.

Claude MCP merging rejects malformed existing JSON before writing, preserves unrelated live keys, and creates a missing file even for an empty registry.

### `,doctor ai`

`,doctor ai` evaluates generated artifact rows without changing anything.

| Check                    | Rule                                                  |
| ------------------------ | ----------------------------------------------------- |
| whole-file outputs       | compare exact bytes                                   |
| Claude MCP               | compare only `mcpServers`                             |
| Codex                    | ignore only its four explicit runtime-owned buckets   |
| source/transform changes | report stale state until the matching hook runs again |

Default output is static. `,doctor ai --live` adds deduplicated local harness probes; it does not apply chezmoi, refresh credentials, or use the network.
