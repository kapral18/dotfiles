---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

## Cross-harness subagents

Subagents are covered in [Cross-harness subagents](../subagents.md). Keep this page focused on tool configuration and config rendering; the subagent page owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

## Codex and OpenCode

| Tool     | Config source                                                        |
| -------- | -------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../../home/dot_codex/)                     |
| OpenCode | [`home/dot_config/opencode/`](../../../../home/dot_config/opencode/) |

Codex and OpenCode use profile merging with MCP injection. `,codex` sessions go through the `~/bin/,codex` shim only so local llama.cpp model selections can inject the local model catalog before falling through to the real Codex binary.

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

Copilot custom providers are BYOK environment variables only, so its wrappers set those variables for OpenAI-compatible endpoints. Both provider wrappers `exec ,copilot` rather than `copilot`, so the header-auth MCP token refresh below runs before the custom upstream starts.

Claude Code is not wired to Cloudflare.

Reason:

- Claude's Anthropic-compatible custom base URL path sends `x-api-key` for `ANTHROPIC_API_KEY`.
- Cloudflare's `/ai/v1/messages` endpoint requires `Authorization: Bearer ...`.
- the `ANTHROPIC_AUTH_TOKEN` path did not issue a request in the local probe.

So there is intentionally no `,claude-cloudflare` wrapper.

## GitHub Copilot CLI

Copilot source and install:

| Surface  | Path                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Source   | [`home/private_dot_copilot/`](../../../../home/private_dot_copilot/)                                                            |
| Target   | `~/.copilot/`                                                                                                                   |
| Install  | Homebrew cask `copilot-cli`, binary `copilot`                                                                                   |
| Brewfile | [`brews/shared/39-applications-casks.brewfile`](../../../../home/.chezmoitemplates/brews/shared/39-applications-casks.brewfile) |

The cask auto-generates fish/zsh/bash completions, so no completion file is tracked. Copilot uses shared SOP, skills, session context, and worklog hooks; Copilot-specific hook adapters live under `home/private_dot_copilot/`.

| Surface            | Source                                                                                                                    | Target                               |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| SOP / instructions | [`symlink_copilot-instructions.md`](../../../../home/private_dot_copilot/symlink_copilot-instructions.md) → `~/AGENTS.md` | `~/.copilot/copilot-instructions.md` |
| Skills             | [`symlink_skills`](../../../../home/private_dot_copilot/symlink_skills) → `~/.agents/skills`                              | `~/.copilot/skills`                  |
| Custom agents      | [`exact_agents/`](../../../../home/private_dot_copilot/exact_agents/)                                                     | `~/.copilot/agents/`                 |
| MCP servers        | `mcp_servers.yaml` via `generate_mcp_configs.py copilot`                                                                  | `~/.copilot/mcp-config.json`         |
| Hooks              | [`hooks.json`](../../../../home/private_dot_copilot/hooks.json)                                                           | `~/.copilot/hooks/agent-memory.json` |
| Settings           | [`settings.json`](../../../../home/private_dot_copilot/settings.json)                                                     | `~/.copilot/settings.json`           |

Key wiring decisions:

