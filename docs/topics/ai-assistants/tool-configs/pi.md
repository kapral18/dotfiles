---
sidebar_position: 4
title: Pi coding agent
---

# Pi coding agent settings

Pi is configured from pnpm-managed packages plus readonly chezmoi sources under `home/dot_pi/agent/`. The page covers the installed packages, profile-specific settings and models, the shared MCP registry path, and the `APPEND_SYSTEM.md` operating layer that gives Pi the same working rules other harnesses receive.

## Mental model

| Piece               | Source                                                                                                                                                                                                                                                                                             | Target / effect                                                 |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Pi packages         | [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs)                                                                                                                                                                                                           | pnpm globals used by Pi                                         |
| Settings + models   | [`home/dot_pi/agent/readonly_settings.{work,personal}.json`](../../../../home/dot_pi/agent/) + work/shared [`readonly_models.json`](../../../../home/dot_pi/agent/readonly_models.json) or personal [`readonly_models.personal.json`](../../../../home/dot_pi/agent/readonly_models.personal.json) | `~/.pi/agent/`                                                  |
| MCP servers         | [`home/.chezmoidata/mcp_servers.yaml`](../../../../home/.chezmoidata/mcp_servers.yaml)                                                                                                                                                                                                             | `~/.pi/agent/mcp.json`                                          |
| System prompt       | [`home/dot_pi/agent/readonly_APPEND_SYSTEM.md`](../../../../home/dot_pi/agent/readonly_APPEND_SYSTEM.md)                                                                                                                                                                                           | `~/.pi/agent/APPEND_SYSTEM.md`, appended to Pi's default prompt |
| Session diagnostics | [`scripts/analyze_pi_session.py`](../../../../scripts/analyze_pi_session.py)                                                                                                                                                                                                                       | privacy-safe aggregate metrics from one saved Pi v3 session     |

## Using it

### Installed packages

Pi globals are installed via pnpm from [`home/readonly_dot_default-pnpm-pkgs`](../../../../home/readonly_dot_default-pnpm-pkgs) to `~/.default-pnpm-pkgs`.

| Package                           | Purpose                                                     |
| --------------------------------- | ----------------------------------------------------------- |
| `@earendil-works/pi-coding-agent` | Core Pi agent                                               |
| `@earendil-works/pi-tui`          | Pi TUI (work profile)                                       |
| `pi-mcp-adapter`                  | MCP adapter extension                                       |
| `pi-subagents`                    | Subagent delegation extension (parallel, isolated context)  |
| `@rahularya01/pi-cursor`          | Native `cursor` model provider (Cursor subscription models) |

### Cursor provider

`@rahularya01/pi-cursor` registers a `cursor` provider that speaks Cursor's own `agent.v1.AgentService/Run` Connect/protobuf stream over HTTP/2 and signs in through the same PKCE deep-link flow (`cursor.com/loginDeepControl` → `api2.cursor.sh/auth/poll`) that OMP's built-in `cursor` provider uses. OMP's provider is not reusable directly: it lives inside `@oh-my-pi/pi-ai` (`src/providers/cursor.ts`, `registry/oauth/cursor.ts`), depends on `@oh-my-pi/pi-catalog` protobuf codegen and `Bun.sleep`, and is not loadable by upstream Pi. The package credits oh-my-pi for the in-process bidirectional HTTP/2 pattern.

