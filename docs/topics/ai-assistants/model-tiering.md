---
sidebar_position: 5
---

# Model tiering

Which model/effort a task should run on, and whether that task belongs inline in the orchestrating session or in a dedicated subagent, are the same decision. This page is the taxonomy that decision uses, the per-harness picks it resolves to, and the native-subagent-takeover risks that can silently bypass it.

Canonical data lives in [`home/.chezmoidata/ai_models/tiering.yaml`](../../../home/.chezmoidata/ai_models/tiering.yaml), split across three tables that are deliberately kept apart:

| Table              | Dimension   | Says                                                                                          |
| ------------------ | ----------- | --------------------------------------------------------------------------------------------- |
| `agent_categories` | portable    | What a kind of work needs: `{band, family}` for each of the seven categories                  |
| `agent_bindings`   | portable    | Which category each delegable agent name belongs to, built-ins included                       |
| `model_bands`      | per harness | What `cheap`, `standard`, and `max` resolve to here, plus `counter` on `max` where one exists |

Whether a findings audit needs max reasoning is a fact about the job, not about Copilot; only `model_bands` knows Codex's catalog. Merging the two is what made the previous single `model_tier_map` need 57 rows to carry roughly 21 facts. Categories are chosen before the model: the SOP delegation section and the `k-*` skills name a category, the category names a band, and only then does a harness resolve an id.

**Bands are editorial.** `cheap`/`standard`/`max` is a human judgment reviewed in the registry, not a value derived from a model's thinking-budget ladder or price. Harness catalogs share the same minimal/low/medium/high shape across most models, so there is nothing to normalize against; the band exists so that "high" on a cheap-band model and "high" on a max-band model are not read as the same amount of effort.

**Two standing policies keep the option space small.** Every band runs short context unless the harness publishes no short variant of the wanted model, and the cheap band takes the codex tier (`gpt-5.4-codex` at high effort) on every harness whose catalog carries it. Claude Code and Antigravity are single-vendor and keep their own cheap pick, Cursor pins every band to `cursor-grok-4.6-xhigh` (user call 2026-08-14; the Task whitelist has no codex id), and native Codex deliberately overrides the cheap rule with the user-selected all-band `gpt-5.6-sol`/xhigh policy.

## Categories

Classification is example-anchored judgment, not a countable metric. Each category names the band to reach for **and** whether the work belongs inline in the orchestrating session or delegated.

| Category      | Band     | Example tasks                                                                                 | Placement                                                                                                                                         |
| ------------- | -------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `search`      | cheap    | Read-only recon: grep-and-report, locate a call site, gather base context                     | Delegate — keeps verbose intermediate output out of the orchestrator's context                                                                    |
| `mechanical`  | cheap    | Deterministic edits with a known shape: a rename across files, applying a settled pattern     | Delegate                                                                                                                                          |
| `research`    | standard | External sources and synthesis: read a public repo, reconcile docs against installed source   | Delegate                                                                                                                                          |
| `implement`   | standard | Normal implementation with a clear shape: add a function, wire a pattern into a new call site | Inline, or delegated when the edit is large or isolated enough to benefit from a fresh context                                                    |
| `orchestrate` | max      | Session default: deciding what to delegate, judging what comes back, resolving ambiguity      | Stays in the main session — ambiguity resolution is not delegable without losing the context needed to do it                                      |
| `review`      | max      | Reviewing a change and auditing findings                                                      | Delegate to a review lane, never demoted below `max`                                                                                              |
| `refute`      | max      | Breaking a conclusion: adversarial verification, criteria refutation, blind clarity           | Delegate; prefer a **different model family** than the lane being refuted at equal capability — capability outranks diversity (`family: counter`) |

`general-purpose` is bound to `implement`, not `search`, despite being the cheapest thing to reach for: it carries `tools: "*"` and is the only delegated agent that can edit anything.

