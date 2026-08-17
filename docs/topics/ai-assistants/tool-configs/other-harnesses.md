---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

This page covers assistant-adjacent tools that do not have their own page in this section: Codex, OpenCode, Oh My Pi, GitHub Copilot CLI, and tuicr. It stays at the configuration and rendering layer; [Cross-harness subagents](../subagents.md) owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

Use it to answer three questions: which repo source owns the deployed config, which wrapper runs before the native binary, and which runtime-owned fields are allowed to survive a merge.

## Mental model

| Area                      | Current rule                                                                                        |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| Codex and OpenCode        | profile merging plus MCP injection                                                                  |
| Codex launcher            | interactive shells route `codex` through managed `~/bin/,codex`                                     |
| Copilot launcher wrappers | custom providers are BYOK environment variables only and wrapper commands `exec ,copilot`           |
| Local provider adapters   | per-wrapper loopback processes translate harness protocols while keeping upstream credentials local |
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

Both interactive profiles and every named Codex agent profile pin `model = "gpt-5.6-sol"`, `model_reasoning_effort = "xhigh"`, and `service_tier = "default"`.

### Codex reconciliation

Codex reconciliation rebuilds from the selected profile and generated MCP registry, then reattaches four explicitly runtime-owned buckets.

| Runtime-owned bucket           | Rule                                           |
| ------------------------------ | ---------------------------------------------- |
| MCP approval overrides         | valid values only                              |
| `[hooks.state.*].trusted_hash` | reattached                                     |
| `projects.*.trust_level`       | reattached when it is `trusted` or `untrusted` |
| `tui.model_availability_nux.*` | counters in `0..4294967295`                    |

All unrelated live tables and invalid values are discarded. Matching source tables remain authoritative. Hook trust hashes are not baked into `home/dot_codex/private_config.*.toml`.

### Provider wrappers

Other provider wrappers:

- `,codex-llama-cpp`
- `,codex-openrouter`
- `,opencode-llama-cpp`
- `,claude-openrouter`
- `,copilot-openrouter`

Copilot custom providers are BYOK environment variables only, so its wrappers set those variables for OpenAI-compatible endpoints. The provider wrappers `exec ,copilot` rather than `copilot` to keep one stable entry point.

The four OpenRouter wrappers read `OPENROUTER_API_KEY`, falling back to the `openrouter/api/token` pass entry when the environment is not already populated.

All OpenRouter entry points default to `deepseek/deepseek-v4-flash-0731` at `max` effort with FP8-or-higher quantization and a 24 t/s preferred floor. `sort` is omitted so OpenRouter's default load balancer keeps uptime, then price-weights remaining endpoints. Kimi remains selectable only on Fireworks, Together, and BaseTen under a $16/M completion cap (`only` blocks other providers), and `openai/gpt-5.6-terra` at `max` remains the Pi counter/verifier. Pi carries the model-specific provider objects as `modelOverrides.compat.openRouterRouting`; OMP 17.2.9, the wrappers, and OpenCode carry them through workspace preset slugs (OMP drops `extraBody.provider` from its typed openrouter wire, so it pins the same preset-slug ids).

Model and effort are selectable per launch. `--model <id>` and `--effort <level>` (aliases `--reasoning-effort`, `--thinking`; `--no-thinking` = minimal) compose the wire id as `<model>@preset/<slug>`, where the slug is `<family>-lanes-<level>` for the four known families (`kimi-lanes-*`, `deepseek-lanes-*`, `glm-lanes-*`, `terra-lanes-*`) and `effort-<level>` for any other model. Levels include `none` (disables reasoning via `reasoning.effort: "none"`) through `max`; each family has a matching `*-lanes-none` workspace preset, and unknown models use `effort-none`. Each preset bakes model, its provider policy, and effort; the default resolves to `deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max`. Some OpenRouter models reject `none` when reasoning is mandatory on their endpoint. The band-gate effort override stays at `high` because it only gates client-side thinking-block handling; the preset carries the provider-facing `max` effort. Route-pinning flags (`--base-url`, config, `--fallback-model`, `-c`) stay rejected. Inside an interactive session, `/model` accepts a free-text id passed verbatim to OpenRouter, so a preset-suffixed model keeps its provider policy while a bare model does not.

