---
sidebar_position: 7
---

# Tool Configs

Per-assistant configuration: the Cursor CLI harness, the profile-based merging mechanism, and each tool's settings source. MCP servers and model lists are single-sourced separately (see [MCP servers](mcp.md) and [Model registry & routing](model-registry.md)).

## Cursor agent CLI

A cross-shell alias `agent` is provided for `cursor-agent`:

- POSIX interactive shells: [`home/readonly_dot_shellrc`](../../../home/readonly_dot_shellrc) → `~/.shellrc`
- fish: [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl) → `~/.config/fish/config.fish`

```bash
command -v agent
agent --help
```

Cursor CLI is the primary interactive assistant harness. Its user-level hooks (session context, worklog, evidence ledger) make up the hook-memory layer — documented in [Agent memory](knowledge-base.md).

### Tmux agent prompt wrap

When running an AI coding agent (`claude`, `cursor-agent`, or `pi`) inside tmux, `Alt-Enter` is intercepted to prepend a calibrated verification scaffold to your prompt before submitting.

- **Binding:** `Alt-Enter` (submits the wrapped prompt)
- **Toggle:** `prefix` + `W` (toggles wrapping on/off for the session)
- **Prefix text:** [`home/dot_config/exact_tmux/agent_prompts/prefix.txt`](../../../home/dot_config/exact_tmux/agent_prompts/prefix.txt)

Plain `Enter` is never touched. `Alt-Enter` is passed through untouched in non-agent panes or when the toggle is OFF.

## Profile-based file merging

Some tools rewrite their config files at runtime, so chezmoi ignores the on-disk target and a `run_onchange` script writes the correct profile-specific version from the repo source.

Instead of keeping complex templates or comment-based filtering logic, we use explicit `.work.*` and `.personal.*` files. The shell script checks the `.isWork` template variable and copies the correct source to the final destination, completely decoupling the formats. All merge scripts live under [`home/.chezmoiscripts/`](../../../home/.chezmoiscripts/) and source the shared [`scripts/chezmoi_lib.sh`](../../../scripts/chezmoi_lib.sh) helper library.

| Tool                 | Source files                                                                                                                                                          | Target                               | Merge script                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Claude Code settings | [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/)                                                                                          | `~/.claude/settings.json`            | `run_onchange_after_07-merge-claude-code-settings.sh.tmpl` |
| Gemini settings+MCP  | [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json) + [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml)                         | `~/.gemini/settings.json`            | `run_onchange_after_07-merge-gemini-settings.sh.tmpl`      |
| OpenCode config+MCP  | [`home/dot_config/opencode/readonly_opencode.{work,personal}.jsonc`](../../../home/dot_config/opencode/)                                                              | `~/.config/opencode/opencode.jsonc`  | `run_onchange_after_07-merge-opencode-config.sh.tmpl`      |
| Codex config+MCP     | [`home/dot_codex/private_config.{work,personal}.toml`](../../../home/dot_codex/)                                                                                      | `~/.codex/config.toml`               | `run_onchange_after_07-merge-codex-config.sh.tmpl`         |
| Pi settings/models   | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../home/dot_pi/agent/) + [`readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json) | `~/.pi/agent/{settings,models}.json` | `run_onchange_after_07-merge-pi-config.sh.tmpl`            |

Pi targets are installed readonly. MCP-server injection for each tool is covered in [MCP servers](mcp.md).

## Claude Code settings

Source: [`home/dot_claude/settings.{work,personal}.json`](../../../home/dot_claude/) → `~/.claude/settings.json`.

Both profiles enable extended thinking and skip the dangerous-mode permission prompt. The work profile uses native Claude enterprise auth by default (no `apiKeyHelper` or `ANTHROPIC_BASE_URL` override). MCP servers are stored separately in `~/.claude.json` (top-level `mcpServers` field) because that file contains runtime state managed by Claude Code; the merge script surgically updates only the `mcpServers` key, leaving other fields intact.

**LetsFG** is intentionally not exposed through the shared MCP registry because its tools are irrelevant to most sessions. Agents load [`~/.agents/skills/letsfg/SKILL.md`](../../../home/exact_dot_agents/exact_skills/exact_letsfg/readonly_SKILL.md) on demand and use the local `letsfg` uv tool from [`home/readonly_dot_default-uv-tools.tmpl`](../../../home/readonly_dot_default-uv-tools.tmpl) for free local searches that return direct airline/OTA `booking_url` values. Normal agent searches pass `LETSFG_BROWSERS=0` on each `letsfg` invocation so LetsFG skips browser connectors without changing the user shell environment; browser connectors are explicit opt-in. Playwriter headless browser automation remains a fallback for rendered UI checks or booking-adjacent flows that need explicit user confirmation.

## Gemini CLI settings

Source: [`home/dot_gemini/settings.json`](../../../home/dot_gemini/settings.json) → `~/.gemini/settings.json`.

- MCP servers are injected from the shared [`mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) registry at apply time (no longer hardcoded in the settings file).
- Tool approval is controlled by `general.defaultApprovalMode` (we use `auto_edit` to auto-approve edit tools).