Only `refute` is `family: counter`. Same-family reviewers inherit the same blind spots and the same context contamination, so prefer the counter at equal capability — capability outranks family diversity (SOP §3.7). Where a harness cannot field a second family, resolution reports `degraded` rather than presenting the weaker pass as a real cross-family one.

The orchestrating session is always the one deciding which category a piece of work falls into and whether to delegate — it is the driver, subagents are dispatched, not the other way around.

### Enforcement

The band reaches a delegated run by two paths, and both are needed:

1. **Profiles declare it where the harness supports profiles.** [`home/.chezmoitemplates/agent-model.partial`](../../../home/.chezmoitemplates/agent-model.partial) resolves `agent → category → band → model` at apply time, so each agent file under `dot_<harness>/exact_agents/` renders a concrete id. Copilot has no per-agent files for its built-ins, so [`scripts/generate_subagent_models.py`](../../../scripts/generate_subagent_models.py) writes `subagents.agents.*` from the same registry. Antigravity uses runtime-defined subagents instead, with the registry's supported `pro` selector passed to `invoke_subagent`.
2. **A hook makes it non-negotiable per call.** [`band_gate.py`](../../../home/exact_dot_agents/exact_hooks/executable_band_gate.py) runs pre-tool-use, reads the projection that [`scripts/generate_agent_bands.py`](../../../scripts/generate_agent_bands.py) emits to `~/.config/ai/agent-bands.v1.json`, and rewrites the delegation payload. Each harness has its own request and response shape, all verified against the running binaries.

| Harness     | Gate wiring                                                           | What it rewrites                                                                                                         |
| ----------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Codex       | `PreToolUse` matcher `spawn_agent` in `hooks.json.tmpl`               | `model` + `reasoning_effort`; `updatedInput` is dropped unless `permissionDecision: "allow"` rides along                 |
| Cursor      | `preToolUse` in `hooks.json`                                          | `Task.model` — `updated_input` replaces the whole input object, so the gate echoes every other field                     |
| Claude Code | `PreToolUse` matcher `Agent\|Task` in `settings.{work,personal}.json` | The family alias, and only when the caller passed a different one; an unqualified call keeps the profile's exact id      |
| Copilot     | `onPreToolUse` in the `agent-memory` extension                        | `modifiedArgs.model` + `reasoning_effort`; Copilot hands `toolArgs` over JSON-encoded, so the gate parses a string first |
| Antigravity | none                                                                  | Dynamic `invoke_subagent` calls receive the registry's abstract `pro` model tier directly                                |
| OMP         | none needed                                                           | Bands are `@role` tokens that `modelRoles` resolves natively                                                             |

`AGENT_BAND_MODEL_OVERRIDE` (with `AGENT_BAND_EFFORT_OVERRIDE`) collapses every band onto one model for a route whose catalog is a single model, and reaches agents with no binding too, since a built-in spawning on its own default is the same leak. The Codex and Copilot OpenRouter wrappers set both; see [Other harnesses](tool-configs/other-harnesses.md). Claude Code pins its root and subagent defaults through its dedicated wrapper environment.
| Pi | none available | No hook system; profiles are the only lever |

The gate fails open on every unknown harness, agent, or tool: a missing projection or an unbound agent leaves the call exactly as the model wrote it.

Two loaders had to be unblocked before any of this could land. Codex agent files are inert without a matching `[agents.<name>] config_file` entry in `private_config.*.toml`, so the profile set and the config table are one change. Pi aborts every session with `Cannot find module 'yaml'` when an unmanaged clone shadows the managed yarn install of `pi-subagents`, which is why its extensions directory is `exact_extensions` and an invariant asserts the non-exact path stays absent. Cursor's `cursor-agent` never scans `~/.cursor/agents` in either print or interactive mode, so tiering there rides the hook over the built-in agents.

### Review-flow roles

The categories above cover general work. The [`/k-deep-review`](reviews/deep-review-topology.md) flow has role stages with model needs distinct from the general taxonomy:

