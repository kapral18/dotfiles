---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

This page covers assistant-adjacent tools that do not have their own page in this section: Codex, OpenCode, GitHub Copilot CLI, and tuicr. It stays at the configuration and rendering layer; [Cross-harness subagents](../subagents.md) owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

Use it to answer three questions: which repo source owns the deployed config, which wrapper runs before the native binary, and which runtime-owned fields are allowed to survive a merge.

## Mental model

| Area                      | Current rule                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------- |
| Codex and OpenCode        | profile merging plus MCP injection                                                                |
| Codex launcher            | interactive shells route `codex` through managed `~/bin/,codex`                                   |
| Copilot launcher wrappers | custom providers are BYOK environment variables only and wrapper commands `exec ,copilot`         |
| Copilot MCP               | generated as stdio `type: "local"`, OAuth HTTP, or header-auth HTTP depending on the server block |
| Copilot memory            | native SDK extension supplies context and worklog hooks                                           |
| tuicr                     | single-sourced readonly review TUI config; labels are categories, not severity                    |
| secrets                   | runtime API keys come from `pass`, not committed tool config files                                |

## Codex and OpenCode

### Config sources

| Tool     | Config source                                                        |
| -------- | -------------------------------------------------------------------- |
| Codex    | [`home/dot_codex/`](../../../../home/dot_codex/)                     |
| OpenCode | [`home/dot_config/opencode/`](../../../../home/dot_config/opencode/) |

Codex and OpenCode use profile merging with MCP injection.

The interactive `codex` command routes through the managed `~/bin/,codex` shim in interactive shells. The shim captures Codex bearer-token MCP env vars for hosted work servers, starts any due proactive rotations after capture, injects the local llama.cpp model catalog when needed, and then falls through to the real Codex binary.

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

Copilot custom providers are BYOK environment variables only, so its wrappers set those variables for OpenAI-compatible endpoints. The provider wrappers `exec ,copilot` rather than `copilot`, so the header-auth MCP token refresh below runs before the custom upstream starts.

`,copilot-litellm` uses `LITELLM_API_BASE` / `LITELLM_PROXY_KEY`, falling back to the `litellm/api/base` and `litellm/api/token` pass entries when the environment is not already populated.

Select a LiteLLM model with `,copilot-litellm <llm-gateway/model>` or `,copilot-litellm --model <llm-gateway/model>`. The wrapper keeps the gateway slug as Copilot's wire model and maps known slugs such as `llm-gateway/claude-opus-4-7` to Copilot's internal `claude-opus-4.7` spelling for model metadata.

`,copilot-openrouter` routes `anthropic/*` and `~anthropic/*` models through `COPILOT_PROVIDER_TYPE=anthropic` against `https://openrouter.ai/api` with no `/v1` suffix. It does this instead of the default `openai`-type client against `https://openrouter.ai/api/v1`.

This matters because Copilot CLI's BYOK client only sets `enableCacheControl: true` and injects Anthropic `cache_control` breakpoints for `COPILOT_PROVIDER_TYPE=anthropic`. The default `openai`-type client always sends `enableCacheControl: false`, so prompt caching never activates for it regardless of what the upstream model supports.

Every other OpenRouter model, including GLM, DeepSeek, Qwen, Kimi, GPT, and Gemini, still uses the `openai`-type client. OpenRouter's public model-endpoints API currently reports `supports_implicit_caching: false` for all providers, so there is no caching benefit to gain there.

Setting `COPILOT_PROVIDER_TYPE` explicitly before invoking the wrapper always overrides this auto-detection.

### Claude Code and Cloudflare

Claude Code is not wired to Cloudflare.

Reason:

- Claude's Anthropic-compatible custom base URL path sends `x-api-key` for `ANTHROPIC_API_KEY`.
- Cloudflare's `/ai/v1/messages` endpoint requires `Authorization: Bearer ...`.
- the `ANTHROPIC_AUTH_TOKEN` path did not issue a request in the local probe.

So there is intentionally no `,claude-cloudflare` wrapper.

### Codex hosted MCP bearer-token env vars

`inject_mcp_into_codex_toml.py` emits `slack` and `scsi-main` as streamable HTTP servers with `bearer_token_env_var`, not inline secrets.

The `,codex` wrapper reads those declarations from `~/.codex/config.toml`, captures each token through `,mcp-token <server> --login --quiet --launch-json`, exports the raw token into the configured env var, starts due proactive rotations after capture, and exits before launch if a valid token cannot be obtained.

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