| Aspect       | Behavior                                                                                                                                                                                                                                                                                                              |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime      | Package docs say "Bun only", but that is the package's own toolchain: the published `dist/index.js` has no `Bun.*` calls, only `node:http2`, and it loads and registers under Pi's Node runtime (probed 2026-09-14 on Pi 0.85.1 / Node 24.6: `registerProvider cursor` with 42 catalog models, `api: cursor-native`). |
| Credentials  | Cascade: `CURSOR_ACCESS_TOKEN` → Pi `~/.pi/agent/auth.json` (`/login cursor`) → Cursor CLI macOS Keychain (`cursor-access-token` / `cursor-refresh-token`) → Cursor IDE `state.vscdb`. Set `PI_CURSOR_SYSTEM_CREDENTIALS=0` to disable Keychain/IDE reuse.                                                            |
| Availability | Pi hides a provider's models until it has a credential for that provider. The Keychain fallback feeds requests, but `/model` and `pi --list-models` show `cursor/*` only after `/login cursor` writes a `cursor` entry to `~/.pi/agent/auth.json`.                                                                    |
| Models       | Live discovery via `GetUsableModels`, cached under `PI_CURSOR_CACHE_DIR`, bundled fallback catalog on first launch. Pi thinking levels map to Cursor effort variants; `/cursor.models`, `/cursor.usage`, `/cursor.doctor` are provided by the package.                                                                |
| Tiering      | Adding the provider does not change any root or category model pick; `category_models` and Pi agent profiles are unchanged. Cursor ids in [`tiering.yaml`](../../../../home/.chezmoidata/ai_models/tiering.yaml) still describe the Cursor harness, not this Pi provider.                                             |

### Profile defaults

| Profile  | Default                               | Extra providers/models |
| -------- | ------------------------------------- | ---------------------- |
| work     | `github-copilot` / `claude-fable-5.1` | configured work models |
| personal | `github-copilot` / `claude-fable-5.1` | `llama-cpp`            |

The native root uses Pi's built-in GitHub Copilot provider at high thinking with Fable 5.1's native 1M window; context-mode does not alter this Claude root because Fable has no distinct short window. Explicit OpenRouter routes and category/child model selections remain independent. The local llama.cpp provider for Pi is covered in [Model registry & routing](../model-registry.md) and [llama.cpp local inference](../llama-cpp/index.md). Both `readonly_models*.json` files carry `providers.github-copilot.modelOverrides.gpt-6-astra.contextWindow: 272000`: Pi's built-in Copilot entry advertises a 1.05M window but bills input and cache tokens at 2× (output at 1.5×) once a request exceeds 272k input tokens (`tiers.inputTokensAbove: 272000` in the bundle's `github-copilot.js`), so the cap makes compaction fire before that tier the way Pi's direct-OpenAI entries already do; Fable 5.1 has no tier and keeps its native 1M. Both files also carry `providers.openrouter.modelOverrides`: `moonshotai/kimi-k3` allows only Fireworks, Together, and BaseTen under a $16/M completion cap, while `z-ai/glm-5.3-flash` and `z-ai/glm-5.2` allow only FP8-or-higher quantization; GLM 5.3 Flash has a 35 t/s preferred floor in work and 24 t/s in personal, while GLM-5.2 stays at 24 t/s in both, and `deepseek/deepseek-v4.1-flash` carries a 35 t/s preferred floor under a $1.20/M completion cap with no quantization filter (user call 2026-09-11: few DeepSeek endpoints declare a quantization, so the allowlist starved the route), and `openai/gpt-6-astra` allows only OpenAI's Flex service tier (`only: ["openai/flex"]`, half the standard endpoint price; base slugs never match service tiers). None of these objects set `sort`, so OpenRouter's default load balancer keeps uptime then price-weights remaining endpoints. Both use `compat.openRouterRouting` (see [OpenRouter routing](../model-registry.md#openrouter-routing)).

### Model profiles

`,pi-model-profile` switches Pi's whole pricing on this machine: the root model plus all six category lanes. `,pi-model-profile --show` prints the active rows, `,pi-model-profile <name>` selects one without fzf, and a bare invocation picks from `default` plus every `pi_model_profiles` name in [`tiering.yaml`](../../../../home/.chezmoidata/ai_models/tiering.yaml). `default` is the repo's own Pi rows; `local` runs everything on the llama.cpp router. `anthropic` runs everything on the direct Anthropic provider and `codex` on the ChatGPT-subscription `openai-codex` provider. Two read-only flags exist for machine consumers rather than for reading: `--list` prints one name per line with `default` first and no active marker, and `--session <name>` prints that profile's session row as `<provider/model-id>\t<effort>`.