| Stage                        | What it does                                                                                                                                                                           | Model tier                                                                                                                       | Placement                                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Review (angle-lane)**      | Bounded reviewer roster: one sighted lane for simple single-surface diffs and extra lanes only for scope-evidenced independent risk                                                    | Registry lane model from `agent_review_models.<harness>.lanes`; Claude may use `inherit` as its degraded/session-model exception | Subagent, one per selected angle; concurrent only when multiple lanes apply                    |
| **Findings audit**           | Dedup/audit candidate findings after live UI or explicit live-UI skip; inlined when trivial, delegated to `findings-auditor` when non-trivial                                          | Top-tier                                                                                                                         | Subagent when non-trivial (2+ findings, HIGH/CRITICAL, lane disagreement); inline when trivial |
| **Adversarial verification** | The one lane where model identity is deliberately pinned — refutes audited candidate findings, preferring a different model **family** than the lane/session model at equal capability | Top-tier; prefer cross-family from the lane model; harnesses with no second family report `families=same (degraded)`             | Subagent, isolated read-only                                                                   |
| **Post-act verification**    | Fix-diff re-review after edits land — the flow's "re-review," there is no separately named re-review stage                                                                             | Top-tier                                                                                                                         | Main/orchestrating session (fix-authorized, runs quality gates + Post-Review Stage)            |

## Per-harness picks

Every harness names models differently and sets effort differently — there is no universal spelling or universal mechanism. When calibrating a harness, verify the model exists in that harness's real catalog/whitelist and pick the first working model from the preference order (do not mass-assign ids across harnesses). The table below is the calibrated default; `home/.chezmoidata/ai_models/tiering.yaml`'s `model_bands` section is the source of truth if this page and the registry ever drift.

**Effort-setting mechanism per harness** (confirmed live, 2026-07-27):

| Harness     | Mechanism                                                                                                                                               | Evidence                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Cursor      | Baked into the model-ID suffix (`gpt-5.6-terra-high`, `glm-5.3-high`)                                                                                   | `cursor-agent models` live catalog                                                                          |
| Claude Code | Separate `--effort <level>` flag (`low, medium, high, xhigh, max`), model ID stays plain                                                                | `claude --help`; live-tested `claude --model sonnet --effort max`                                           |
| Copilot CLI | Separate `--effort`/`--reasoning-effort <level>` flag (`none, minimal, low, medium, high, xhigh, max`)                                                  | `copilot --help`; live-tested `copilot --model gpt-5.6-terra --effort medium`                               |
| Codex CLI   | `-c model_reasoning_effort=<level>` config override, no dedicated flag                                                                                  | `codex --help`; live-tested `codex exec -m gpt-5.6-terra` (model accepted, only hit an unrelated spend cap) |
| Pi          | `--thinking <level>` or model-string suffix (`provider/model:<thinking>`); subagents carry `model` strings, not a separate thinking field               | `pi --help`; installed Pi 0.82.1 and `pi-subagents` 0.37.0 source; safe resolver probes                     |
| OMP         | Profile frontmatter `model` string; repo registry uses provider-qualified IDs plus `:<thinking>` suffix for pinned profiles                             | `home/.chezmoidata/ai_models/tiering.yaml`; `.omp/agent/agents/*.md` templates                              |
| Antigravity | Separate root-session `--effort <low \| medium \| high>` flag; dynamic subagents accept the abstract `inherit \| flash_lite \| flash \| pro` model tier | `agy 1.1.16 --help`; live `/model` and installed `invoke_subagent` schema probes on 2026-08-20              |

Do not assume one mechanism works across harnesses — a suffix that means "max effort" in Cursor is not a valid model ID anywhere else.

**Where "high effort, non-thinking" is actually reachable** (verified 2026-08-01):