`,claude-openrouter` points `ANTHROPIC_BASE_URL` at `https://openrouter.ai/api` with no `/v1` suffix, because Claude's Anthropic SDK appends `/v1/messages`. It pins the root model, all family defaults, and `CLAUDE_CODE_SUBAGENT_MODEL` to the DeepSeek max preset; it also passes the client-side `--effort high` gate, sets `ANTHROPIC_AUTH_TOKEN`, and clears `ANTHROPIC_API_KEY`.

`,codex-openrouter` configures a per-invocation Responses provider (`model_providers.openrouter`, `wire_api="responses"`, `env_key="OPENROUTER_API_KEY"`) and pins `--model` to the preset-suffixed wire id. `model_reasoning_effort` is left unset so the preset is the single source of effort (a Codex body field would fight the preset). No loopback shim is involved: OpenRouter answers `/api/v1/responses` natively. Codex's `model_providers` schema is `deny_unknown_fields` with no extra-body channel, so `--model` and the band override carry DeepSeek's FP8-or-higher, 24 t/s floor, no-sort policy and max effort.

`,copilot-openrouter` uses the cache-capable `COPILOT_PROVIDER_TYPE=anthropic` client against `https://openrouter.ai/api` with no `/v1` suffix. The display model is DeepSeek, while `COPILOT_PROVIDER_WIRE_MODEL` and the band override carry the preset-suffixed wire id for the no-sort (uptime-aware) policy and max effort. Kimi presets restrict routing to Fireworks, Together, and BaseTen under the $16/M cap.

`,cursor-openrouter` launches the agent-cli-local flavor of Cursor's CLI: the regular `cursor-agent` build hard-rejects `--base-url`/`--local-agent-api-key` (`can only be used with agent-cli-local`), but Cursor publishes the sibling `agent-cli-local-package.tar.gz` per version in the same public S3 bucket. `~/lib/,cursor-agent-local/install.sh` installs it into `~/.local/share/cursor-agent-local/versions/<version>/` in lockstep with the installed cursor-agent (the chezmoi hook `run_onchange_after_05-install-cursor-agent-local` re-fires on version change, and the wrapper self-heals after a cursor-agent self-update). The wrapper exports `CURSOR_LOCAL_AGENT_BASE_URL` plus the key, and pins `--model` and the band override to the preset-suffixed wire id; the local provider config is baseUrl+apiKey only, so the provider policy and effort ride the preset slug (see the selectable-effort paragraph above). Fish `--effort` completions list that model's live `supported_efforts` and always add `none` (workspace `*-lanes-none` presets) when the catalog omits it.

Every `,cursor-openrouter` session runs through the loopback shim (`~/lib/,cursor-agent-shim/shim.py`), which enforces the session's model pin at the wire. The launcher exports the pinned wire id as `CURSOR_AGENT_ALLOWED_MODEL`, and the shim rejects any `/chat/completions` whose `model` differs with an HTTP 403 before the request reaches OpenRouter — so a subagent, `.cursor/agents/` profile (`model:`/`agent_model`), resumed session, or caller-supplied `Task.model` can never run a different (e.g. Claude-family) model on a pinned session, no matter what the client-side band gate or model resolver allowed. The shim also strips the `strict` flag from `openai/*` tool schemas: cursor-agent-local's reasoning-model predicate is `modelId.startsWith("o")`, so those ids get `strict:true` tool schemas, and OpenAI/Azure strict validation rejects the bundled Shell schema's optional `debounce_ms` (missing from `required`) with "Provider returned error" (live-probed 2026-08-09; both the shipped 2026.08.04 and the current lab build fail identically). DeepSeek/Kimi/GLM ids never matched the reasoning predicate, but they still pass through the allowlist; `--no-shim` is the explicit direct-OpenRouter opt-out and is only meaningful for a model with no preset family (no provider policy to carry), since it disables both the guardrail and the strict fix. The shim binds an ephemeral 127.0.0.1 port, inherits the real key (never in argv), announces `PORT=` through a ready file, and is killed by the wrapper's EXIT trap.

