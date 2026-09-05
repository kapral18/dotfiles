---
sidebar_position: 2
title: Profile-based merging
---

# Profile-based file merging

Some assistant tools rewrite their config files at runtime, so chezmoi does not treat the deployed target as the source of truth. The repo keeps explicit profile sources, and `run_onchange` scripts render the selected profile into the live target only when content differs.

This avoids complex templates and comment filters. Work/personal differences live in `.work.*` and `.personal.*` files, while mixed-ownership targets pass through typed reconcilers that know which runtime fields may survive.

## Mental model

| Step | What happens                                                                                                                                |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | The merge script checks the `.isWork` template variable.                                                                                    |
| 2    | It picks the correct source file.                                                                                                           |
| 3    | Mixed-ownership targets pass through a typed ownership-aware reconciler.                                                                    |
| 4    | It writes the final destination only when content differs and updates both the generic checksum manifest and the AI effective-state ledger. |
| 5    | Tool-specific formats stay decoupled.                                                                                                       |

All merge scripts live under [`home/.chezmoiscripts/`](../../../../home/.chezmoiscripts/) and source [`scripts/chezmoi_lib.sh`](../../../../scripts/chezmoi_lib.sh).

## Reference matrix

| Tool                           | Source files                                                                                                                                                                                                                                                                                                                            | Target                                                                             | Merge script                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Claude Code settings           | [`home/dot_claude/settings.{work,personal}.json`](../../../../home/dot_claude/)                                                                                                                                                                                                                                                         | `~/.claude/settings.json`                                                          | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| OpenCode config+MCP            | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../../home/dot_config/opencode/)                                                                                                                                                                                                                             | `~/.config/opencode/opencode.jsonc`                                                | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP               | [`home/dot_codex/private_config.{work,personal}.toml`](../../../../home/dot_codex/)                                                                                                                                                                                                                                                     | `~/.codex/config.toml`                                                             | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models             | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) / [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json)                                                            | `~/.pi/agent/{settings,models}.json`                                               | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |
| Copilot settings+MCP+extension | [`home/private_dot_copilot/settings.json`](../../../../home/private_dot_copilot/settings.json) + [`exact_extensions/exact_agent-memory/readonly_extension.mjs`](../../../../home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs) + [`mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml) | `~/.copilot/{settings.json,mcp-config.json,extensions/agent-memory/extension.mjs}` | `run_onchange_after_07-merge-copilot-config.sh.tmpl`       |

## Using it

Pi targets are installed readonly. Both shared write helpers enforce the requested file mode even when content already matches, without rewriting matching bytes. The string helper compares the exact bytes it would write (`desired` plus one newline), so missing or extra trailing newlines are corrected.

Codex rebuilds from its profile base and reattaches only MCP approvals, hook trust, valid project trust, and valid TUI counters. Trailing comments on TOML table headers preserve the same runtime state as equivalent uncommented headers.

Copilot recursively preserves undeclared runtime settings, lets declared policy win, and replaces only `subagents.agents` exactly so stale agents and per-agent overrides cannot survive.

MCP-server injection for each tool is covered in [MCP servers](../mcp.md).

## Internals (for maintainers)

### Effective-state trace

Each successful 07-hook write records one schema-v1 artifact row under `~/.local/state/chezmoi/generated_artifacts.v1.json`.

The row carries:

- producer
- selected profile
- complete repo-local input/transform hashes
- target
- ownership adapter
- expected owned semantic hash
- consumer
- local consumer probe (defaults to `--version`; `record --probe-arg` overrides its arguments)

Copilot MCP rendering is apply-time only: `run_onchange_after_07-merge-copilot-config.sh.tmpl` owns the target and its `copilot-mcp` ledger row. Runtime `,copilot` does not render config or change the ledger; it only replaces bare `--resume` with a locally selected `--session-id=<id>` to avoid Copilot 1.0.73's MCP startup race. Hosted authentication rotates inside the per-request stdio bridges.

Claude settings provenance includes the selected settings file, model-tier registry, and the owning merge-hook template. Registry changes report `input-drift`; changes to the hook itself report `transform-drift`, even before target bytes change.

Claude MCP merging rejects malformed existing JSON before writing, preserves unrelated live keys, and creates a missing file even for an empty registry. The Cursor OAuth mint artifact names its actual consumer, `,mcp-token`, and probes `--help` because that command has no `--version` option. Claude model-mirror defaults, curated models, recommendations, and provenance follow `category_models.claude_code.orchestrate`, the same owner used by the settings renderer.

### `,doctor ai`

`,doctor ai` evaluates generated artifact rows without changing anything.

| Check                    | Rule                                                                        |
| ------------------------ | --------------------------------------------------------------------------- |
| whole-file outputs       | compare exact bytes                                                         |
| Claude MCP               | compare only `mcpServers`                                                   |
| Copilot settings         | follow the declared baseline shape and require `subagents.agents` exactness |
| Codex                    | ignore only its four explicit runtime-owned buckets                         |
| source/transform changes | report stale state until the matching hook runs again                       |

Default output is static. `,doctor ai --live` adds deduplicated local harness probes; it does not apply chezmoi, refresh credentials, or use the network.