| Harness     | Reachable? | Why                                                                                                                                      |
| ----------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Cursor      | yes        | Effort and thinking are separate ID families: `claude-sonnet-5-high` vs `claude-sonnet-5-thinking-high`                                  |
| Copilot CLI | yes        | `COPILOT_DISABLE_ANTHROPIC_THINKING=1` suppresses the thinking budget while reasoning effort still ships; set by the `,copilot` launcher |
| Claude Code | yes        | `alwaysThinkingEnabled: false` in `settings.json` yields `thinking: {type:"disabled"}` on first-party; already set in both profiles      |
| Pi / OMP    | no         | One dial: `:high` is thinking-high and `:off` surrenders the effort level                                                                |
| Codex       | n/a        | OpenAI-only harness, no Opus                                                                                                             |
| Antigravity | n/a        | Google-only harness, no Opus                                                                                                             |

Cursor, Copilot, and Claude Code all reach the combination, by three different mechanisms.

`COPILOT_DISABLE_ANTHROPIC_THINKING` is undocumented — `copilot help environment` does not list it. It is real in 1.0.77: `Q3e()` injects `copilotDisableAnthropicThinkingEnv: process.env.COPILOT_DISABLE_ANTHROPIC_THINKING` into the options passed to `nativeModelClientDefaultOptionsJson`, whose result carries `thinkingBudget`. Reasoning effort travels a separate path (`supportedReasoningEfforts` / `reasoningPickerType: "effort"`), so `effortLevel: high` is still sent as `reasoning_effort` with thinking suppressed. Verifying this needs the real bundle: the shipped binary is a Node SEA whose payload is a gzipped tar in the `NODE_SEA` segment, so plain `strings` on it finds nothing, and `~/.copilot/pkg` may hold only an older extracted version.

Claude Code turns thinking off through the settings file, not an env var, and the chain is visible in the 2.1.220 binary. `Hye()` returns `false` when `alwaysThinkingEnabled === false`, which makes `thinkingConfig` resolve to `{type:"disabled"}` rather than `{type:"adaptive"}`, and the request builder then sends `thinking: {type:"disabled"}` under `r.type==="disabled" && xn()==="firstParty" && !bn`. Both `settings.personal.json` and `settings.work.json` already set `alwaysThinkingEnabled: false`, so the max-band Opus 5 pick is genuinely non-thinking on the native route. That guard keys on the settings flag, not on the model id, so it holds across a band model change.

Two conditions in that guard are easy to break. `xn()==="firstParty"` means the guarantee holds only on the native Anthropic route; a gateway route such as `,claude-openrouter` falls through to omitting the parameter, and adaptive-reasoning models may still think. `!bn` means `CLAUDE_CODE_DISABLE_THINKING=1` _defeats_ the hard disable rather than reinforcing it — it forces the omit path. It is correct in `,claude-openrouter`, whose route is not first-party, but it must never be set for a native session.

The env var that does not help is `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`: it is gated to `f.includes("opus-4-6") || f.includes("sonnet-4-6")`, so it never applies to Opus 5. `alwaysThinkingEnabled: false` is the lever that does.

### Claude Code

| Band               | Model            | Effort | Thinking | Context |
| ------------------ | ---------------- | ------ | -------- | ------- |
| cheap              | `claude-fable-5` | low    | off      | short   |
| standard           | `claude-fable-5` | medium | off      | short   |
| max                | `claude-fable-5` | medium | off      | short   |
| counter (on `max`) | none             | —      | —        | —       |

Claude Code cannot take a cross-vendor counter: it accepts only Claude-family selectors, and an unknown id is not remapped — it reaches the API and returns `API model not found`. `refute` therefore resolves to the primary `max` pick and reports `degraded`. Every band runs Fable 5 (user call, 2026-08-05, following the Cursor GPT-5.6 exit): cheap at low effort, standard and max at medium effort. The 2026-08-03 opus-ban exemption for this harness is superseded — Opus and Sonnet are no longer active picks here either. `claude-fable-5` is verified inside the installed 2.1.222 bundle and `fable` is a first-class Agent-tool alias there; the API-key route short-circuits on billing before model validation, so a live `-p` probe cannot prove id validity on this machine. `alwaysThinkingEnabled: false` keeps the pick non-thinking. `gpt-5.4-codex` is not in the Anthropic-only catalog, so cheap takes a Claude rather than the cross-harness codex-tier pick.

