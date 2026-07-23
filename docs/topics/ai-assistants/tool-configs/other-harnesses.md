---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

This page covers assistant-adjacent tools that do not have their own page in this section: Codex, OpenCode, GitHub Copilot CLI, and tuicr. It stays at the configuration and rendering layer; [Cross-harness subagents](../subagents.md) owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

Use it to answer three questions: which repo source owns the deployed config, which wrapper runs before the native binary, and which runtime-owned fields are allowed to survive a merge.

## Mental model

| Area                      | Current rule                                                                                        |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| Codex and OpenCode        | profile merging plus MCP injection                                                                  |
| Codex launcher            | interactive shells route `codex` through managed `~/bin/,codex`                                     |
| Copilot launcher wrappers | custom providers are BYOK environment variables only and wrapper commands `exec ,copilot`           |
| Vertex adapter            | per-wrapper loopback process translates Responses, Chat Completions, and Anthropic Messages         |
| Copilot MCP               | generated as stdio `type: "local"`, OAuth HTTP, or token-bridge stdio depending on the server block |
| Copilot memory            | native SDK extension supplies context and worklog hooks                                             |
| tuicr                     | single-sourced readonly review TUI config; labels are categories, not severity                      |
| secrets                   | runtime API keys come from `pass`, not committed tool config files                                  |

## Codex and OpenCode

### Config sources

| Tool     | Config source                                                        |
| -------- | -------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../../home/dot_codex/)                     |
| OpenCode | [`home/dot_config/opencode/`](../../../../home/dot_config/opencode/) |

Codex and OpenCode use profile merging with MCP injection.

The interactive `codex` command routes through the managed `~/bin/,codex` shim in interactive shells. The shim injects the local llama.cpp model catalog when needed and then falls through to the real Codex binary; hosted MCP auth needs no launch-time work because those servers run as `,mcp-token --bridge` stdio bridges.

### Codex profiles and approvals

Codex policy settings are profile-specific.