This matters because Copilot CLI's BYOK client only sets `enableCacheControl: true` and injects Anthropic `cache_control` breakpoints for `COPILOT_PROVIDER_TYPE=anthropic`. Its `openai`-type client builds the request with no cache-control flag at all, so prompt caching never activates there for an Anthropic model: a wire capture of the same Opus 5 session shows four `cache_control` blocks and a 72,458-token cache read on `/v1/messages`, against zero breakpoints and zero cached tokens on `/chat/completions`.

The client kind is fixed when the session starts. The OpenAI client has no cache-control support, so the wrapper does not permit it as a fallback.

Delegated lanes need their own pin. The Codex, Copilot, and Cursor wrappers export `AGENT_BAND_MODEL_OVERRIDE` (Codex and Copilot also `AGENT_BAND_EFFORT_OVERRIDE`), so [the band gate](../model-tiering.md) resolves every delegated agent to the DeepSeek max wire id. Copilot's live `task` schema accepts both `model` and `reasoning_effort`; the gate rewrites both. Claude Code applies the same pin through its root, family-default, and subagent environment variables.

### Repo-owned Codex subscription adapter

`,copilot-codex`, `,claude-codex`, and `,cursor-codex` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The child receives only a random per-launch loopback token. The adapter reads the existing Codex ChatGPT OAuth state from `${CODEX_HOME:-~/.codex}/auth.json`; it never copies the upstream access token into the Copilot, Claude, or Cursor environment.

| Wrapper          | Harness protocol        | Codex backend adaptation                                                                                                     |
| ---------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `,copilot-codex` | OpenAI Responses        | forces the backend's required SSE mode, relays streaming callers, and assembles `response.output_item.done` for JSON callers |
| `,claude-codex`  | Anthropic Messages      | translates messages, images, tools/tool results, structured output, usage, and streaming events to and from OpenAI Responses |
| `,cursor-codex`  | OpenAI Chat Completions | translates Chat Completions requests and SSE/JSON responses to and from OpenAI Responses                                     |

The adapter sends requests to the same ChatGPT Codex Responses backend used by the installed Codex CLI. It supports both Codex credential stores: legacy `${CODEX_HOME:-~/.codex}/auth.json` and current device authorization in the macOS Keychain, using Codex's account-key derivation and keeping the decoded bearer only in adapter memory. If the backend rejects the current bearer with `401`, the adapter asks `codex app-server` to run `account/read` with `refreshToken: true`, reloads the active store, and retries once. Other failures are not retried.

All three wrappers accept `--model <id>` / `-m <id>` and `--effort <level>` / `--reasoning-effort <level>`. An explicit wrapper value overrides the model or reasoning effort emitted by the harness. Without `--model`, the Codex wrappers read the top-level `model` from the active Codex `config.toml`; without `--effort`, they preserve the harness-generated effort. `,cursor-codex` Fish completions read every current model and its supported reasoning efforts from `~/.codex/models_cache.json`, rather than the policy-curated default list. It launches the version-matched `cursor-agent-local` binary with only `CURSOR_LOCAL_AGENT_BASE_URL=<loopback>/v1` and its random token. Forwarded Cursor `--base-url`, `--local-agent-api-key`, `--authless`, and model flags are rejected so they cannot bypass that boundary.

Both wrappers read the selected model's `max_context_window` from `${CODEX_HOME:-~/.codex}/models_cache.json`, falling back to `context_window`. For GPT-5.4, GPT-5.5, and GPT-5.6 family IDs, Copilot receives a `128000` output allowance and the remaining context through `COPILOT_PROVIDER_MAX_PROMPT_TOKENS`, so its combined budget equals the Codex context limit. Other model IDs receive the Codex context as their prompt limit and keep Copilot's native output default. Claude Code receives the context as the auto-compact window and adds Claude's `[1m]` frontend capability marker when the window exceeds Claude's default `200k`; the adapter still sends the original, unsuffixed model ID to Codex. If the model metadata is unavailable, each harness keeps its native default instead of guessing a larger window.

Claude token counting is a local byte-based estimate because the Codex backend does not expose an Anthropic token-count endpoint. Claude's required `max_tokens` field is not forwarded because the installed Codex request schema has no output-token-cap field. Opaque encrypted reasoning attached to a tool turn stays in bounded process memory only, keyed by the following tool call ID, so it can be restored on the tool-result turn without writing prompts or credentials to disk.