- **Instructions/skills are symlinks** (not copies): Copilot reads `$HOME/.copilot/copilot-instructions.md` as its global SOP and `~/.copilot/skills/<name>/SKILL.md` for skills. Copilot no longer reads `~/.claude/` agents/skills, so the explicit `~/.copilot/skills` symlink is required. The managed custom agents are thin `.agent.md` profiles that point back to the shared review skill; they exist only to give Copilot a runtime-native subagent surface and per-agent model settings. Internal worker profiles are model-invocable but not user-invocable, matching Copilot's source behavior: `disable-model-invocation: false` keeps them available to `session.tasks.startAgent`, while `user-invocable: false` keeps them out of direct `/agent` selection.
- **MCP: stdio (`type: "local"`), OAuth HTTP, or header-auth HTTP.** The `copilot` transform in `generate_mcp_configs.py` emits stdio servers as `type: "local"`, OAuth HTTP servers as `type: "http"` with `oauthClientId` + `auth.redirectPort` + `oauthScopes`, and — when the `copilot` block carries `headerAuth` — a header-auth HTTP server as `type: "http"` with `headers.Authorization` (OAuth keys skipped). Copilot cannot run the SCSI/Slack browser OAuth flows itself: it hardcodes its OAuth redirect to `http://127.0.0.1:{port}/` (only the port is configurable), which neither the SCSI Okta app nor the public Slack client registers, and Slack's MCP authorization server offers no dynamic client registration and requires a client secret at the token endpoint. So both `scsi-main` and `slack` give their `copilot` block a `headerAuth: "$(,mcp-token <server> --bearer)"`, and Copilot reaches each with a bearer token minted by cursor-cli (both servers accept header bearer auth). If the cursor cache is stale during `chezmoi apply`, the generator emits a refresh placeholder for that header instead of failing the apply; the `,copilot` wrapper still detects the header-auth server, refreshes it quietly (`--login --quiet` with output discarded), and re-bakes before launch. If refresh fails, re-bake fails, or a placeholder remains, the wrapper exits before starting Copilot. For opaque tokens such as Slack, `,mcp-token` uses a per-server refresh ledger in `~/.cache/mcp-token/` instead of the shared cursor cache file mtime; SCSI JWTs use their `exp`. Because Copilot reads each Authorization header once at launch and never reloads it, the `,copilot` wrapper does this proactively: before launch, it derives the header-auth HTTP servers from `~/.copilot/mcp-config.json`, refreshes each stale token without streaming cursor-agent auth logs or the final raw token, and re-bakes the fresh tokens by re-running the hook's generator (`generate_mcp_configs.py … copilot`, located via `chezmoi data`). The token-bearing `~/.copilot/mcp-config.json` is written `0600` under a `0700` `~/.copilot/` directory. Plain `,copilot` then launches the real Copilot CLI natively. `scsi-local` has no OAuth (local stdio with `pass` Elasticsearch credentials), so it is emitted as a `type: "local"` server. Copilot's generated `mcp-config.json` therefore carries `scsi-main`, `scsi-local`, and `slack` plus its built-in servers. The built-in `github-mcp-server` is provided by Copilot and is not emitted. See [MCP servers](../mcp.md).
- **Settings are merged, not overwritten.** Copilot owns `~/.copilot/settings.json` and rewrites it at runtime (chosen `model`, `allowedUrls`, `config.json` migration), so the merge script deep-merges the declared baseline (`effortLevel: xhigh`, `keepAlive: busy`, `autoUpdate: false` to defer to the brew cask's auto-update, `banner: never`, `includeCoAuthoredBy: true`) **on top of** the live file with our keys winning, preserving the user's runtime choices. The target is in `.chezmoiignore`.
- **Hooks use PascalCase event names** (`SessionStart`, `PreToolUse`, `PostToolUse`) so Copilot delivers the VS Code-compatible snake_case payloads (`hook_event_name`, `session_id`, `tool_input`) that the shared session/worklog scripts already read — the same contract Codex uses. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

## tuicr (review TUI)

[tuicr](https://github.com/agavra/tuicr) is a terminal UI for code review, not an LLM harness. Its config is single-sourced and read-only.

| Surface | Path                                                                                                   | Target                        |
| ------- | ------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Config  | [`home/dot_config/tuicr/readonly_config.toml`](../../../../home/dot_config/tuicr/readonly_config.toml) | `~/.config/tuicr/config.toml` |

The config defines the review **comment types** (`issue`, `suggestion`, `question`, `nit`, `praise`) that tuicr exports as `[LABEL]` prefixes in the markdown an agent consumes. These are actionable categories, not severity — severity (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) stays internal per the `~/AGENTS.md` review SOP and is intentionally not encoded here, so tuicr labels and the review skill's severity model do not collide.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../../security/security-and-secrets.md).