| Profile                   | Policy                                                                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| work interactive          | managed-device requirements with `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, and `sandbox_mode = "workspace-write"` |
| personal interactive      | `approval_policy = "never"` with `sandbox_mode = "danger-full-access"`                                                                          |
| read-only worker profiles | `approval_policy = "untrusted"` with `sandbox_mode = "read-only"`                                                                               |

Repeated exact-command approvals can be captured by Codex execpolicy `*.rules` files under `~/.codex/rules/`. Those rules should stay narrow because explicit allow rules also bypass sandboxing for the matched command prefix.

Repeated MCP tool approvals live as `mcp_servers.<server>.tools.<tool>.approval_mode = "approve"` in `~/.codex/config.toml`. The Codex merge hook preserves those runtime-written approval overrides when it regenerates the managed MCP blocks.

`scsi-main` and `scsi-local` are generated with `default_tools_approval_mode = "approve"` so their read-analysis tools do not depend on the flaky MCP approval persistence path. Slack is only auto-approved for read/search tools (`slack_read_*` and `slack_search_*`), while send/create/update/schedule tools stay prompted/auto-reviewed.

Both interactive profiles pin `service_tier = "default"` so `gpt-5.5` starts on standard routing instead of priority/legacy `fast` routing.

### Codex reconciliation

Codex reconciliation rebuilds from the selected profile and generated MCP registry, then reattaches four explicitly runtime-owned buckets.

| Runtime-owned bucket           | Rule                                           |
| ------------------------------ | ---------------------------------------------- |
| MCP approval overrides         | valid values only                              |
| `[hooks.state.*].trusted_hash` | reattached                                     |
| `projects.*.trust_level`       | reattached when it is `trusted` or `untrusted` |
| `tui.model_availability_nux.*` | counters in `0..4294967295`                    |

All unrelated live tables and invalid values are discarded. Matching source tables remain authoritative. Hook trust hashes are not baked into `home/dot_codex/private_config.*.toml`.

### OpenCode Cloudflare provider

Personal OpenCode exposes Cloudflare.

| Provider                | Env                                                                 | Models                                                               |
| ----------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `cloudflare-workers-ai` | `CLOUDFLARE_WORKERS_AI_ACCOUNT_ID`, `CLOUDFLARE_WORKERS_AI_API_KEY` | `@cf/zai-org/glm-5.2`, `@cf/moonshotai/kimi-k2.7-code`, `minimax/m3` |

`,opencode-cloudflare` wraps that provider with Fish-completable model choices.

### Provider wrappers

Codex Cloudflare wrapper:

| Wrapper             | Target                                          |
| ------------------- | ----------------------------------------------- |
| `,codex-cloudflare` | Cloudflare AI Gateway OpenAI Responses endpoint |

The wrapper uses the Gateway OpenAI provider with:

- `CLOUDFLARE_GATEWAY_ID` (default `default`)
- `CLOUDFLARE_API_TOKEN`

It does not target Workers AI's `@cf/...` Chat Completions endpoint. Chat Completions wire mode is not a supported Codex target.

Other provider wrappers:

- `,codex-llama-cpp`
- `,opencode-llama-cpp`
- `,copilot-cloudflare`
- `,copilot-litellm`
- `,copilot-openrouter`

Copilot custom providers are BYOK environment variables only, so its wrappers set those variables for OpenAI-compatible endpoints. The provider wrappers `exec ,copilot` rather than `copilot` to keep one stable entry point.

`,copilot-litellm` uses `LITELLM_API_BASE` / `LITELLM_PROXY_KEY`, falling back to the `litellm/api/base` and `litellm/api/token` pass entries when the environment is not already populated.

Select a LiteLLM model with `,copilot-litellm <llm-gateway/model>` or `,copilot-litellm --model <llm-gateway/model>`. The wrapper keeps the gateway slug as Copilot's wire model and maps known slugs such as `llm-gateway/claude-opus-4-7` to Copilot's internal `claude-opus-4.7` spelling for model metadata.

`,copilot-openrouter` routes `anthropic/*` and `~anthropic/*` models through `COPILOT_PROVIDER_TYPE=anthropic` against `https://openrouter.ai/api` with no `/v1` suffix. It does this instead of the default `openai`-type client against `https://openrouter.ai/api/v1`.

This matters because Copilot CLI's BYOK client only sets `enableCacheControl: true` and injects Anthropic `cache_control` breakpoints for `COPILOT_PROVIDER_TYPE=anthropic`. The default `openai`-type client always sends `enableCacheControl: false`, so prompt caching never activates for it regardless of what the upstream model supports.

Every other OpenRouter model, including GLM, DeepSeek, Qwen, Kimi, GPT, and Gemini, still uses the `openai`-type client. OpenRouter's public model-endpoints API currently reports `supports_implicit_caching: false` for all providers, so there is no caching benefit to gain there.

Setting `COPILOT_PROVIDER_TYPE` explicitly before invoking the wrapper always overrides this auto-detection.

### Repo-owned Vertex adapter

`,codex-vertex`, `,copilot-vertex`, and `,claude-vertex` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The adapter uses the configured Google Cloud project and refreshes `gcloud auth print-access-token` credentials behind the local protocol boundary; no Google bearer or project credential is written to generated config.

The three local frontends map to the two Vertex transports:

| Wrapper           | Local protocol          | Vertex transport                                                                   |
| ----------------- | ----------------------- | ---------------------------------------------------------------------------------- |
| `,codex-vertex`   | OpenAI Responses        | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |
| `,copilot-vertex` | OpenAI Chat Completions | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |
| `,claude-vertex`  | Anthropic Messages      | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |

The canonical `provider_models` entries in `home/.chezmoidata/ai_models.yaml` own the four allowed IDs, backend wire IDs, token limits, and effort matrix. `home/dot_config/vertex-adapter/readonly_models.json.tmpl` renders that data for the deployed core in `~/lib/,vertex-adapter/`. For Codex, the launcher also renders an owner-only, per-session `model_catalog_json` from the same registry and removes it on exit; the loopback `/v1/models` route exposes the equivalent Codex schema so these non-OpenAI IDs use their declared context, effort, shell, and freeform `apply_patch` metadata instead of fallback metadata.

All wrappers use `gemini-3.6-flash` unless `--model`/`-m` selects `gemini-3.1-pro-preview`, `claude-opus-4-6`, or `claude-opus-4-7`. `--thinking` enables the model's declared default, `--effort` selects a supported level, and `--no-thinking` is accepted only for the Claude models. Gemini 3.6 Flash's closest low-reasoning mode is `--effort minimal`; Gemini 3.1 Pro cannot disable thinking.

Streaming text and parallel function/custom tools are translated incrementally. Gemini tool-call thought signatures and Claude signed thinking blocks that cannot cross another protocol directly are stored by call ID in owner-only runtime state under `${XDG_STATE_HOME:-~/.local/state}/vertex-adapter/`; no user prompts, credentials, or general conversation transcript are added to that store.

Cursor is intentionally absent: Cursor Agent has no custom model-provider/base-URL route, so a `,cursor-vertex` command would not make Cursor use Vertex. Native `vlaude` also remains unchanged for direct Claude Code → Vertex Claude use.

### Claude Code and Cloudflare

Claude Code is not wired to Cloudflare.

Reason:

- Claude's Anthropic-compatible custom base URL path sends `x-api-key` for `ANTHROPIC_API_KEY`.
- Cloudflare's `/ai/v1/messages` endpoint requires `Authorization: Bearer ...`.
- the `ANTHROPIC_AUTH_TOKEN` path did not issue a request in the local probe.

So there is intentionally no `,claude-cloudflare` wrapper.

### Codex hosted MCP token bridges

`inject_mcp_into_codex_toml.py` emits `slack` and `scsi-main` as `,mcp-token <source> --bridge --url <url>` command servers, not inline secrets or env-var contracts.

The bridge injects a freshly selected bearer per request, rotating through cursor's refresh grant behind the seam, so a Codex session outlives any single token.

## GitHub Copilot CLI

### Source and install

| Surface  | Path                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Source   | [`home/private_dot_copilot/`](../../../../home/private_dot_copilot/)                                                            |
| Target   | `~/.copilot/`                                                                                                                   |
| Install  | Homebrew cask `copilot-cli`, binary `copilot`                                                                                   |
| Brewfile | [`brews/shared/39-applications-casks.brewfile`](../../../../home/.chezmoitemplates/brews/shared/39-applications-casks.brewfile) |

The cask auto-generates fish/zsh/bash completions for the native binary. Comma wrappers track their Fish completions under `home/dot_config/fish/completions/`.

Copilot uses shared SOP, skills, session context, and worklog hooks. The Copilot-specific SDK adapter lives under `home/private_dot_copilot/`.

### Rendered surfaces

| Surface                | Source                                                                                                                                                          | Target                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| SOP / instructions     | [`symlink_copilot-instructions.md`](../../../../home/private_dot_copilot/symlink_copilot-instructions.md) → `~/AGENTS.md`                                       | `~/.copilot/copilot-instructions.md`               |
| Skills                 | [`symlink_skills`](../../../../home/private_dot_copilot/symlink_skills) → `~/.agents/skills`                                                                    | `~/.copilot/skills`                                |
| Custom agents          | [`exact_agents/`](../../../../home/private_dot_copilot/exact_agents/)                                                                                           | `~/.copilot/agents/`                               |
| MCP servers            | `mcp_servers.yaml` via `generate_mcp_configs.py copilot`                                                                                                        | `~/.copilot/mcp-config.json`                       |
| Agent-memory extension | [`exact_extensions/exact_agent-memory/readonly_extension.mjs`](../../../../home/private_dot_copilot/exact_extensions/exact_agent-memory/readonly_extension.mjs) | `~/.copilot/extensions/agent-memory/extension.mjs` |
| Settings               | [`settings.json`](../../../../home/private_dot_copilot/settings.json)                                                                                           | `~/.copilot/settings.json`                         |

### Instructions, skills, and agents

Instructions and skills are symlinks, not copies. Copilot reads `$HOME/.copilot/copilot-instructions.md` as its global SOP and `~/.copilot/skills/<name>/SKILL.md` for skills.

The explicit `~/.copilot/skills` symlink is required, and the Copilot path does not depend on `~/.claude/` agents or skills.

The managed custom agents are thin `.agent.md` profiles that point back to the shared review skill. `settings.json` owns the exact agent roster plus effort/context policy, while profile frontmatter owns registry-rendered model selection.

Internal worker profiles are model-invocable but not user-invocable. `disable-model-invocation: false` keeps them available to `session.tasks.startAgent`, while `user-invocable: false` keeps them out of direct `/agent` selection.

### Copilot MCP modes

The `copilot` transform in `generate_mcp_configs.py` emits three MCP server shapes.

| Server shape              | Generated form                                                                                                    |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| stdio servers             | `type: "local"`                                                                                                   |
| OAuth HTTP servers        | `type: "http"` with `oauthClientId` + `auth.redirectPort` + `oauthScopes`                                         |
| token-bridge HTTP servers | `type: "local"` running `,mcp-token <source> --bridge --url <url>` when the `copilot` block carries `tokenBridge` |

Because Copilot cannot run the SCSI/Slack browser OAuth flows itself, both `scsi-main` and `slack` carry a `copilot` `tokenBridge` source and reach the hosted endpoint through a local stdio bridge that injects a bearer token minted by cursor-cli per request. `scsi-local` has no OAuth, so it is emitted as a `type: "local"` stdio server with local `pass` Elasticsearch credentials. Copilot's generated `mcp-config.json` therefore carries `scsi-main`, `scsi-local`, and `slack` plus its built-in servers; the built-in `github-mcp-server` is Copilot-provided and not emitted.

The rendered config carries no Authorization values, so `chezmoi apply` owns it entirely. `,copilot` passes through to the real binary except for bare `--resume`, which selects a local session before launching `--session-id=<id>` to avoid Copilot 1.0.73's MCP startup race. The full OAuth-exception rationale, synchronous rotation grant, and opaque-token liveness probe are owned by [MCP servers](../mcp.md). The bearer-free `~/.copilot/mcp-config.json` is written `0600` under a `0700` `~/.copilot/` directory.

### Copilot settings reconciliation

Copilot owns `~/.copilot/settings.json` and rewrites it at runtime, including chosen `model`, `allowedUrls`, and `config.json` migration.

The typed reconciler recursively preserves live keys absent from the baseline and lets declared values win. It replaces `subagents.agents` exactly with the seven declared agents, which removes stale agent names and persisted per-agent model/effort/context overrides while preserving unrelated runtime preferences.

The target is in `.chezmoiignore`.

### Copilot agent memory

A live probe of Copilot 1.0.68 showed that its JSON command hooks run from `~/.copilot/hooks/*.json`, but their `SessionStart` stdout is not ingested as context.

The active context path is the `agent-memory` extension. It registers `onSessionStart`, `onPostToolUse`, and `onPostToolUseFailure`, translates Copilot's camelCase SDK payloads to the shared snake_case script contract, and returns SDK `additionalContext`.

The command-hook file and its legacy checksum row are cleaned up by the apply hook. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

## tuicr (review TUI)

[tuicr](https://github.com/agavra/tuicr) is a terminal UI for code review, not an LLM harness. Its config is single-sourced and read-only.

| Surface | Path                                                                                                   | Target                        |
| ------- | ------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Config  | [`home/dot_config/tuicr/readonly_config.toml`](../../../../home/dot_config/tuicr/readonly_config.toml) | `~/.config/tuicr/config.toml` |

The config defines the review **comment types** (`issue`, `suggestion`, `question`, `nit`, `praise`) that tuicr exports as `[LABEL]` prefixes in the markdown an agent consumes.

These are actionable categories, not severity. Severity (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) stays internal per the `~/AGENTS.md` review SOP and is intentionally not encoded here, so tuicr labels and the review skill's severity model do not collide.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${OPENAI_API_KEY:+set}"
echo "${ANTHROPIC_API_KEY:+set}"
echo "${GEMINI_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../../security/security-and-secrets.md).