### Repo-owned Copilot subscription adapter

`,claude-copilot`, `,codex-copilot`, and `,cursor-copilot` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The adapter resolves the active GitHub credential with `gh auth token`, while the child receives only a random per-launch loopback token.

The adapter asks the installed Copilot CLI SDK for its entitlement-filtered live model catalog before launch and rejects unavailable models, models without a supported completion endpoint, unsupported effort values, or unsupported context tiers. Every Messages-, Responses-, or Chat-Completions-capable catalog model is selectable from either harness. `,claude-copilot` defaults to `claude-sonnet-5`; `,codex-copilot` and `,cursor-copilot` default to `gpt-5.3-codex` with `medium` effort. All accept `--model` / `-m`, `--effort` / `--reasoning-effort`, and `--context default|long_context`, with `--` separating colliding native harness flags. `,cursor-copilot` Fish completions cache that same entitlement-filtered catalog for 1 hour and narrow effort/context suggestions to the selected model. The Cursor wrapper uses the same version-matched local agent and pinned loopback settings as `,cursor-codex`; route and model override flags after `--` fail before the child starts.

Native Claude Code Messages traffic and native Codex Responses traffic remain pass-through. For a cross-protocol selection, the loopback reuses the repo's tested subscription translation modules: Messages ↔ Responses for Claude/GPT crossings, and either native harness protocol ↔ Chat Completions for models such as Gemini. Tool calls, tool results, streaming terminal events, effort, and provider-owned opaque tool context are translated with the conversation. Opaque context remains in bounded process memory for the lifetime of the adapter; the GitHub bearer remains confined to that process.

Without `--context`, both wrappers use Copilot's `default` tier. When the selected model advertises `long_context`, `--context long_context` uses the tier's catalogued prompt allowance plus the model's output allowance, capped by its maximum context window. Models without that tier fail before the child starts. This matches Copilot CLI's [`--context` contract](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).

Claude's selected Copilot context window becomes `CLAUDE_CODE_AUTO_COMPACT_WINDOW`. Windows above Claude's default `200k` also add Claude's `[1m]` frontend capability marker; the loopback strips that marker before sending the exact catalog model ID to Copilot. The loopback removes only Copilot-incompatible Anthropic beta values, currently Claude Code's `advisor-tool-2026-03-01`, while preserving the rest of a native Messages request. Codex receives a provider-owned `/v1/models` projection of the same live catalog so every translated model retains its prompt limit, reasoning levels, shell, and freeform patch tool metadata instead of falling back.

The GitHub bearer is added only on the adapter's upstream request together with Copilot's `copilot-developer-cli` integration ID. A `401` refreshes the value from `gh auth token` and retries once; other failures pass through without retry. Interactive interrupts propagate to the native harness, while adapter shutdown suppresses follow-up `SIGINT` delivery so cleanup does not emit a Python traceback.

### Repo-owned Vertex adapter

`,codex-vertex`, `,copilot-vertex`, and `,claude-vertex` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The adapter uses the configured Google Cloud project and refreshes `gcloud auth print-access-token` credentials behind the local protocol boundary; no Google bearer or project credential is written to generated config.

The three local frontends map to the two Vertex transports:

| Wrapper           | Local protocol          | Vertex transport                                                                   |
| ----------------- | ----------------------- | ---------------------------------------------------------------------------------- |
| `,codex-vertex`   | OpenAI Responses        | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |
| `,copilot-vertex` | OpenAI Chat Completions | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |
| `,claude-vertex`  | Anthropic Messages      | Gemini OpenAI Chat Completions or Claude publisher `rawPredict`/`streamRawPredict` |

The canonical `provider_models` entries in `home/.chezmoidata/ai_models/provider-routes.yaml` own the four allowed IDs, backend wire IDs, token limits, and effort matrix. `home/dot_config/vertex-adapter/readonly_models.json.tmpl` renders that data for the deployed core in `~/lib/,vertex-adapter/`. For Codex, the launcher also renders an owner-only, per-session `model_catalog_json` from the same registry and removes it on exit; the loopback `/v1/models` route exposes the equivalent Codex schema so these non-OpenAI IDs use their declared context, effort, shell, and freeform `apply_patch` metadata instead of fallback metadata.