## Pi coding agent settings

**Installation:** Pi globals are installed via yarn from [`home/readonly_dot_default-yarn-pkgs`](../../../home/readonly_dot_default-yarn-pkgs) → `~/.default-yarn-pkgs`:

| Package                           | Purpose               |
| --------------------------------- | --------------------- |
| `@earendil-works/pi-coding-agent` | Core Pi agent         |
| `@earendil-works/pi-tui`          | Pi TUI (work profile) |
| `pi-mcp-adapter`                  | MCP adapter extension |

**Config sources:**

| Config            | Source                                                                                                                                                                                        |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Settings + models | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../home/dot_pi/agent/) + shared [`readonly_models.json`](../../../home/dot_pi/agent/readonly_models.json) → `~/.pi/agent/` |
| MCP servers       | [`home/.chezmoidata/mcp_servers.yaml`](../../../home/.chezmoidata/mcp_servers.yaml) (shared registry) → `~/.pi/agent/mcp.json`                                                                |

**Profile defaults:** both work and personal default to provider `openrouter`, model `moonshotai/kimi-k2.6`. The work profile also exposes additional configured models alongside the OpenRouter default.

**Shared settings:**

- Automatic context compaction (saves tokens)
- Exponential backoff retries
- Pi loads `pi-mcp-adapter` from a yarn global `node_modules` path in Pi settings (avoids Pi-managed npm update prompts). `@earendil-works/pi-tui` stays yarn-managed but is not loaded as a Pi extension package.
- Shell PATH order keeps `~/.yarn/bin` ahead of runtime-manager shims so `pi` resolves to the yarn-managed binary
- Secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`) are picked up from environment variables exported via `pass` in `config.fish.tmpl`

The work-profile LiteLLM provider and the local llama.cpp provider for Pi are covered in [Model registry & routing](model-registry.md) and [llama.cpp local inference](llama-cpp.md).

## Codex, OpenCode, Amp

| Tool     | Config source                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../home/dot_codex/)                                                                                   |
| OpenCode | [`home/dot_config/opencode/`](../../../home/dot_config/opencode/)                                                               |
| Amp      | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../../home/dot_config/exact_amp/private_readonly_settings.json) |

Codex and OpenCode use the profile-merging mechanism above (with MCP injection); Amp settings are tracked directly. Codex also has a llama.cpp launcher wrapper — see [llama.cpp local inference](llama-cpp.md#codex-launcher-metadata).

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../security/security-and-secrets.md).

## Related

- [MCP servers](mcp.md) — single-sourced server registry
- [Model registry & routing](model-registry.md) — single-sourced model definitions
- [llama.cpp local inference](llama-cpp.md) — local backend + Claude/Codex launchers
- [The Agentic Operating System](index.md) — governance layer