The gate can only clamp Claude to a family alias (`sonnet`, `opus`, `haiku`, `fable`), not to a full id, so it compares alias _rank_ and acts only when the caller asked for something more capable than the band's. An unqualified `Agent` call is left alone, which keeps the profile's more precise id rather than promoting a cheap-band pick to whatever `ANTHROPIC_DEFAULT_SONNET_MODEL` resolves to. All three bands project to `fable`, so the alias cannot separate any of them — the same collision the two Sonnet bands used to have, and the profile frontmatter is what holds each band.

Spelling matters on this harness alone: Claude Code hyphenates point versions, and its own 404 troubleshooting text names `claude-sonnet-4.6` as the typo for `claude-sonnet-4-6`. Copilot and Cursor use the dotted form for the same model, so the id cannot be normalized across harnesses.

Context stays short: bare `claude-fable-5` is the short-window selector, and the `[1m]` suffix is what would swap it onto the 1M window. Nothing in the tier map asks for it, and `,claude-openrouter` passes bare OpenRouter ids for the same reason.

### Codex

| Band               | Model         | Effort |
| ------------------ | ------------- | ------ |
| cheap              | `gpt-5.6-sol` | xhigh  |
| standard           | `gpt-5.6-sol` | xhigh  |
| max                | `gpt-5.6-sol` | xhigh  |
| counter (on `max`) | none          | —      |

Codex is single-vendor (OpenAI only); there is no cross-family split to make here, so `refute` reports `degraded`. Native Codex 0.147.0 lists `gpt-5.6-sol` with `xhigh` among its supported reasoning levels (`codex debug models --bundled`; native default is `low`). Every Codex band, root profile, and named role therefore pins `gpt-5.6-sol` at xhigh effort (user call 2026-08-14: Sol/xhigh, not Sol/high), and every profile pins `service_tier = "default"`. Codex carries effort per profile as `model_reasoning_effort`, and the gate rewrites both model fields on `spawn_agent`. Codex exposes no context-tier dial, so every band is short by construction.

### Copilot CLI

| Band               | Model               | Effort                                                         |
| ------------------ | ------------------- | -------------------------------------------------------------- |
| cheap              | `gpt-5.4-codex`     | high                                                           |
| standard           | `claude-sonnet-4.6` | high (non-thinking)                                            |
| max                | `gpt-5.6-terra`     | high                                                           |
| counter (on `max`) | `claude-sonnet-4.6` | high (non-thinking via `COPILOT_DISABLE_ANTHROPIC_THINKING=1`) |

Copilot's live 1.0.75 catalog confirms `gpt-5.4-codex` and `claude-opus-5`; `gpt-5.6-terra` is reached through the OpenAI provider. The cost-driven move off opus-5/gpt-5.5 (closed 2026-08-03) puts `gpt-5.6-terra` on the review lanes and `claude-sonnet-4.6` as the cross-family refuter (opus-5 is banned, so sonnet is the cheapest non-banned cross-family pick). Effort is not an agent _frontmatter_ field, but `~/.copilot/settings.json` carries `subagents.agents.<name>.effortLevel`, so per-lane effort is pinnable there. That file is source JSON the merge script reads and the artifact ledger records as a `json-declared` baseline path, so it cannot be a template; `scripts/generate_subagent_models.py` writes it from the band registry instead and an invariant fails when the two drift. Model IDs stay catalog-native: Copilot uses dotted 4.x IDs such as `claude-opus-4.8`, but the Opus 5 ID is `claude-opus-5`.

Copilot is the only harness with a live context dial: `subagents.agents.<name>.contextTier` takes `default` or `long_context`, and every subagent is pinned to `default` under the short-context policy. `explore` is the deployed cheap lane; `task` binds to `implement` and therefore takes the standard band.

### Cursor