| Server shape             | Generated form                                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| stdio servers            | `type: "local"`                                                                                               |
| OAuth HTTP servers       | `type: "http"` with `oauthClientId` + `auth.redirectPort` + `oauthScopes`                                     |
| header-auth HTTP servers | `type: "http"` with `headers.Authorization`; OAuth keys skipped when the `copilot` block carries `headerAuth` |

Copilot cannot run the SCSI/Slack browser OAuth flows itself. It hardcodes its OAuth redirect to `http://127.0.0.1:{port}/`, where only the port is configurable, which neither the SCSI Okta app nor the public Slack client registers.

Slack's MCP authorization server offers no dynamic client registration and requires a client secret at the token endpoint. Both `scsi-main` and `slack` therefore give their `copilot` block a `headerAuth: "$(,mcp-token <server> --bearer)"`, and Copilot reaches each with a bearer token minted by cursor-cli; both servers accept header bearer auth.

If the cursor cache is stale during `chezmoi apply`, the generator emits a refresh placeholder for that header instead of failing the apply. The `,copilot` wrapper obtains a typed header-auth plan from the registry, deduplicates token sources, captures each source once with `--login --quiet --launch-json`, and passes the in-memory values to one render before launch.

If no valid token is returned, render fails, or a placeholder remains, the wrapper exits before starting Copilot. Direct `,mcp-token --login` still guarantees runway, not just validity.

Managed launchers use `--launch-json` so a still-valid token short of the min-TTL floor can be captured immediately and proactively rotated with detached `--rotate` only after the fixed header or env value is ready. The final blocking window, expired tokens, and revoked tokens still rotate synchronously by invalidating the access token in the newest cursor project cache holding a `refresh_token` and running a bounded `cursor-agent mcp list-tools <server>` in that cache's trusted workspace.

Cursor then executes the provider's refresh grant and writes a freshly minted chain in place, with no browser, and in-flight tokens of running sessions stay live. Concurrent deferred workers serialize through `~/.cache/mcp-token/rotation.lock` and recheck whether rotation is still due before touching the shared cursor cache.

For opaque tokens such as Slack, ledger state and cursor cache mtime cannot prove the token is still live because the provider can revoke it while the ledger still lists it as fresh. Launch capture validates the ledger-selected opaque token with a minimal MCP `initialize` probe against the server URL from `~/.cursor/mcp.json`, adopts a live cached alternative when rotation is unavailable and the ledger token is revoked, and only runs the cursor browser flow when no live candidate exists, confirming the post-login token by the same probe.

SCSI JWTs use their `exp`.

Before launch, `,copilot` holds a private config lock, asks `generate_mcp_configs.py` for the canonical plan, captures each unique source, sends the Authorization values to a single generator render over stdin, verifies exact headers and no placeholders, and atomically writes only a semantic change.

It then starts due proactive rotations and execs Copilot. A changed target records the existing `copilot-mcp` row in `generated_artifacts.v1.json`; a no-op leaves both target and ledger inode/mtime unchanged, and an artifact-recording failure rolls the target back before Copilot can start.

The token-bearing `~/.copilot/mcp-config.json` is written `0600` under a `0700` `~/.copilot/` directory.

`scsi-local` has no OAuth, so it is emitted as a `type: "local"` server with local stdio and `pass` Elasticsearch credentials. Copilot's generated `mcp-config.json` therefore carries `scsi-main`, `scsi-local`, and `slack` plus its built-in servers. The built-in `github-mcp-server` is provided by Copilot and is not emitted. See [MCP servers](../mcp.md).

### Copilot settings reconciliation

Copilot owns `~/.copilot/settings.json` and rewrites it at runtime, including chosen `model`, `allowedUrls`, and `config.json` migration.

The typed reconciler recursively preserves live keys absent from the baseline and lets declared values win. It replaces `subagents.agents` exactly with the seven declared agents, which removes stale agent names and persisted per-agent model/effort/context overrides while preserving unrelated runtime preferences.

The target is in `.chezmoiignore`.

### Copilot agent memory

Copilot 1.0.68 runs JSON command hooks from `~/.copilot/hooks/*.json`, but live probes showed their `SessionStart` stdout is not ingested as context.

The active context path is the `agent-memory` extension. It registers `onSessionStart`, `onPostToolUse`, and `onPostToolUseFailure`, translates Copilot's camelCase SDK payloads to the shared snake_case script contract, and returns SDK `additionalContext`.

Command-hook files are cleaned up by the apply hook along with their exact generated-config ledger row. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

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