The selection is one line in `${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/pi-model-profile`, beside the managed-config manifest, because the pick belongs to the machine rather than to a commit. The picker writes it and then runs a full `chezmoi apply`, which re-renders the 16 `~/.pi/agent/agents/*.md` profiles and re-runs the Pi merge hook; that hook patches `defaultProvider`, `defaultModel` and `defaultThinkingLevel` in the installed `settings.json` from the active session row, so the checked-in `readonly_settings.{work,personal}.json` stay at `default`. An unknown name in the state file fails the apply with the valid names listed. See [Model tiering](../model-tiering.md#pi-model-profiles).

#### `/model-profile` inside a session

`pi-model-profile.ts` registers `/model-profile` so the switch does not need a second terminal. With no argument it selects over `,pi-model-profile --list`, marking the active name from `--show`; with an argument it uses that name directly, and argument completion comes from the same `--list`. Either way it then runs `,pi-model-profile <name>`, so the CLI stays the only writer and the only validator of the state file — the extension never writes that file and never parses `tiering.yaml`. A non-zero exit is reported as an error and the live session is left alone; for a known name the CLI has already written the state file by then, so the next `chezmoi apply` renders the selected profile.

A successful apply reaches new sessions and subagents, never the running one: Pi resolved its model at session start. So the command then reads `,pi-model-profile --session <name>`, splits the provider at the **first** slash (model ids such as `z-ai/glm-5.3` carry their own slashes, providers do not), looks the model up in the session's catalogue, and calls `setModel`/`setThinkingLevel`. Those are session-scoped and do not disturb the `default*` keys the apply just wrote. When the lookup fails or the provider has no configured authentication it warns that the profile is applied for new sessions and subagents but this session's model was not switched, and names why. In print (`-p`) and JSON modes there is no dialog UI, so the command is a no-op.

### Shared settings

| Setting area       | Behavior                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Context compaction | Automatic context compaction uses a hybrid sliding window.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Cache visibility   | Significant prompt-cache misses appear in the transcript; the footer and `/session` expose Pi's own cache accounting.                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Retries            | Exponential backoff retries.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Extension loading  | Pi loads the chezmoi-managed runtime extensions plus `pi-mcp-adapter`, `pi-subagents`, and `@rahularya01/pi-cursor` from the stable `~/.local/share/pnpm-global-links/node_modules/` tree that `,install-pnpm-pkgs` rebuilds after every sync (pnpm 11+ global install paths are hashed and move on update).                                                                                                                                                                                                                                                    |
| Model re-pin       | `model-pin.ts` appends a `model_change` after any turn whose assistant message echoes a different model id than the routed catalog id (GitHub Copilot returns `claude-fable-5-1` for `claude-fable-5.1`), so `pi -c` restores the real model instead of warning `Could not restore model`. Workaround for [earendil-works/pi#9243](https://github.com/earendil-works/pi/issues/9243); remove when the read side prefers `model_change`.                                                                                                                         |
| Subagent config    | `pi-subagents` reads `~/.pi/agent/extensions/subagent/config.json`; chezmoi manages it as `exact_extensions/subagent/readonly_config.json` with `modelResponseAliases` mapping `github-copilot/claude-fable-5.1` to the `claude-fable-5-1` echo, so its parity check accepts the response id. The `subagent/` directory is not `exact_`, so package-owned `agents/` or instruction files under it survive apply; before this file was managed, `exact_extensions` pruned the directory on every apply and `chezmoi update` prompted on the recreated directory. |
| Native tools       | `runtime-parity.ts` enables `grep`, `find`, and `ls` alongside Pi's default tools unless explicit CLI tool-selection flags override the defaults.                                                                                                                                                                                                                                                                                                                                                                                                               |
| Model profile      | `pi-model-profile.ts` registers `/model-profile`, a front end for `,pi-model-profile` that also re-points the running session at the chosen profile's session row. See [`/model-profile` inside a session](#model-profile-inside-a-session).                                                                                                                                                                                                                                                                                                                    |
| Delegation         | `subagent-contract.ts` publishes the sole `subagent` tool (plus native `bg_wait`) for isolated child contexts by loading the installed `pi-subagents` entry once with empty package extensions/skills/prompts; named review profiles cover reviewer, verifier, live-UI, and findings-audit phases.                                                                                                                                                                                                                                                              |
| Session hooks      | `ai-kb-recall.ts` invokes the shared session-context hook, stages depth-aware per-turn recall candidates for the `k-agent-smol` judge (pointer injection only) plus the correction directive, and forwards tool results to the shared worklog.                                                                                                                                                                                                                                                                                                                  |
| PATH               | Shell PATH order keeps `~/.local/share/pnpm/bin` ahead of runtime-manager shims so `pi` resolves to the pnpm-managed binary.                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Secrets            | `GEMINI_API_KEY` and `OPENROUTER_API_KEY` are picked up from environment variables exported via `pass` in `config.fish.tmpl`. `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are not exported; those are subscription logins, and any tool needing a raw key reads `pass` itself.                                                                                                                                                                                                                                                                                     |

Automatic context compaction triggers when context exceeds `contextWindow − reserveTokens` (16384), keeps the most recent `keepRecentTokens` (80000) verbatim, and LLM-summarizes older turns. It merges iteratively with the prior summary so it never decays into a summary-of-a-summary.

`keepRecentTokens` is raised from Pi's `20000` default to preserve far more high-fidelity recent context before any lossy summarization. The setting is global, not per-model.

`80000` is sized for the 262144-token local Nemotron window, ~30% recent-verbatim. It also remains below the work-profile Qwen3.8 131072-token context and the configured OpenRouter default's context limit.

### Working-context selection

Pi and OMP share `~/lib/shared/context_mode.ts`, loaded by each harness's managed `context-mode.ts` extension.
A model is eligible only when it has a distinct short window below native capacity.
GPT models default to short. Other eligible families keep the native window until `/context-mode short`.
Ineligible models and global settings stay unchanged.

| Command                | Effect                                                                                                                                              |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/context-mode short`  | Use the smaller of the native window and the catalog's long-context input threshold. GPT without tier metadata uses a 272,000-token working budget. |
| `/context-mode long`   | Opt this provider/model into its known native or advertised maximum.                                                                                |
| `/context-mode status` | Show the selected mode and effective working window.                                                                                                |

For Copilot Astra, short uses 272,000 tokens. The fallback for other GPT models is a working budget, not a guarantee about their pricing.
Non-GPT families have no 272k fallback: short comes from catalog tiers or from `contextWindow` when `maxContextWindow` is larger.
Copilot Grok 4.5/4.6 are eligible (500k native, 200k tier). Claude Fable is not.
Thresholds come from Pi's `cost.tiers[].inputTokensAbove` or OMP's `cost.longContext.inputThreshold`; the earliest valid threshold wins.
Selections are custom session entries, not prompt text or global preferences. They follow the active branch and survive resume; selecting another provider/model does not inherit the previous model's override.
Pi reapplies on model selection and before each prompt. OMP reapplies before each prompt or an idle `/context-mode` command because its native model-change event is not exposed to extensions.

Switching to short with history already at or above the short window is refused without running a summarizer.
Use `/compact` or start a new session, then select short. An active turn/model change also prevents selection.
Native compaction and output sizing use the selected window; the model route, explicit effort, output-capacity metadata, and cache controls are not replaced.
Earlier compaction is not a hard pre-send token limit or a credit cap: large pending input and compaction itself can still cost money.
The selector requires the extension to load; it does not rewrite separately pinned child roles or enable extensions in restricted native workers.

### Prompt-cache and compaction diagnostics

Both profiles set `showCacheMissNotices: true`. Pi emits a transcript notice only for a significant miss after cache activity has been observed; providers that never report cache counters are not treated as misses. The interactive footer shows the latest cache-hit rate, and `/session` shows cached versus uncached prompt tokens plus cumulative cache re-billing.

The repo does not duplicate Pi's cache-miss algorithm. [`scripts/analyze_pi_session.py`](../../../../scripts/analyze_pi_session.py) adds the offline view Pi lacks:

```bash
python3 scripts/analyze_pi_session.py /path/to/session.jsonl
python3 scripts/analyze_pi_session.py /path/to/session.jsonl \
  --max-compactions 2 \
  --max-reread-ratio 0.25 \
  --min-cache-hit-rate 0.50
```

The analyzer accepts only Pi session format v3. It follows the active `parentId` chain, aggregates assistant token/cache/cost fields, records compaction `tokensBefore`, and compares structured built-in `read` calls after compaction with the compaction's `details.readFiles`. It reports only counts and ratios: prompts, summaries, tool output, and file paths never appear.

`cache.hit_rate` is `null` until a positive provider cache counter is observed. `compaction.reread_ratio` is `null` when no post-compaction reads can be measured, and `read_tracking_complete` shows whether every active-branch compaction exposed default read-file details. Exit status `2` means an explicit threshold failed; malformed input or an unsupported format exits `1`.

Pi loads packages from the pnpm global link tree paths to avoid Pi-managed npm update prompts; `pi install` is not used. Each package's `package.json` `pi` field declares its extension/skills/prompts, which Pi auto-loads, except `pi-subagents`: its settings entry uses the object form with empty `extensions`, `skills`, and `prompts`, so the package stays installed but contributes no registration. The source-owned `exact_extensions/subagent-contract.ts` adapter loads that entry exactly once and is the sole owner of the published `subagent` tool.

The installed Pi discovers `~/.agents/skills/` natively, so no skills bridge package is configured. See [Runtime recall wiring](../knowledge-base/cross-agent-memory.md). `@earendil-works/pi-tui` stays pnpm-managed but is not loaded as a Pi extension package.

The `subagent` tool supports review, scout, and parallel audits while keeping the parent session's token use bounded on long tasks. It is fully local: no network/telemetry beyond the model calls the child agents make. Its published description and parameter schema come from `subagent-contract.ts`, which projects a managed leaf-only contract before registration: a provider-compatible root object schema with closed properties and two closed variants (leaf requiring `agent`/`agentScope:"user"`/`acceptance:false` with fresh context and one leaf packet per call; management requiring one of `list`/`status`/`debug.run`/`stop`/`interrupt`). The same registered schema is enforced at runtime through the native pi-ai validator, so the guard owns no separate allowlist. Two rejection classes both mean invalid invocation, final for that shape: the native schema failure `Validation failed for tool "subagent"` (thrown before `tool_call`/`execute`, so no run id exists) and the deployment guard prefix `INVALID_DISPATCH_REQUEST`. Correct the call instead of retrying it unchanged, and never treat either as lost authorization.

`subagent-contract.ts` appends the root dispatch note to the system prompt, pointing at the tool description and registered schema as the sole contract. The note names both rejection classes (`Validation failed for tool "subagent"` from the native validator, `INVALID_DISPATCH_REQUEST` from the deployment guard) as correct-don't-retry, and an identical packet is retried once only when the tool executed and then reported a host, bootstrap, or runner failure; a child that timed out or exhausted its budget is re-sized (split, or ship materialized inputs), never relaunched identical. The tool description tells the root to call `{action:"list",agentScope:"user",capabilities:true}` once per session and reuse the roster, and to consume a child result once (read the file for a file-only pointer; do not re-read when the body arrived inline). The same adapter decorates `sendMessage`: upstream watchdog notices (`subagent_control_notice`, formatted by pi-subagents `subagent-control.ts`) advertise `steer`/`resume` nudges the contract rejects, so those lines are replaced with a status/interrupt hint before the parent sees them; signal, facts, intercom target, status, and interrupt lines pass through unchanged. `runtime-parity.ts` keeps only search-tool defaults and SOP delivery; it no longer owns any dispatch policy.

Native sources (installed Pi 0.85.1 / pi-subagents 0.67.0, under the pnpm global store): the factory projection point is `pi-subagents/src/extension/index.ts` (the `subagent` tool registration, with parameters from `createSubagentParamsSchema` in `src/extension/schemas.ts`); package filtering is `pi-coding-agent/dist/core/package-manager.js` (`collectPackageResources`/`applyPackageFilter`); the validator-before-hook order is `pi-agent-core/dist/agent-loop.js` (`prepareToolCall` runs pi-ai `validateToolArguments` from `pi-ai/dist/utils/validation.js` before `beforeToolCall`, and the failure text is `Validation failed for tool "subagent"`); single-owner registration rests on `pi-coding-agent/dist/core/extensions/runner.js` (`getAllRegisteredTools`, first registration per name wins) plus the filter above.

Four leaves whose returns are multi-kilobyte reports (`k-agent-reviewer`, `k-agent-adversarial-verifier`, `k-agent-public-sources`, `k-agent-code-searcher`) set `output: k-agent-<role>.md` and `outputMode: file-only`, so the completion notice carries an `Output saved to: <path>` pointer instead of the full report. The root reads that file once. Every other profile (including `k-agent-change-auditor`, `k-agent-implementer`, and `k-agent-mechanical`) stays inline; their returns are short enough that a pointer would cost a second round-trip.

Managed Pi agent profiles keep model and thinking separate. `agent-model.partial` or `review-agent-model.partial` renders the category model without a `:level` suffix; `agent-thinking.partial` renders the category row's `effort` as frontmatter `thinking:` and omits the line when effort is empty. `pi-subagents` accepts `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`.

## Harness operating layer (`APPEND_SYSTEM.md`)

Pi's built-in default prompt is minimal: persona, tools list, "be concise", and "show file paths". Cursor injects a thicker operating layer: tool policy, task/todo discipline, code citations, proactiveness, and edit-scope rules.

`~/.pi/agent/APPEND_SYSTEM.md` closes that gap.

Prompt order:

```text
Pi default -> operating layer -> project context
```

Pi discovers `APPEND_SYSTEM.md` through `DefaultResourceLoader` and appends it before the `<project_context>` block that wraps `AGENTS.md` / `CLAUDE.md`. `,q` skips this file: it passes a short `--system-prompt` and an empty `--append-system-prompt`.

Why `APPEND_SYSTEM.md`, not `SYSTEM.md`:

- additive file preserves Pi's default tools list and self-doc pointers.
- replacement file would lose those defaults.
- source is profile-agnostic and installed readonly.

**Scope:** this is harness parity, not a replacement for `AGENTS.md`.

`runtime-parity.ts` supplies the full home SOP outside `$HOME` through `before_agent_start`. It preserves the existing system prompt and skips insertion when a canonical native context path or the complete SOP body is already present. Explicit no-extension workflows bypass this adapter. A missing SOP emits a diagnostic and preserves the base prompt.

Ported mechanics are the set difference:

```text
Cursor built-in prompt - Pi built-in prompt
```

Included mechanics:

- tone/style: no emojis, no colon before a tool call, backtick paths/symbols.
- tool calling: use dedicated file tools, parallelize independent calls, don't name tools to the user.
- code changes: read before edit, fix introduced linter errors, avoid narrating comments.
- autonomy: finish before yielding.
- task management: todos for complex tasks.
- structured enumerated questions.
- `file_path:line_number` citations.

Excluded Cursor-only mechanics:

- `@`-mentions and system-tag handling.
- terminal-files convention.
- Plan/Agent mode selection.
- Cursor's `start:end:path` citation UI.
- inline line-number disambiguation, because Pi's read tool returns raw text without `LINE|` prefixes.

The read-tool detail was verified in `core/tools/read.ts`; there is no line-prefix stream for the inline-number rule to disambiguate.

Where project context overlaps, `AGENTS.md` wins.