| Band               | Model                                                                        | Effort | Context |
| ------------------ | ---------------------------------------------------------------------------- | ------ | ------- |
| cheap              | `cursor-grok-4.6-xhigh`                                                      | xhigh  | short   |
| standard           | `cursor-grok-4.6-xhigh`                                                      | xhigh  | short   |
| max                | `cursor-grok-4.6-xhigh`                                                      | xhigh  | short   |
| counter (on `max`) | none — verifier follows the band (single-model policy, user call 2026-08-14) | —      | —       |

Cursor's bands are read by the gate alone, because `cursor-agent` does not discover home-level agent files. That matters for which ids are legal: the `Task` tool takes a far narrower whitelist than the ids `cursor-agent models` lists. The live Task enum in Cursor IDE on 2026-08-14 is `claude-fable-5-medium`, `claude-opus-5-high`, `claude-sonnet-5-thinking-max`, `composer-2.8`, `composer-2.8-fast`, `cursor-grok-4.5-high-fast`, `cursor-grok-4.6-xhigh`, `gpt-5.6-sol-xhigh`, and `gpt-5.6-terra-xhigh`. Anything else fails the spawn with `Invalid model selection`. An invariant pins the bands to that list. User call 2026-08-14: every Cursor band and both review-lane roles run `cursor-grok-4.6-xhigh`, replacing `gpt-5.6-terra-max` / cheap `composer-2.8`, so the Cursor harness matches the personal OMP pin. `claude-fable-5-low`/`claude-fable-5-max` and kimi-k3 are sellable to a Cursor main session but absent from the whitelist, so they cannot be subagent picks. No band names `composer-2.8-fast`: Cursor prices Composer 2.8 at $0.5/$2.8 and describes the fast variant as "A faster variant with the same intelligence" at $3/M input and $15/M output, so `-fast` buys speed at 6x, never a cheaper rung. An invariant keeps `-fast` ids out of every band.

The cost-driven ban (closed 2026-08-03) moved the lanes off `claude-opus-5-high`, which is what had made the lane/verifier pairing cross-family. GPT-5.6 left Cursor on 2026-08-05, returned on 2026-08-07, and was replaced by Grok 4.6 Extra High on 2026-08-14 (all user calls): both review-lane roles are now `cursor-grok-4.6-xhigh`, `max` carries no counter, and refutation is `families=same (reduced independence)` — a deliberate single-model policy: report it, never present it as a cross-family pass.

`cursor-grok-4.6-xhigh` is not a 1M-only id in live `cursor-agent models` 2026.08.11-e8db854 ("Cursor Grok 4.6 Extra High"), so the short-context policy holds. The effort/thinking split is a real Cursor id-scheme fact — `claude-fable-5-medium` (plain) and `claude-fable-5-thinking-medium` are distinct, real model IDs — Cursor is the one harness where "non-thinking" is selected by picking a different model ID outright, not a flag, which is why effort rides in the id here.

### Antigravity

| Band               | Model                      | Effort |
| ------------------ | -------------------------- | ------ |
| cheap              | `gemini-3.7-flash`         | high   |
| standard / max     | `gemini-3.7-flash`         | high   |
| counter (on `max`) | none — Google-only catalog | —      |

Google-only catalog, so cheap, standard, and max collapse to `gemini-3.7-flash` with high effort. The `,ai` launcher reads the generated `agent-bands.v1.json` default and passes `--model gemini-3.7-flash --effort high`; Antigravity resolves that pair to `gemini-3.7-flash-high`. An explicit effort-suffixed model may accompany `--depth` only when both select the same effort; the launcher rejects a conflict before invocation. Dynamic review subagents expose only abstract model tiers, so `agent_review_models.gemini.{lanes,verifier}` stores `pro` and the controller passes it to `invoke_subagent`.

### Pi

| Band               | Model                                            | Effort |
| ------------------ | ------------------------------------------------ | ------ |
| cheap              | `openrouter/deepseek/deepseek-v4-flash-0731:max` | max    |
| standard           | `openrouter/deepseek/deepseek-v4-flash-0731:max` | max    |
| max                | `openrouter/deepseek/deepseek-v4-flash-0731:max` | max    |
| counter (on `max`) | `openrouter/openai/gpt-5.6-terra:max`            | max    |

