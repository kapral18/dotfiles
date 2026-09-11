---
sidebar_position: 5
title: Other harnesses
---

# Other harnesses

This page covers assistant-adjacent tools that do not have their own page in this section: Codex, OpenCode, Oh My Pi, GitHub Copilot CLI, Crush, tuicr, and lgtm. It stays at the configuration and rendering layer; [Cross-harness subagents](../subagents.md) owns runtime discovery, review fan-out hierarchy, source paths, and design notes.

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
| lgtm                      | single-sourced readonly live diff reviewer config; comments/snapshots stay repo-local               |
| Crush                     | static `crushrc` injects the home SOP as a global context path                                      |
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

Both profiles set `tui.auto_recap = false` to disable automatic conversation recaps. Manual `/recap` remains available: the [official schema](https://learn.chatgpt.com/docs/config-schema.json) states, “Disabling this leaves `/recap` available on demand.”

Both profiles show the model with reasoning effort, current directory, and remaining context in `tui.status_line`. The removed `features.js_repl` option is no longer configured.

| Profile              | Policy                                                                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| work interactive     | managed-device requirements with `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, and `sandbox_mode = "workspace-write"`; approval requests use automatic review |
| personal interactive | `approval_policy = "never"` with `sandbox_mode = "danger-full-access"`                                                                                                                  |
| child role profiles  | inherit parent permissions; disable `features.multi_agent`                                                                                                                              |

The work profile declares the following `sandbox_workspace_write.writable_roots` for AI runtime storage and chezmoi deployment. The exceptions also apply to sandboxed subprocesses when Codex works in another repository.

| Purpose                                 | Writable directories                                       |
| --------------------------------------- | ---------------------------------------------------------- |
| Source and durable memory               | `~/.local/share/chezmoi`, `~/.local/share/ai-kb`           |
| Topic backups and proof receipts        | `~/.local/state/agent-specs`, `~/.local/state/agent-proof` |
| Generated-config ledger                 | `~/.local/state/chezmoi`                                   |
| Embedding runtime and artifacts         | `~/.cache/ai-embed-runtime`, `~/.cache/agent-artifacts`    |
| MCP token rotation                      | `~/.cache/mcp-token`                                       |
| Local model-server lifecycle            | `~/.local/state/llama-cpp/lifecycle`                       |
| Deployed commands and libraries         | `~/bin`, `~/lib`                                           |
| Shared agents and harness configuration | `~/.agents`, `~/.codex`, `~/.claude`                       |

Workspace sandboxing and approval settings remain in effect. These exceptions grant directory write access; they do not cover every target of a full `chezmoi apply`. Other deployment paths still require approval. New sessions load the updated roots.

Repeated exact-command approvals can be captured by Codex execpolicy `*.rules` files under `~/.codex/rules/`. Those rules should stay narrow because explicit allow rules also bypass sandboxing for the matched command prefix.

Repeated MCP tool approvals live as `mcp_servers.<server>.tools.<tool>.approval_mode = "approve"` in `~/.codex/config.toml`. The Codex merge hook preserves those runtime-written approval overrides when it regenerates the managed MCP blocks.

`scsi-main` and `scsi-local` are generated with `default_tools_approval_mode = "approve"` so their read-analysis tools do not depend on the flaky MCP approval persistence path. Slack is only auto-approved for read/search tools (`slack_read_*` and `slack_search_*`), while send/create/update/schedule tools stay prompted/auto-reviewed.

Both interactive profiles default to `gpt-6-astra` with `model_reasoning_effort = "high"`, matching the approved live root model and registry orchestration category. Orchestration-bound roles, including native `default`, follow that selection. Other categories are unchanged: research stays `gpt-5.6-sol`/high; named review and verifier agents run `gpt-6-astra`/high; `k-agent-smol` and `k-agent-mechanical` use `gpt-5.6-terra`/high, and implement workers ride the same terra pick. Every profile pins `service_tier = "default"`.

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

The four OpenRouter wrappers read `OPENROUTER_API_KEY`; Claude, Codex, and Cursor fall back to the active password store's `openrouter/api/token` entry when the environment is not already populated, while Copilot requires the environment variable. Before launching, each wrapper checks the active account for its `effort-<level>` preset. A missing preset is created in that account with only `reasoning.effort`; an existing preset is used unchanged. No account discovery or cross-account synchronization occurs.

Before entering the native harness, all four OpenRouter wrappers clear inherited `AGENT_BAND_SUBSCRIPTION`, `AGENT_BAND_CLAUDE_ROUTES`, and `AGENT_BAND_CODEX_ROUTES` along with model/effort overrides. The new Pi/OpenRouter selection therefore does not reuse a parent's subscription projection. Claude and Codex then install fresh role-to-wire maps for their own managed leaf profiles. Leaf identity and orchestration restrictions remain untouched.

The four `*-openrouter` wrappers default the root session to `z-ai/glm-5.3-flash` at `high` and compose `<model>@preset/effort-<level>`. Delegated lanes inherit Pi's OpenRouter-compatible matrix through `AGENT_BAND_SCHEMA_HARNESS=pi` plus `AGENT_BAND_MODEL_FORMAT=openrouter-preset`, so each Pi category row becomes `<model>@preset/effort-<level>`: Fable 5.1 high for the T1 primary lanes, GPT-5.6 SOL high for T2 implement, GLM 5.3 Flash high for mechanical, Gemini 3.8 Flash low for memory, and GPT-5.6 SOL xhigh for refute (the same model as T2 implement at a higher effort, since GPT-5.6 SOL superseded GPT-5.5 on 2026-09-07). `,claude-openrouter` projects managed native agent definitions with each exact backend selector, including the distinct refute effort; it no longer squeezes those pairs into the call schema's finite alias slots. Provider policy stays model-specific: Pi sends `modelOverrides.compat.openRouterRouting` for Kimi, GLM-5.2, and the `z-ai/glm-5.3-flash` route; OMP 17.2.9 and OpenCode carry the shared Kimi/GLM policies through workspace `*-lanes-*` preset slugs (the request model overrides the preset's pinned GLM-5.2 id, so GLM 5.3 Flash rides `glm-lanes-max`) (OMP drops `extraBody.provider` from its typed openrouter wire, so it pins the same preset-slug ids). Those policies keep FP8-or-higher plus a 24 t/s preferred floor on GLM, Fireworks/Together/BaseTen-only Kimi under a $16/M completion cap, and no `sort`, so OpenRouter's default load balancer keeps uptime.

Model and effort are selectable per launch. `--model <id>` and `--effort <level>` (aliases `--reasoning-effort`, `--thinking`; `--no-thinking` = minimal) compose `<model>@preset/effort-<level>` for every root model. Levels include `none` (disables reasoning via `reasoning.effort: "none"`) through `max`. The default resolves to `z-ai/glm-5.3-flash@preset/effort-high`; delegated lanes use the Pi matrix's preset wire ids. All four wrappers accept `--context short|long` and default to `short`. The shared helper resolves paired context/output limits from the live catalog; the prompt budget reserves output space, and `short` stays below the first pricing transition when one exists. Claude and Copilot use the smallest budget across the root and reachable delegated models because their overrides apply to the whole session. Codex receives a temporary per-model startup catalog; Cursor receives per-model `/models` capabilities through its loopback shim. Claude sets both its custom-model maximum and auto-compaction window without changing the OpenRouter wire id. Inherited context overrides cannot enlarge the resolved budget. Some OpenRouter models reject `none` when reasoning is mandatory on their endpoint. Route-pinning flags (`--base-url`, config, `--fallback-model`, `-c`) stay rejected. Inside an interactive session, `/model` accepts a free-text id passed verbatim to OpenRouter, so a typed `model@preset/effort-<level>` keeps the effort slug while a bare model does not.

Fish `--model`/`--effort` completions for `,claude-openrouter`, `,codex-openrouter`, `,copilot-openrouter`, and `,cursor-openrouter` share `~/.config/fish/functions/__openrouter_catalog.fish` (cache `~/.cache/,openrouter/models.tsv`). The catalog is `GET /api/v1/models?supported_parameters=reasoning`. A model stays listed when `reasoning.supported_efforts` is missing (live: `inclusionai/ling-3.0-flash`). `--effort` lists that model's live efforts and always adds `none` (workspace `effort-none`); an empty efforts cell uses the full ladder. `,image-openrouter` keeps its own static ZDR image set.

`,claude-openrouter` points `ANTHROPIC_BASE_URL` at `https://openrouter.ai/api` with no `/v1` suffix, because Claude's Anthropic SDK appends `/v1/messages`. It keeps the root model on the selected OpenRouter wire id. `~/lib/shared/claude_lanes.py` reads the managed Claude profiles and Pi category projection, then supplies native `--agents` definitions with exact backend model/effort selectors. The profile body and skill preloads remain unchanged; explicit tools retain their original restrictions and exclude `Agent`, `Task`, and `SendMessage`. The `readonly` frontmatter annotation is not a native permission control; it is not converted into an invented permission mode. The gate requires the fresh role-to-wire map and removes call-level model overrides so the projected definition wins. Missing or stale roles, conflicting controls, and resume/fork requests are denied. `CLAUDE_CODE_SUBAGENT_MODEL` is cleared. The wrapper passes the selected effort through Claude's client gate when Claude supports that level (`low` through `max`). OpenRouter `none`/`minimal` presets use Claude's `low` client gate while the model preset carries the real effort. For context, it keeps the model id bare and sets `CLAUDE_CODE_MAX_CONTEXT_TOKENS` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW` from the resolved session budget. The wrapper sets `ANTHROPIC_AUTH_TOKEN` and clears `ANTHROPIC_API_KEY`.

`,codex-openrouter` configures a per-invocation Responses provider (`model_providers.openrouter`, `wire_api="responses"`, `env_key="OPENROUTER_API_KEY"`) and pins `--model` to `<model>@preset/effort-<level>`. `model_reasoning_effort` is left unset so the preset is the single source of effort (a Codex body field would fight the preset). No loopback shim is involved: OpenRouter answers `/api/v1/responses` natively. Its startup catalog retains each exact `@preset/effort-<level>` selector, including different efforts for the same base model. The shared `~/lib/shared/codex_lanes.py` projects model-free managed leaf profiles for both this route and `,codex-copilot`; their instructions and native no-nesting feature remain intact. The gate requires the fresh role/pair map and denies missing or stale projections, forks, conflicting controls, and child-originated spawns. Native role defaults can no longer replace an admitted OpenRouter selector. After exact-pair admission, the hook omits the redundant native reasoning field: effort stays in the preset selector, and the catalog does not claim unsupported native reasoning levels.

`,copilot-openrouter` uses the cache-capable `COPILOT_PROVIDER_TYPE=anthropic` client against `https://openrouter.ai/api` with no `/v1` suffix. The display model is the selected OpenRouter id, while `COPILOT_PROVIDER_WIRE_MODEL` carries the root `<model>@preset/effort-<level>` id and delegated lanes are rewritten from Pi category rows to preset wire ids. `COPILOT_PROVIDER_MAX_PROMPT_TOKENS` and `COPILOT_PROVIDER_MAX_OUTPUT_TOKENS` use separate resolved limits. Explicit OpenRouter budget overrides must fit the selected tier and provider capacity.

`,cursor-openrouter` launches the agent-cli-local flavor of Cursor's CLI: the regular `cursor-agent` build hard-rejects `--base-url`/`--local-agent-api-key` (`can only be used with agent-cli-local`), but Cursor publishes the sibling `agent-cli-local-package.tar.gz` per version in the same public S3 bucket. `~/lib/,cursor-agent-local/install.sh` installs it into `~/.local/share/cursor-agent-local/versions/<version>/` in lockstep with the installed cursor-agent (the chezmoi hook `run_onchange_after_05-install-cursor-agent-local` re-fires on version change, and the wrapper self-heals after a cursor-agent self-update). The wrapper exports `CURSOR_LOCAL_AGENT_BASE_URL` plus the key, pins root `--model` to `<model>@preset/effort-<level>`, and lets delegated lanes inherit Pi's OpenRouter preset wire ids. Fish `--model`/`--effort` completions use the shared OpenRouter catalog above.

Every `,cursor-openrouter` session runs through the loopback shim (`~/lib/,cursor-agent-shim/shim.py`), which enforces the allowed model set at the wire. The launcher exports a comma-separated `CURSOR_AGENT_ALLOWED_MODEL` containing the selected root wire id plus Pi's lane wire ids, and the shim rejects any `/chat/completions` whose `model` is outside that set with an HTTP 403 before the request reaches OpenRouter. A subagent, `.cursor/agents/` profile (`model:`/`agent_model`), resumed session, or caller-supplied `Task.model` can run only the root pin or one of the backend schema lane ids, no matter what the client-side band gate or model resolver allowed. Its `/models` response supplies each allowed wire model's resolved prompt and output capabilities to Cursor's local-provider consumer. The shim also strips the `strict` flag from `openai/*` tool schemas: cursor-agent-local's reasoning-model predicate is `modelId.startsWith("o")`, so those ids get `strict:true` tool schemas, and OpenAI/Azure strict validation rejects the bundled Shell schema's optional `debounce_ms` (missing from `required`) with "Provider returned error" (live-probed 2026-08-09; both the shipped 2026.08.04 and the current lab build fail identically). On the way back, it rewrites inbound `Bash` tool calls to `Shell` so Claude-trained OpenRouter models (live: `inclusionai/ling-3.0-flash`) do not trip `AI_NoSuchToolError` and the TUI reconnect loop; Shell already accepts Claude Bash's `command`/`timeout`/`description`, and outbound tool lists stay Cursor-native. Some models, first observed with `stealth/ox-alpha`, hang or return an empty success response when Cursor's OpenAI chat-completions request includes tool schemas. The explicit known-model adapter still strips tools for those named models. An empty or refusal response does not establish tool incapability: the shim returns it without another inference request, retains tools on later requests, and never learns a no-tools downgrade from the response. DeepSeek/Kimi/GLM ids never matched the reasoning predicate, but they still pass through the allowlist and the inbound rewrite; `--no-shim` is the explicit direct-OpenRouter opt-out and disables the guardrail, the strict fix, the explicit known-model no-tools adapter, the inbound rewrite, and wrapper-provided context metadata. Explicit long context therefore requires the shim. The shim binds an ephemeral 127.0.0.1 port, inherits the real key (never in argv), announces `PORT=` through a ready file, and is killed by the wrapper's EXIT trap.

This matters because Copilot CLI's BYOK client only sets `enableCacheControl: true` and injects Anthropic `cache_control` breakpoints for `COPILOT_PROVIDER_TYPE=anthropic`. Its `openai`-type client builds the request with no cache-control flag at all, so prompt caching never activates there for an Anthropic model: a wire capture of the same Opus 5 session shows four `cache_control` blocks and a 72,458-token cache read on `/v1/messages`, against zero breakpoints and zero cached tokens on `/chat/completions`.

The client kind is fixed when the session starts. The OpenAI client has no cache-control support, so the wrapper does not permit it as a fallback.

Delegated lanes need their own backend schema. The Codex, Copilot, Cursor, and Claude OpenRouter wrappers export `AGENT_BAND_SCHEMA_HARNESS=pi` and `AGENT_BAND_MODEL_FORMAT=openrouter-preset`, so [the band gate](../model-tiering.md) resolves every bound delegated agent through Pi's OpenRouter category matrix and converts the result to the wrapper's preset wire format. Copilot's live `task` schema accepts both `model` and `reasoning_effort`; the gate rewrites both. Claude Code applies the same backend schema through alias defaults because its Agent tool accepts family aliases, not arbitrary OpenRouter ids.

OpenCode's custom OpenRouter preset IDs declare context and output limits explicitly because they do not inherit metadata from the bare model ID. Pi's GLM-5.2 override and OMP's custom entries stay within the routed provider's capacity; existing smaller output allowances remain in place.

### Cross-backend capability limits

A shared adapter is not evidence of equal native frontend behavior or provider cache hits. This inventory separates configured mechanisms from remaining verification and policy gaps.

| Wrappers                                                                            | Delegation mechanism / gap                                                                                                              | Cache and context boundary                                                                                           |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `,codex-copilot`                                                                    | Fresh exact-pair projected native leaves; prior scripted transport proof, not arbitrary live refuter completion                         | Shared translation fixes; bounded Opus/high tool-continuation cache hit observed separately                          |
| `,claude-copilot`, `,claude-codex`                                                  | Exact managed Claude profiles; unavailable pairs denied                                                                                 | Session-wide minimum context budget; protocol-specific controls/accounting                                           |
| `,copilot-codex`                                                                    | Delegation runs, but a child tag cannot reach it: `~/.copilot/settings.json` supplies the subagent model after the hook rewrite         | Root adapter usable; this does not prove child caching                                                               |
| `,cursor-copilot`, `,cursor-codex`                                                  | Child-tag transport remains unverified and disabled                                                                                     | Root adapters remain usable; this does not prove child caching                                                       |
| `,codex-openrouter`                                                                 | Exact preset catalog plus session-projected managed leaves                                                                              | Per-model prompt budgets; provider owns cache acceptance/hits                                                        |
| `,claude-openrouter`                                                                | Exact managed profiles carry all configured pairs, including refute xhigh                                                               | Session-minimum budgets; no substitute effort allowed                                                                |
| `,copilot-openrouter`                                                               | Pi lane rewrite exists; complete native child lifecycle is not certified here                                                           | Anthropic client supplies cache controls; hits remain provider-dependent                                             |
| `,cursor-openrouter`                                                                | Pi wire allowlist exists; current native custom-selector child transport is not certified here                                          | Per-model catalog; no inferred no-tools retry/downgrade                                                              |
| `,claude-llama-cpp`, `,codex-llama-cpp`, `,cursor-llama-cpp`, `,opencode-llama-cpp` | No approved local category matrix; native hosted profile defaults or Cursor's root override are not a capability-equivalent lane policy | Local KV cache is distinct from hosted prompt-cache billing; existing local budgets are not child-lane certification |

A scripted local-provider check with Copilot CLI `1.0.83` preserved an exact child selector on its Anthropic BYOK path, but the child still exposed `task`. This is not proof of the Responses subscription path or native no-nesting. On that Responses subscription path the hook's per-call `model` rewrite is not what the child runs: a probe on 2026-09-11 injected `gpt-5.6-sol@lane-medium` through the band hook and the child request carried `claude-opus-5`, the `~/.copilot/settings.json` subagent model.
The adapter had also dropped every tool call on that path, because it relayed a terminal `response.completed` whose `output` array was empty; it now restores the streamed items, so `bash` and `task` run.
An isolated Cursor `2026.09.08-6caf4ff` check stopped at authentication before any loopback request; authenticated child behavior remains unverified. Codex `0.154.0` natively supports reopening closed agents, so removing child collaboration tools does not seal terminal results against root revival.

Full parity requires a verified child selector/effort path, native no-nesting and terminal behavior, an approved backend category policy, and route-specific runtime evidence. Do not enable a missing route by dropping its effort or calling the root model an equivalent worker.

### Repo-owned Codex subscription adapter

`,copilot-codex`, `,claude-codex`, and `,cursor-codex` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The child receives only a random per-launch loopback token. The adapter reads the existing Codex ChatGPT OAuth state from `${CODEX_HOME:-~/.codex}/auth.json`; it never copies the upstream access token into the Copilot, Claude, or Cursor environment.

| Wrapper          | Harness protocol        | Codex backend adaptation                                                                                                                                                                            |
| ---------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `,copilot-codex` | OpenAI Responses        | forces the backend's required SSE mode, relays streaming callers while restoring the terminal `response.output` from the streamed items, and assembles `response.output_item.done` for JSON callers |
| `,claude-codex`  | Anthropic Messages      | translates messages, images, tools/tool results, structured output, usage, and streaming events to and from OpenAI Responses                                                                        |
| `,cursor-codex`  | OpenAI Chat Completions | translates Chat Completions requests and SSE/JSON responses to and from OpenAI Responses                                                                                                            |

The adapter sends requests to the same ChatGPT Codex Responses backend used by the installed Codex CLI. It supports both Codex credential stores: legacy `${CODEX_HOME:-~/.codex}/auth.json` and current device authorization in the macOS Keychain, using Codex's account-key derivation and keeping the decoded bearer only in adapter memory. If the backend rejects the current bearer with `401`, the adapter asks `codex app-server` to run `account/read` with `refreshToken: true`, reloads the active store, and retries once. Other failures are not retried.

All three wrappers accept `--model <id>` / `-m <id>` and `--effort <level>` / `--reasoning-effort <level>`. An explicit wrapper value selects the root model or effort. Only explicit child-lane selectors choose the backend matrix's model and effort; raw model IDs retain root controls. Claude managed profiles carry those exact pairs. Copilot/Cursor subscription frontends cannot receive a child tag while their settings-level subagent model wins; see the [coverage limits](../subagents.md#coverage-inventory). Without `--model`, the Codex wrappers read the top-level `model` from the active Codex `config.toml`; without `--effort`, they preserve the harness-generated effort. `,cursor-codex` Fish completions read every current model and its supported reasoning efforts from `~/.codex/models_cache.json`, rather than the policy-curated default list. It launches the version-matched `cursor-agent-local` binary with only `CURSOR_LOCAL_AGENT_BASE_URL=<loopback>/v1` and its random token. Forwarded Cursor `--base-url`, `--local-agent-api-key`, `--authless`, and model flags are rejected so they cannot bypass that boundary.

All three wrappers resolve the selected model's active `context_window` from `${CODEX_HOME:-~/.codex}/models_cache.json`. `max_context_window` is the ceiling for an explicit Codex configuration override, not the default. The adapter applies Codex's effective-context percentage and compaction threshold separately. Copilot receives the usable prompt budget without a model-name-based output subtraction; the Codex backend does not expose an output-cap field, so Copilot keeps its native output default. Cursor receives the selected model's usable context through `/v1/models` capabilities. Claude uses a conservative global budget across the root and its reachable managed profiles, with a custom-model maximum for small models and a frontend `[1m]` marker where needed. Missing metadata requires an explicit configured context or a refreshed native Codex catalog instead of silently retaining an unrelated frontend default.

Claude token counting is a local byte-based estimate because the Codex backend does not expose an Anthropic token-count endpoint. Claude's required `max_tokens` field is not forwarded because the installed Codex request schema has no output-token-cap field. Chat callers retain an explicit `prompt_cache_key` through Responses translation; absent keys still use the existing client default. Unsupported retention/TTL controls are not synthesized. Opaque encrypted reasoning attached to a tool turn stays in bounded process memory only, keyed by the following tool call ID, so it can be restored on the tool-result turn without writing prompts or credentials to disk.

### Repo-owned Copilot subscription adapter

`,claude-copilot`, `,codex-copilot`, and `,cursor-copilot` start one authenticated adapter on a random `127.0.0.1` port and stop it with the harness. The adapter resolves the active GitHub credential with `gh auth token`, while the child receives only a random per-launch loopback token.

The adapter asks the installed Copilot CLI SDK for its entitlement-filtered live model catalog before launch and rejects unavailable models, models without a supported completion endpoint, unsupported effort values, or unsupported context tiers. Every Messages-, Responses-, or Chat-Completions-capable catalog model is selectable from either harness. `,claude-copilot` defaults to `claude-sonnet-5`; `,codex-copilot` and `,cursor-copilot` default to `gpt-5.3-codex` with `medium` effort. All accept `--model` / `-m`, `--effort` / `--reasoning-effort`, `--thinking auto|on|off` (`--no-thinking` = `off`), and `--context default|long_context`, with `--` separating colliding native harness flags. Thinking control applies only when the selected Copilot backend is Claude/Messages-capable; other backends fail before the upstream request if a thinking override is supplied. `,cursor-copilot` Fish completions cache that same entitlement-filtered catalog for 1 hour and narrow effort/context suggestions to the selected model. The Cursor wrapper uses the same version-matched local agent and pinned loopback settings as `,cursor-codex`; route and model override flags after `--` fail before the child starts.

Native Claude Code Messages traffic and native Codex Responses traffic remain pass-through, with launch-level effort/thinking controls injected where the selected backend supports them. A raw model change does not imply a child role. Only explicit lane tags bypass root controls; Claude managed profiles carry them. The Codex frontend uses a session-local catalog of entitled lane selectors and model-free managed leaf profiles, so native profile defaults cannot overwrite the hook's backend model/effort. Only projected roles and exact pairs are admitted; full-history forks and stale sessions without that projection are denied. Cursor subscription child transport remains disabled. For a cross-protocol selection, the loopback reuses the repo's tested subscription translation modules: Messages ↔ Responses for Claude/GPT crossings, and either native harness protocol ↔ Chat Completions for models such as Gemini. Tool calls, tool results, streaming terminal events, effort, Claude backend thinking mode, and provider-owned opaque tool context are translated with the conversation. Opaque context remains in bounded process memory for the lifetime of the adapter; the GitHub bearer remains confined to that process.

The Codex-subscription adapter also keys the prompt cache the way the Codex CLI does: one `session_id` header and matching `prompt_cache_key` per adapter process. In a live experiment on 2026-09-06, a repeated 2.8k-token prompt read 0 cached tokens without them and 2,688 of 2,823 with them. That sample does not establish hit rates on other routes. No `originator` impersonation is needed or sent.

The Copilot adapter preserves caller-supplied `prompt_cache_key`, `prompt_cache_options`, `prompt_cache_retention`, and text-part breakpoints between Chat and Responses. Marked system/developer content remains structured instead of being flattened into unmarked instructions. OpenAI-to-Messages translation maps text markers to ephemeral block controls and requests automatic caching unless the caller selected explicit mode. Explicit mode without markers stays without cache controls. OpenAI cache keys and lifetimes have no exact Anthropic equivalent and are omitted.

Anthropic-to-OpenAI cache-control synthesis remains unavailable: Copilot's catalog does not advertise the required OpenAI explicit-cache capability. The adapter does not guess capability from a model name or move tool-definition/tool-use markers onto text. Native requests retain their own controls; controls alone do not prove provider acceptance, cache writes, or hits. The shared Codex-subscription allowlist remains unchanged.

Translated streaming Chat upstream requests ask for usage. A Chat frontend receives a separate usage-only chunk only when it requested `stream_options.include_usage`; JSON responses keep their usage object. Responses usage writes use `input_tokens_details.cache_write_tokens`, the field native Codex consumes, while Chat retains `prompt_tokens_details.cache_creation_tokens`. Inclusive input is split into fresh, cache read, and cache write without counting writes twice. The normalizer leaves unreported cache fields absent; renderers use zero for missing split values and omit Chat/Responses detail objects when both cache values are zero.

Responses tool namespaces are flattened to request-local collision-checked wire names for Messages/Chat backends, then restored as separate `namespace` and `name` fields in streamed and JSON function/custom tool calls. Historical calls participate in the same mapping; unnamespaced names remain unchanged. Namespace guidance and raw custom input are retained. This translation fix does not establish the cause of the separate upstream assistant-prefill rejection observed during a worker run.

Translated Responses streams close each text item at its Messages text-block boundary or before a tool item changes the active slot. Later text gets a new item ID and output index. This preserves Messages text/tool order and prevents native Codex from receiving text deltas without a matching active item. Chat backends without explicit text-block stops close text at tool boundaries or the terminal event. Request history is not reordered and no user continuation is invented; this stream fix does not establish the cause of the separate upstream assistant-prefill rejection.

An explicit upstream `stop_reason: "refusal"` becomes a failed translated Responses result, not empty success. Streaming callers receive `response.failed`; JSON callers receive `status: "failed"`. Both include an `invalid_prompt` error with a neutral upstream-refusal message, while retaining usage and any text already emitted. Codex recognizes that error as an invalid request rather than retrying it as a stream failure. Native passthrough and other stop reasons are unchanged. Reporting a refusal does not explain its cause or make the provider accept the request.

Without `--context`, both wrappers use Copilot's `default` tier. When the selected model advertises `long_context`, `--context long_context` caps the tier's prompt allowance at the model's input capability before adding its separate output allowance to the context metadata. Models without that tier fail before the child starts. This matches Copilot CLI's [`--context` contract](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).

Claude's auto-compact window reserves `32k` below the selected prompt budget and also respects the smallest reachable managed-profile budget. Claude's native summary reserve leaves additional headroom; this is compaction guidance, not a hard per-request billing guarantee. Windows above Claude's default `200k` add its frontend-only `[1m]` marker, which the adapter strips before forwarding the catalog model ID. Small custom models receive an explicit maximum. Codex projects each selected prompt limit through `/v1/models` and uses its existing `90%` effective window and compaction threshold; GPT-6 Astra's default `272000` prompt allowance therefore displays `244800` usable tokens. Cursor receives the same selected prompt budget as `capabilities.context_length`. Output capacity remains separate. The loopback removes only Copilot-incompatible Anthropic beta values, currently `advisor-tool-2026-03-01`, while preserving the rest of a native Messages request.

The GitHub bearer is added only on the adapter's upstream request together with Copilot's `copilot-developer-cli` integration ID. A `401` refreshes the value from `gh auth token` and retries once; other failures pass through without retry. Interactive interrupts propagate to the native harness, while adapter shutdown suppresses follow-up `SIGINT` delivery so cleanup does not emit a Python traceback.

### Re-read gate coverage

The hash-gated re-read refusal runs on Claude Code, Codex, OpenCode (via `~/.config/opencode/plugins/agent-memory.ts`, whose `tool.execute.before` throws the gate's reason as the tool error on `read`/`bash` and whose `tool.execute.after` records the result; the earlier copy is verified against the `part` rows of `~/.local/share/opencode/opencode.db`, and a copy cleared by OpenCode's prune counts as gone), and Pi (via `~/.pi/agent/extensions/read-gate.ts`, which feeds `tool_call`/`tool_result` into the shared `read_gate.py`). Pi also carries `~/.pi/agent/extensions/read-supersede.ts`, a port of OMP's read supersede: before each provider call, older results of a file that was read again are replaced with `[Superseded by a newer read of this file]` on the outgoing message list only, and only while the suffix after them is small or the session idled 90 minutes, so the prompt cache is not thrown away for a small saving. OpenCode carries the same port in `~/.config/opencode/plugins/read-supersede.ts` through `experimental.chat.messages.transform`, which runs on the message list OpenCode reloads from its store before every provider call, so the store keeps every original output. OpenCode's native `compaction.prune` stays off (its default): it clears every old tool output beyond a 40k-token tail, not only duplicate file copies. OMP is excluded on purpose: it supersedes the earlier read result in the session as soon as a re-read is attempted, so a block would strip the bytes from the model; OMP therefore dedups re-reads natively. Cursor is wired through `beforeReadFile` (which fires after the read and gates delivery), `beforeShellExecution`, `afterShellExecution`, and `stop`; its tool results live in the conversation's `~/.config/cursor/chats/*/<conversation_id>/store.db` (verbatim JSON blobs), and a token shrink reported by `stop` counts as a compaction. Copilot is wired through the agent-memory extension's `onPreToolUse`/`onPostToolUse`; its `~/.copilot/session-state/<id>/events.jsonl` holds every tool result and `session.compaction_complete` markers. Antigravity can deny on `PreToolUse`, but its transcript and `PostToolUse` result shapes are unverified, so it is not wired.

The publication gate (`~/.agents/hooks/publish_gate.py`) runs on `PreToolUse` in Claude Code (matcher `Bash|mcp__slack__.*`) and Codex (`Bash|shell`; Slack MCP mutations there rely on `codex_tool_approval_modes`, which auto-approves only the read tools). It denies `gh` PR/issue/release/gist mutations, non-GET `gh api` REST calls with a body, `gh api graphql` mutations, `gws` Gmail/Chat sends, and Slack MCP mutation tools from a delegated leaf (Claude Code child `agent_id`, Copilot parent session, pi child), and rides the SOP §3.8 checklist along with the root's call; `AGENT_PUBLISH_GATE_ROOT=ask` makes the root path a harness confirmation and `AGENT_PUBLISH_GATE=off` disables it. Cursor, Copilot, Pi, OMP, OpenCode, and Antigravity are not wired; the leaf contract and repo-authored Claude profiles' `disallowedTools` denial of the six Slack mutation tools remain the boundary there.

### Codex hooks: tool names and trust

Codex reports hook tool names in Claude's vocabulary: shell commands (the plain `exec_command` tool and the code-mode `exec` tool alike) arrive as `Bash`, and spawns as `collaborationspawn_agent`, so `hooks.json` matches `Bash|shell` and `.*spawn_agent` (probed 2026-09-06 with a catch-all dump hook on codex-cli 0.153.4). Codex also runs only hooks it has trusted: `~/.codex/config.toml` keeps a `[hooks.state.<file>:<event>:<index>]` `trusted_hash` per entry, written by the TUI's hooks review, and `chezmoi apply` only preserves those rows. After the repo adds or changes a hook entry, open interactive Codex once and accept the hooks review, or the new entry stays silently inert. `codex exec --dangerously-bypass-hook-trust` runs them without that step and is only for vetted automation such as probes.

### Codex hosted MCP token bridges

`inject_mcp_into_codex_toml.py` emits `slack` and `scsi-main` as `,mcp-token <source> --bridge --url <url>` command servers, not inline secrets or env-var contracts.

The bridge injects a freshly selected bearer per request, rotating through cursor's refresh grant behind the seam, so a Codex session outlives any single token.

## Oh My Pi

The managed `context-mode.ts` extension adds [GPT-only context selection](pi.md#gpt-context-selection):
`/context-mode short`, `/context-mode long`, and `/context-mode status`.
It stores overrides per provider/model in the active session, not in OMP's global `extendedContext` setting.
Non-GPT models keep their existing policy. OMP reapplies the selected mode before each prompt or an idle `/context-mode` command; native `/extended-context` remains a separate global control.

| Surface       | Source                                                                                                                   | Target                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------- |
| Agent config  | [`home/dot_omp/private_agent/readonly_config.yml.tmpl`](../../../../home/dot_omp/private_agent/readonly_config.yml.tmpl) | `~/.omp/agent/config.yml`  |
| MCP servers   | `mcp_servers.yaml` via `generate_mcp_configs.py omp`                                                                     | `~/.omp/agent/mcp.json`    |
| Shared skills | `symlink_skills` → `~/.agents/skills`                                                                                    | `~/.omp/agent/skills`      |
| Runtime hooks | `extensions/`                                                                                                            | `~/.omp/agent/extensions/` |
| Install       | [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs) `@oh-my-pi/pi-coding-agent`     | pnpm global, unpinned      |

### Managed configuration

`readonly_config.yml.tmpl` is the complete declarative OMP contract. `modelRoles` is one profile-independent block placed before the `isWork` branch (user call 2026-09-07); only the web-search chains still fork per profile. Every built-in role is pinned explicitly so nothing falls through to the harness default or the `@smol` fallback: `default`, `vision`, `slow`, and `plan` on `anthropic/claude-fable-5.1:high` (T1); `task` on `anthropic/claude-opus-5:high` (T2 implement — the native `task` agent and every implement worker); `smol` on `anthropic/claude-sonnet-5:high`; `tiny` (titles, memory, auto-thinking classification, unexpected-stop detection) on `anthropic/claude-sonnet-5:medium`; `commit` on `anthropic/claude-sonnet-5:medium`; `advisor` on `openai-codex/gpt-6-astra:high`. `omp config list --json` reports the effective typed settings; inspect all model-role pins together with `omp config get modelRoles`, not with dotted child keys. A second file, `readonly_models.yml` (`~/.omp/agent/models.yml`), keeps the bare OpenRouter ids selectable and declares the preset-slug ids used by shared provider-policy routes: `z-ai/glm-5.3-flash@preset/glm-lanes-high` (FP8-or-higher quantization, 24 t/s floor, no `sort` so default load balancing keeps uptime), `z-ai/glm-5.2@preset/glm-lanes-max` (same FP8-or-higher, 24 t/s floor policy; still selectable), `deepseek/deepseek-v4.1-flash@preset/deepseek-lanes-max` (35 t/s preferred floor under a $1.20/M completion cap, no quantization filter; still selectable), and `moonshotai/kimi-k3@preset/kimi-lanes` (Fireworks/Together/BaseTen-only under the $16/M cap), with `auth: none` so the env `OPENROUTER_API_KEY` still authorizes (see [Model registry & routing](../model-registry.md#openrouter-routing)).

| Setting                                                                                | Work value                                                                                        | Personal value                                             |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `modelRoles.default`, `vision`, `slow`, `plan` (T1)                                    | `anthropic/claude-fable-5.1:high`                                                                 | same (one profile-independent block)                       |
| `modelRoles.task` (T2 implement: native `task` agent + implement workers)              | `anthropic/claude-opus-5:high`                                                                    | same (one profile-independent block)                       |
| `modelRoles.smol`                                                                      | `anthropic/claude-sonnet-5:high`                                                                  | same                                                       |
| `modelRoles.tiny`                                                                      | `anthropic/claude-sonnet-5:medium`                                                                | same                                                       |
| `modelRoles.commit`                                                                    | `anthropic/claude-sonnet-5:medium`                                                                | same                                                       |
| `modelRoles.advisor`                                                                   | `openai-codex/gpt-6-astra:high`                                                                   | same                                                       |
| `modelProviderOrder`                                                                   | `anthropic`, `openai-codex`, `openrouter`, `cursor`, `openai`                                     | same                                                       |
| `advisor.enabled`                                                                      | `false` (subagents false; background advice disabled)                                             | same                                                       |
| `defaultThinkingLevel`                                                                 | `high`                                                                                            | `high`                                                     |
| `memory.backend`                                                                       | `off`                                                                                             | `off`                                                      |
| `autolearn.enabled`, `autolearn.autoContinue`                                          | `false`, `false`                                                                                  | `false`, `false`                                           |
| `dev.autoqaConsent`                                                                    | `granted`                                                                                         | `granted`                                                  |
| `skills.enabled`, `skills.enableSkillCommands`                                         | `true`, `true`                                                                                    | `true`, `true`                                             |
| `task.isolation.mode`, `task.enableEffort`, `task.enableLsp`, `task.maxRecursionDepth` | `auto`, `true`, `true`, `1` (children cannot spawn grandchildren); `task.agentAdvisor.task` `off` | same                                                       |
| `retry.enabled`, `retry.maxRetries`                                                    | `true`, `3`                                                                                       | `true`, `3`                                                |
| `symbolPreset`, `theme.dark`, `setupVersion`                                           | `nerd`, `dark-catppuccin`, `2`                                                                    | `nerd`, `dark-catppuccin`, `2`                             |
| `providers.webSearchOrder`                                                             | `codex`, `gemini`, `google`, `duckduckgo`                                                         | `codex`, then keyless scrapers in OMP built-in order       |
| `providers.webSearchExclude`                                                           | every other OMP search id, including `perplexity`                                                 | every keyed search id, including `perplexity` and `gemini` |

`modelRoles` is also what prices OMP's categories: repo-managed agent profiles carry `@role` tokens (`@default`, `@smol`, `@task`, `@plan`, `@advisor`) that `category_models.omp` names, so the one profile-independent role table above decides what each category costs. See [Model tiering](../model-tiering.md).

The background OMP advisor is disabled (`advisor.enabled: false`, `advisor.subagents: false`, and `task.agentAdvisor.task: "off"`). The `modelRoles.advisor` pin remains available to the explicit final refute lane; a model-role selector does not enable background advice. `syncBacklog` and `immuneTurns` do not create an advisor while it is disabled. Shared `,ai-kb` recall and learning remain active through the managed memory extension; OMP's separate native memory/autolearn settings stay off.

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

The managed custom agents are thin `.agent.md` profiles that point back to the shared review skill. `settings.json` owns the exact agent roster plus effort/context policy, while profile frontmatter owns resolver-rendered model selection.

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

The typed reconciler recursively preserves live keys absent from the baseline and lets declared values win. It replaces `subagents.agents` exactly with the declared agent map, which removes stale agent names and persisted per-agent model/effort/context overrides while preserving unrelated runtime preferences.

The target is in `.chezmoiignore`.

### Copilot agent memory

A live probe of Copilot 1.0.68 showed that its JSON command hooks run from `~/.copilot/hooks/*.json`, but their `SessionStart` stdout is not ingested as context.

The active context path is the `agent-memory` extension. It registers `onSessionStart`, `onPostToolUse`, and `onPostToolUseFailure`, translates Copilot's camelCase SDK payloads to the shared snake_case script contract, and returns SDK `additionalContext`.

The command-hook file and its legacy checksum row are cleaned up by the apply hook. Copilot has no shell-gate hooks; PR review anchor verification is instruction-owned by the review/GitHub skills.

## Crush

Crush auto-discovers project-local context files (such as `AGENTS.md`) from the working directory only. The home SOP is injected into every session through a global `crushrc`.

| Surface       | Path                                                                                           | Target                    |
| ------------- | ---------------------------------------------------------------------------------------------- | ------------------------- |
| Global config | [`home/dot_config/crush/readonly_crushrc`](../../../../home/dot_config/crush/readonly_crushrc) | `~/.config/crush/crushrc` |
| Home SOP      | [`home/readonly_AGENTS.md`](../../../../home/readonly_AGENTS.md) → `~/AGENTS.md`               | global context path       |

The `crushrc` sets `option global-context-path "$HOME/AGENTS.md"`, so Crush loads the compiled home SOP in every session regardless of cwd. Project repos keep their own local `AGENTS.md`, which is discovered automatically; per the home SOP hierarchy, project-local instructions may add constraints but must not weaken the global SOP.

## tuicr (review TUI)

[tuicr](https://github.com/agavra/tuicr) is a terminal UI for code review, not an LLM harness. Its config is single-sourced and read-only.

| Surface | Path                                                                                                   | Target                        |
| ------- | ------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Config  | [`home/dot_config/tuicr/readonly_config.toml`](../../../../home/dot_config/tuicr/readonly_config.toml) | `~/.config/tuicr/config.toml` |

The config defines the review **comment types** (`issue`, `suggestion`, `question`, `nit`, `praise`) that tuicr exports as `[LABEL]` prefixes in the markdown an agent consumes.

These are actionable categories, not severity. Severity (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) stays internal per the `~/AGENTS.md` review SOP and is intentionally not encoded here, so tuicr labels and the review skill's severity model do not collide.

## lgtm (live diff reviewer)

[lgtm](https://github.com/kunkka19xx/lgtm) is a terminal diff reviewer that runs in a tmux pane beside the agent and sends `path:line` references into its input box. Its config is single-sourced and read-only.

| Surface | Path                                                                                                 | Target                       |
| ------- | ---------------------------------------------------------------------------------------------------- | ---------------------------- |
| Config  | [`home/dot_config/lgtm/readonly_config.toml`](../../../../home/dot_config/lgtm/readonly_config.toml) | `~/.config/lgtm/config.toml` |

The config sets the `catppuccin` theme, nerd-font icons, inline comment rendering, lockfile ignores, and the compose-box question presets; every other setting stays compiled-in default.

Per-repo `.lgtm/` state (comments, reviews, read marks) and `refs/lgtm/**` snapshots are runtime-owned and intentionally unmanaged by chezmoi.

## Secrets

Some API keys are loaded into the shell from `pass` in [`home/dot_config/fish/readonly_config.fish.tmpl`](../../../../home/dot_config/fish/readonly_config.fish.tmpl). That means your password-store is part of the runtime wiring for AI tools.

```bash
echo "${GEMINI_API_KEY:+set}"
echo "${OPENROUTER_API_KEY:+set}"
```

Do not commit literal secrets into tool config files; keep them in `pass` and load at runtime. See [Security and secrets](../../security/security-and-secrets.md).
