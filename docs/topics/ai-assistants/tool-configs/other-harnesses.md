---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

## Cross-harness subagents

Subagents are covered in [Cross-harness subagents](../subagents.md). Keep this page focused on tool configuration and config rendering; the subagent page owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

## Codex, OpenCode, Amp

| Tool     | Config source                                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../../home/dot_codex/)                                                                                   |
| OpenCode | [`home/dot_config/opencode/`](../../../../home/dot_config/opencode/)                                                               |
| Amp      | [`home/dot_config/exact_amp/private_readonly_settings.json`](../../../../home/dot_config/exact_amp/private_readonly_settings.json) |

Codex and OpenCode use profile merging with MCP injection. Amp settings are tracked directly.

Personal OpenCode exposes Cloudflare:

| Provider                | Env                                                                 | Models                                                               |
| ----------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `cloudflare-workers-ai` | `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY` | `@cf/zai-org/glm-5.2`, `@cf/moonshotai/kimi-k2.7-code`, `minimax/m3` |

`,opencode-cloudflare` wraps that provider with Fish-completable model choices.

Codex Cloudflare wrapper:

| Wrapper             | Target                                          |
| ------------------- | ----------------------------------------------- |
| `,codex-cloudflare` | Cloudflare AI Gateway OpenAI Responses endpoint |

Codex no longer supports Chat Completions wire mode, so the wrapper uses the Gateway OpenAI provider with:

- `CLOUDFLARE_GATEWAY_ID` (default `default`)
- `CLOUDFLARE_API_TOKEN`

It does not target Workers AI's `@cf/...` Chat Completions endpoint.

Other provider wrappers:

- `,codex-llama-cpp`
- `,opencode-llama-cpp`
- `,copilot-cloudflare`
- `,copilot-openrouter`

Copilot custom providers are BYOK environment variables only, so its wrappers set those variables for OpenAI-compatible endpoints.

Claude Code is not wired to Cloudflare.

Reason:

- Claude's Anthropic-compatible custom base URL path sends `x-api-key` for `ANTHROPIC_API_KEY`.
- Cloudflare's `/ai/v1/messages` endpoint requires `Authorization: Bearer ...`.
- the `ANTHROPIC_AUTH_TOKEN` path did not issue a request in the local probe.

So there is intentionally no `,claude-cloudflare` wrapper.

Amp remains lightly integrated:

- no SOP symlink.
- no MCP injection.
- no RTK hook.
- `amp.dangerouslyAllowAll: true`.

The `/agent-review` bridge uses only Amp's built-in `Task` tool and shared skills, so it adds no Amp-specific profile files or settings. If Amp comes back into regular rotation, wire it into `mcp_servers.yaml` injection and SOP fan-out before deeper configuration.

## GitHub Copilot CLI

Copilot source and install:

| Surface  | Path                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Source   | [`home/dot_copilot/`](../../../../home/dot_copilot/)                                                                            |
| Target   | `~/.copilot/`                                                                                                                   |
| Install  | Homebrew cask `copilot-cli`, binary `copilot`                                                                                   |
| Brewfile | [`brews/shared/39-applications-casks.brewfile`](../../../../home/.chezmoitemplates/brews/shared/39-applications-casks.brewfile) |

The cask auto-generates fish/zsh/bash completions, so no completion file is tracked. Copilot uses shared SOP, skills, session context, and worklog hooks; Copilot-specific hook adapters live under `home/dot_copilot/`.

| Surface            | Source                                                                                                            | Target                               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| SOP / instructions | [`symlink_copilot-instructions.md`](../../../../home/dot_copilot/symlink_copilot-instructions.md) → `~/AGENTS.md` | `~/.copilot/copilot-instructions.md` |
| Skills             | [`symlink_skills`](../../../../home/dot_copilot/symlink_skills) → `~/.agents/skills`                              | `~/.copilot/skills`                  |
| Custom agents      | [`exact_agents/`](../../../../home/dot_copilot/exact_agents/)                                                     | `~/.copilot/agents/`                 |
| MCP servers        | `mcp_servers.yaml` via `generate_mcp_configs.py copilot`                                                          | `~/.copilot/mcp-config.json`         |
| Hooks              | [`hooks.json`](../../../../home/dot_copilot/hooks.json)                                                           | `~/.copilot/hooks/agent-memory.json` |
| Settings           | [`settings.json`](../../../../home/dot_copilot/settings.json)                                                     | `~/.copilot/settings.json`           |

Key wiring decisions:

- **Instructions/skills are symlinks** (not copies): Copilot reads `$HOME/.copilot/copilot-instructions.md` as its global SOP and `~/.copilot/skills/<name>/SKILL.md` for skills. Copilot no longer reads `~/.claude/` agents/skills, so the explicit `~/.copilot/skills` symlink is required. The managed custom agents are thin `.agent.md` profiles that point back to the shared review skill; they exist only to give Copilot a runtime-native subagent surface and per-agent model settings. Internal worker profiles are model-invocable but not user-invocable, matching Copilot's source behavior: `disable-model-invocation: false` keeps them available to `session.tasks.startAgent`, while `user-invocable: false` keeps them out of direct `/agent` selection.
- **MCP: stdio only; no OAuth HTTP server.** The `copilot` transform in `generate_mcp_configs.py` emits stdio servers as `type: "local"` and (when wired) OAuth HTTP servers as `type: "http"` with `oauthClientId` + `auth.redirectPort` + `oauthScopes` for Copilot's browser `authorization_code` flow. In practice no HTTP server is wired for Copilot: it hardcodes its OAuth redirect to `http://127.0.0.1:{port}/` (only the port is configurable), which neither the SCSI Okta app nor the public Slack client registers, so the flow is rejected (HTTP 400 / `redirect_uri did not match`). `scsi-main` and `slack` therefore omit a `copilot` `oauth_by_tool` block, and `scsi-local` carries `exclude_tools: [copilot]` (no point keeping the local SCSI backend once the hosted one is gone). With the always-on `sequentialthinking` server also removed from the registry, Copilot's generated `mcp-config.json` has an empty `mcpServers` and it relies solely on its built-in servers. The built-in `github-mcp-server` is provided by Copilot and is not emitted. See [MCP servers](../mcp.md).
- **Settings are merged, not overwritten.** Copilot owns `~/.copilot/settings.json` and rewrites it at runtime (chosen `model`, `allowedUrls`, `config.json` migration), so the merge script deep-merges the declared baseline (`effortLevel: xhigh`, `keepAlive: busy`, `autoUpdate: false` to defer to the brew cask's auto-update, `banner: never`, `includeCoAuthoredBy: true`) **on top of** the live file with our keys winning, preserving the user's runtime choices. The target is in `.chezmoiignore`.
- **Hooks use PascalCase event names** (`SessionStart`, `PreToolUse`, `PostToolUse`) so Copilot delivers the VS Code-compatible snake_case payloads (`hook_event_name`, `session_id`, `tool_input`) that the shared session/worklog scripts already read — the same contract Codex uses. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

## Token optimization (RTK)

RTK output compaction is covered in [RTK token optimization](../rtk.md): agent wiring, macOS config path, excluded commands, tee behavior, and the recovery contract.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../../security/security-and-secrets.md).