DeepSeek max carries every Pi primary band with FP8-or-higher quantization, a 24 t/s preferred floor, and no `sort` so OpenRouter's default load balancer keeps uptime. Kimi remains selectable only on Fireworks, Together, and BaseTen under a $16/M completion cap; the counter stays `gpt-5.6-terra:max`, so lanes vs counter remain cross-family.

Pi has no hook system, so profiles are the only lever and the gate never runs there. Pi's default model/thinking is config-file based, but Pi also supports `--model`, `--thinking`, and model strings suffixed with `:<thinking>`. The `,ai` OpenRouter route deliberately rejects those overrides and pins the lane route to `openrouter/deepseek/deepseek-v4-flash-0731` at thinking `max`. `pi-subagents` has per-task/per-agent `model` but no separate per-task `thinking`; use the suffix form `openrouter/deepseek/deepseek-v4-flash-0731:max` for subagent pins. That suffix is a thinking level, not a separate effort dial: `pi-subagents` 0.38.0 parses it with `splitKnownThinkingSuffix` against `THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]` (`src/shared/model-info.ts`), and `@earendil-works/pi-agent-core` declares the same union in `dist/types.d.ts:254`. So `claude-sonnet-5:high` means thinking high, and `off` is the only non-thinking value — Pi cannot express "high effort, non-thinking" because both live on one dial. The `:<level>` suffix is a thinking dial, not a context tier — Pi exposes no context selector, so every row is short by construction.

### OMP

OMP is the one harness with native band indirection, so its bands are spelled as `@role` tokens and [`readonly_config.yml.tmpl`](../../../home/dot_omp/private_agent/readonly_config.yml.tmpl)'s `modelRoles` prices them per profile. That is what lets the repo pin band costs per profile without needing a gate.