All wrappers use `gemini-3.6-flash` unless `--model`/`-m` selects `gemini-3.1-pro-preview`, `claude-opus-4-6`, or `claude-opus-4-7`. `--thinking` enables the model's declared default, `--effort` selects a supported level, and `--no-thinking` is accepted only for the Claude models. Gemini 3.6 Flash's closest low-reasoning mode is `--effort minimal`; Gemini 3.1 Pro cannot disable thinking.

Streaming text and parallel function/custom tools are translated incrementally. Gemini tool-call thought signatures and Claude signed thinking blocks that cannot cross another protocol directly are stored by call ID in owner-only runtime state under `${XDG_STATE_HOME:-~/.local/state}/vertex-adapter/`; no user prompts, credentials, or general conversation transcript are added to that store.

Cursor is intentionally absent: Cursor Agent has no custom model-provider/base-URL route, so a `,cursor-vertex` command would not make Cursor use Vertex. Native `vlaude` also remains unchanged for direct Claude Code → Vertex Claude use.

### Codex hosted MCP token bridges

`inject_mcp_into_codex_toml.py` emits `slack` and `scsi-main` as `,mcp-token <source> --bridge --url <url>` command servers, not inline secrets or env-var contracts.

The bridge injects a freshly selected bearer per request, rotating through cursor's refresh grant behind the seam, so a Codex session outlives any single token.

## Oh My Pi

| Surface       | Source                                                                                                                   | Target                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------- |
| Agent config  | [`home/dot_omp/private_agent/readonly_config.yml.tmpl`](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl) | `~/.omp/agent/config.yml`  |
| MCP servers   | `mcp_servers.yaml` via `generate_mcp_configs.py omp`                                                                     | `~/.omp/agent/mcp.json`    |
| Shared skills | `symlink_skills` → `~/.agents/skills`                                                                                    | `~/.omp/agent/skills`      |
| Runtime hooks | `extensions/`                                                                                                            | `~/.omp/agent/extensions/` |
| Install       | [`home/readonly_dot_default-yarn-pkgs`](../../../../home/readonly_dot_default-yarn-pkgs) `@oh-my-pi/pi-coding-agent`     | yarn global, unpinned      |

### Managed configuration

`readonly_config.yml.tmpl` is the complete declarative OMP contract. Work routes primary roles through OpenRouter DeepSeek max and keeps `vision` on Kimi high; personal pins primary roles to Cursor `cursor-grok-4.6-xhigh`, uses `composer-2.5` for `smol`, and uses Cursor Grok for `vision`. `omp config list --json` reports the effective typed settings; inspect all model-role pins together with `omp config get modelRoles`, not with dotted child keys. A second file, `readonly_models.yml` (`~/.omp/agent/models.yml`), declares the OpenRouter models as preset-slug ids (OMP's typed transport drops `modelOverrides…compat.extraBody.provider` from the wire): `deepseek/deepseek-v4-flash-0731@preset/deepseek-lanes-max` (FP8-or-higher quantization, 24 t/s floor, no `sort` so default load balancing keeps uptime), `z-ai/glm-5.2@preset/glm-lanes-max` (same FP8-or-higher, 24 t/s floor policy), and `moonshotai/kimi-k3@preset/kimi-lanes` (Fireworks/Together/BaseTen-only under the $16/M cap), with `auth: none` so the env `OPENROUTER_API_KEY` still authorizes (see [Model registry & routing](../model-registry.md#openrouter-routing)).

| Setting                                                                                | Work value                                                    | Personal value                                                |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| `modelRoles.default`                                                                   | `openrouter/deepseek/deepseek-v4-flash-0731:max`              | `cursor/cursor-grok-4.6-xhigh`                                |
| `modelRoles.smol`                                                                      | `openrouter/deepseek/deepseek-v4-flash-0731:max`              | `cursor/composer-2.5:high`                                    |
| `modelRoles.vision`                                                                    | `openrouter/moonshotai/kimi-k3:high`                          | `cursor/cursor-grok-4.6-xhigh`                                |
| `modelRoles.slow`, `modelRoles.plan`                                                   | `openrouter/deepseek/deepseek-v4-flash-0731:max`              | `cursor/cursor-grok-4.6-xhigh`                                |
| `modelRoles.task`                                                                      | `openrouter/deepseek/deepseek-v4-flash-0731:max`              | `cursor/cursor-grok-4.6-xhigh`                                |
| `modelRoles.advisor`                                                                   | `openrouter/deepseek/deepseek-v4-flash-0731:max`              | `cursor/cursor-grok-4.6-xhigh`                                |
| `modelProviderOrder`                                                                   | `openrouter`, `cursor`, `openai-codex`, `anthropic`, `openai` | `cursor`, `openai-codex`, `openrouter`, `anthropic`, `openai` |
| `advisor.enabled`                                                                      | `true` (subagents true, syncBacklog 1, immuneTurns 0)         | `true` (subagents true, syncBacklog 1, immuneTurns 0)         |
| `defaultThinkingLevel`                                                                 | `high`                                                        | `high`                                                        |
| `memory.backend`                                                                       | `off`                                                         | `off`                                                         |
| `autolearn.enabled`, `autolearn.autoContinue`                                          | `false`, `false`                                              | `false`, `false`                                              |
| `dev.autoqaConsent`                                                                    | `granted`                                                     | `granted`                                                     |
| `skills.enabled`, `skills.enableSkillCommands`                                         | `true`, `true`                                                | `true`, `true`                                                |
| `task.isolation.mode`, `task.enableEffort`, `task.enableLsp`, `task.maxRecursionDepth` | `auto`, `true`, `true`, `2`                                   | `auto`, `true`, `true`, `2`                                   |
| `retry.enabled`, `retry.maxRetries`                                                    | `true`, `5`                                                   | `true`, `5`                                                   |
| `symbolPreset`, `theme.dark`, `setupVersion`                                           | `nerd`, `titanium`, `1`                                       | `nerd`, `titanium`, `1`                                       |
| `providers.webSearchOrder`                                                             | `codex`, `gemini`, `google`, `duckduckgo`                     | `codex`, then keyless scrapers in OMP built-in order          |
| `providers.webSearchExclude`                                                           | every other OMP search id, including `perplexity`             | every keyed search id, including `perplexity` and `gemini`    |

`modelRoles` is also what prices OMP's bands: repo-managed agent profiles carry `@role` tokens (`@smol`, `@task`, `@default`, `@advisor`) that `model_bands.omp` names, so the work and personal role tables above decide what each band costs. See [Model tiering](../model-tiering.md).

The OMP advisor is enabled for primary turns and spawned agents. It uses the configured `modelRoles.advisor` model to inject actionable notes as `<advisory>` context. `syncBacklog: 1` pauses the primary for up to 30 seconds at every pending advisor review, waiting for the backlog to clear before continuing. `immuneTurns: 0` keeps every later `concern` or `blocker` eligible for steering instead of downgrading it to a non-interrupting aside. These settings make advisor recommendations reach the primary promptly; OMP still marks them as `guidance="weigh, don't blindly obey"`, so it does not mechanically enforce compliance.

AutoQA consent is source-managed as `granted`, so OMP records and uploads concise `xd://report_issue` tool-grievance reports without prompting again.

`web_search` is profile-specific. Work walks Codex, then Gemini, then Google scrape, then DuckDuckGo. Personal walks Codex, then every keyless scraper in OMP's built-in relative order (`startpage`, `duckduckgo`, `ecosia`, `google`, `mojeek`, `public`). Listing `perplexity` is an explicit selection that calls OpenRouter `perplexity/sonar-pro` when an OpenRouter key is set, so both profiles exclude it. Unlisted providers stay in the fallback chain, so `providers.webSearchExclude` drops every id not in that profile's order. Bash `ddgr --noua` remains the SOP fallback if the tool fails.

OMP receives a native `mcp.json` generated from the shared registry. `scsi-main` and `slack` run as `,mcp-token --bridge` stdio servers, so fresh cursor-minted bearer tokens are injected per request; `scsi-local` remains a direct stdio server.

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