| Band               | Token      | Work profile                                                                          | Personal profile               |
| ------------------ | ---------- | ------------------------------------------------------------------------------------- | ------------------------------ |
| cheap              | `@smol`    | `openrouter/deepseek/deepseek-v4-flash-0731:max`                                      | `cursor/composer-2.8:high`     |
| standard           | `@task`    | `openrouter/deepseek/deepseek-v4-flash-0731:max`                                      | `cursor/cursor-grok-4.6-xhigh` |
| max                | `@default` | `openrouter/deepseek/deepseek-v4-flash-0731:max`                                      | `cursor/cursor-grok-4.6-xhigh` |
| counter (on `max`) | —          | — (no counter: advisor resolves to the lanes' own model on both profiles, 2026-08-06) | —                              |

Verified on 17.2.4: a profile carrying `model: "@smol"` runs on `modelRoles.smol`, and an unknown token fails loudly with `Error: No model selected.` rather than falling back. Provider and model are separated by `/`, never `:` — `cursor:` parses as a bogus provider. Like Pi, OMP's `:<level>` suffix is a single thinking dial the runtime maps straight onto `reasoning`, so "high effort, non-thinking" is not expressible here. Work routes primary roles through OpenRouter `deepseek/deepseek-v4-flash-0731:max` and keeps `vision` on `openrouter/moonshotai/kimi-k3:high`; personal pins primary roles to Cursor `cursor-grok-4.6-xhigh`, uses `composer-2.8` for `smol`, and uses Cursor `cursor-grok-4.6-xhigh` for `vision`.

`modelRoles.advisor` resolves to the lanes' own model on both profiles — OpenRouter DeepSeek max on work, Cursor Grok 4.6 Extra High on personal — and the advisor is enabled for primary turns and spawned agents. Review lanes and verifier both resolve `@default` (same-family per profile). An invariant asserts OMP carries a counter whenever any profile's `advisor` differs from `default`, so moving cross-family refutation means repricing the role first, not editing the band.

## Native subagent takeover risk

Every harness that can spawn subagents has its own **native** default model for that path — separate from anything this repo's registry declares — and an unpinned harness silently falls back to whatever that native default is. This is the risk this taxonomy exists to close, not just document. `agent_bindings` therefore lists built-in names (Copilot's `explore`, Codex's `worker`, Antigravity's `generalist`, Cursor's `generalPurpose`) next to the repo-authored profiles, and the gate covers the call sites that no profile can reach.

| Harness         | Takeover risk                                                                                                                                                                                                         | Status                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cursor**      | Omitted/default Cursor subagents are unsafe: local CLI shows `auto`, and user-verified expenditure data shows Cursor-served defaults can resolve to `composer-2.8-fast`                                               | **Mitigated by the gate**, which is the only mechanism available: `cursor-agent` does not read `~/.cursor/agents`, and same-name profiles cannot shadow native enum agents in a workspace either. The `preToolUse` hook rewrites `Task.model` for every bound `subagent_type`, within the Task tool's own model whitelist. Cursor `worker`/cloud `requested_models` omission remains an open risk unless launched with explicit models. |
| **Codex**       | `multi_agent` `spawn_agent`/`wait`; omitted models fall back to native/default metadata that is not auditable enough for this policy                                                                                  | **Mitigated** — Codex profiles carry an explicit `model` plus `model_reasoning_effort`, each registered through an `[agents.<name>] config_file` entry, and the `spawn_agent` gate rewrites both fields when a call omits or overrides them.                                                                                                                                                                                            |
| **Copilot CLI** | `--agent` flag, `subagents.agents.*` config; stale target-only nested settings can otherwise preserve old model overrides                                                                                             | **Mitigated** — profile frontmatter and generated `~/.copilot/settings.json` subagent entries both pin registry-aligned models, and the `agent-memory` extension's `onPreToolUse` returns `modifiedArgs` for the `task` tool.                                                                                                                                                                                                           |
| **Claude Code** | `Task` tool w/ `subagent_type`, embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`), plus a separate `claude agents`/background-agent surface with its own `--model` default flag | **Mitigated for the OpenRouter route**: repo-owned same-name profiles shadow high-risk builtins, and `,claude-openrouter` pins `CLAUDE_CODE_SUBAGENT_MODEL`, all family defaults, and root invocation to `deepseek/deepseek-v4-flash-0731@preset/effort-max`.                                                                                                                                                                           |
| **Antigravity** | Dynamic `define_subagent` / `invoke_subagent`; omitted model tiers inherit the parent/default route                                                                                                                   | **Mitigated by controller instructions** — review roles are defined from the shared role contracts and invoked with the registry's `pro` tier. Antigravity exposes no global per-role profile files or pre-delegation model-rewrite hook.                                                                                                                                                                                               |
| **Pi**          | `~/.pi/agent/agents/*.md`; subagent runner accepts model strings and encodes thinking as a suffix                                                                                                                     | **Mitigated for repo-owned profiles** — Pi profiles render from `model_bands`/`agent_review_models`; lanes use `openrouter/deepseek/deepseek-v4-flash-0731:max` and the verifier `openrouter/openai/gpt-5.6-terra:max`. Pi has no hook, so future profiles must either pin `model` or document why they intentionally use `defaultProvider`/`defaultModel`.                                                                             |
| **OMP**         | `~/.omp/agent/agents/*.md`; omitted profile models can fall back to the harness's native subagent default outside the repo registry                                                                                   | **Mitigated for repo-owned profiles** — OMP profiles carry `@role` tokens resolved by `modelRoles`, so both profiles price the same bands. Future profiles must either pin `model` or document why they intentionally use the native default.                                                                                                                                                                                           |

## Related

- [Subagents](subagents.md) — cross-harness subagent discovery and profile topology
- [Model registry & routing](model-registry.md) — the underlying `.chezmoidata/ai_models/` sections and generators
- [Scenarios](scenarios.md) — when to reach for which skill/flow; this page's buckets refine that page's "smallest flow that fits" default with model/placement specifics
