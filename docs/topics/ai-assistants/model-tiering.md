---
sidebar_position: 5
---

# Model tiering

Which model/effort a task should run on, and whether that task belongs inline in the orchestrating session or in a dedicated subagent, are the same decision. This page is the taxonomy that decision uses, the per-harness picks it resolves to, and the native-subagent-takeover risks that can silently bypass it.

Canonical data lives in [`home/.chezmoidata/ai_models/tiering.yaml`](../../../home/.chezmoidata/ai_models/tiering.yaml), split across portable routing tables, per-harness category rows, and sparse review overrides:

| Table                    | Dimension   | Says                                                                                   |
| ------------------------ | ----------- | -------------------------------------------------------------------------------------- |
| `agent_categories`       | portable    | What a kind of work means: `{family, contract}` for each category                      |
| `agent_bindings`         | portable    | Which category each delegable agent name belongs to, built-ins included                |
| `category_models`        | per harness | What each category resolves to in that harness, including verifier status for `refute` |
| `review_model_overrides` | per harness | Only non-derivable review selectors such as Claude `inherit` and Antigravity `pro`     |

Whether a findings audit needs review-grade reasoning is a fact about the job, not about Copilot; only `category_models` knows Codex's catalog. Merging the two is what made the previous single `model_tier_map` need 57 rows to carry roughly 21 facts. Categories are chosen before the model: the SOP delegation section and the `k-*` skills name a category, and then `category_models` resolves that category to a harness-native id.

**Categories are the routing unit.** Cost labels such as `cheap`/`standard`/`max` collapsed distinct risks: exact lookup, deterministic edits, semantic investigation, implementation, orchestration, review, and refutation are different jobs. The matrix prices each category explicitly per harness.

**Two standing policies keep the option space small.** Every category runs short context unless the harness publishes no short variant of the wanted model, and `lookup` is exact retrieval only rather than semantic discovery. Copilot uses `gpt-5.5`/xhigh for every category except mechanical (`claude-sonnet-4.6`/high) and refute (`claude-fable-5`/high). Cursor mirrors that shape only where its Task enum can spawn the id: primary categories use `gpt-5.6-sol-xhigh`, mechanical uses `cursor-grok-4.6-xhigh`, and refute uses `claude-opus-5-high`. Antigravity uses `gemini-3.1-pro-preview` long-context categories except mechanical, which stays on `gemini-3.7-flash`; Claude Code and Antigravity keep single-vendor picks, and native Codex deliberately uses `gpt-5.4`/high for mechanical while every other category uses `gpt-5.5`/xhigh.

## Categories

Classification is example-anchored judgment, not a countable metric. Each category names the kind of work, the evidence contract, and whether the work belongs inline in the orchestrating session or delegated.

| Category      | Contract                 | Example tasks                                                                            | Placement                                                                                                                                         |
| ------------- | ------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lookup`      | Exact retrieval          | Read `--help`, list caller-scoped files, return raw pointers without choosing importance | Delegate only when scoped by a stronger caller                                                                                                    |
| `mechanical`  | Deterministic edit       | Rename across files, apply a settled pattern                                             | Delegate                                                                                                                                          |
| `research`    | Evidence synthesis       | Find the important code path, run SCSI/base-context gathering, inspect public source     | Delegate                                                                                                                                          |
| `implement`   | Implementation           | Add a function, wire a pattern into a new call site                                      | Inline, or delegated when the edit is large or isolated enough to benefit from a fresh context                                                    |
| `orchestrate` | Orchestration            | Session default: decide what to delegate, judge what comes back, resolve ambiguity       | Stays in the main session — ambiguity resolution is not delegable without losing the context needed to do it                                      |
| `review`      | Review                   | Review a change and audit findings                                                       | Delegate to a review lane                                                                                                                         |
| `refute`      | Adversarial verification | Break a conclusion: adversarial verification, criteria refutation, blind clarity         | Delegate; prefer a **different model family** than the lane being refuted at equal capability — capability outranks diversity (`family: counter`) |

`general-purpose` is bound to `implement`, not `lookup`, despite being the cheapest thing to reach for: it carries `tools: "*"` and is the only delegated agent that can edit anything.

`lookup` returns candidate pointers, not conclusions. Anything that discovers relevance, chooses symbols, or reports an architecture/root-cause judgment is `research`.

Only `refute` is `family: counter`. Same-family reviewers inherit the same blind spots and the same context contamination, so prefer the counter at equal capability — capability outranks family diversity (SOP §3.7). Where a harness cannot field a second family, resolution reports `degraded` rather than presenting the weaker pass as a real cross-family one.

The orchestrating session is always the one deciding which category a piece of work falls into and whether to delegate — it is the driver, subagents are dispatched, not the other way around.

### Enforcement

The category pick reaches a delegated run by two paths, and both are needed:

1. **Profiles declare it where the harness supports profiles.** [`home/.chezmoitemplates/agent-model.partial`](../../../home/.chezmoitemplates/agent-model.partial) resolves `agent → category → model` at apply time, so each agent file under `dot_<harness>/exact_agents/` renders a concrete id. Copilot has no per-agent files for its built-ins, so [`scripts/generate_subagent_models.py`](../../../scripts/generate_subagent_models.py) writes `subagents.agents.*` from the same registry. Antigravity uses runtime-defined subagents instead, with the registry's supported `pro` selector passed to `invoke_subagent`.
2. **A hook makes it non-negotiable per call.** [`band_gate.py`](../../../home/exact_dot_agents/exact_hooks/executable_band_gate.py) runs pre-tool-use, reads the projection that [`scripts/generate_agent_bands.py`](../../../scripts/generate_agent_bands.py) emits to `~/.config/ai/agent-bands.v1.json`, and rewrites the delegation payload. Each harness has its own request and response shape, all verified against the running binaries.

| Harness     | Gate wiring                                                           | What it rewrites                                                                                                                          |
| ----------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Codex       | `PreToolUse` matcher `spawn_agent` in `hooks.json.tmpl`               | `model` + `reasoning_effort`; `updatedInput` is dropped unless `permissionDecision: "allow"` rides along                                  |
| Cursor      | `preToolUse` in `hooks.json`                                          | `Task.model` — `updated_input` replaces the whole input object, so the gate echoes every other field                                      |
| Claude Code | `PreToolUse` matcher `Agent\|Task` in `settings.{work,personal}.json` | The family alias; native Claude leaves unqualified calls on profile ids, while backend-wrapper schema inheritance forces the mapped alias |
| Copilot     | `onPreToolUse` in the `agent-memory` extension                        | `modifiedArgs.model` + `reasoning_effort`; Copilot hands `toolArgs` over JSON-encoded, so the gate parses a string first                  |
| Antigravity | none                                                                  | Dynamic `invoke_subagent` calls receive the registry's abstract `pro` model tier directly                                                 |
| Pi          | none available                                                        | No hook system; profiles are the only lever                                                                                               |
| OMP         | none needed                                                           | Category rows are `@role` tokens that `modelRoles` resolves natively                                                                      |

Backend wrappers keep the frontend adapter but can inherit a backend matrix with `AGENT_BAND_SCHEMA_HARNESS`: `*-copilot` reads `category_models.copilot`, `*-codex` reads `category_models.codex`, and `*-openrouter` reads `category_models.pi` as the closest OpenRouter-compatible schema. OpenRouter wrappers also set `AGENT_BAND_MODEL_FORMAT=openrouter-preset`, so rows such as `openrouter/openai/gpt-5.5:xhigh` become `openai/gpt-5.5@preset/effort-xhigh` before they reach Claude, Codex, Copilot, or Cursor. The older `AGENT_BAND_MODEL_OVERRIDE`/`AGENT_BAND_EFFORT_OVERRIDE` path still exists for a true single-model route and reaches agents with no binding.

The gate fails open on every unknown harness, agent, or tool: a missing projection or an unbound agent leaves the call exactly as the model wrote it.

Two loaders had to be unblocked before any of this could land. Codex agent files are inert without a matching `[agents.<name>] config_file` entry in `private_config.*.toml`, so the profile set and the config table are one change. Pi aborts every session with `Cannot find module 'yaml'` when an unmanaged clone shadows the managed yarn install of `pi-subagents`, which is why its extensions directory is `exact_extensions` and an invariant asserts the non-exact path stays absent. Cursor's `cursor-agent` never scans `~/.cursor/agents` in either print or interactive mode, so tiering there rides the hook over the built-in agents.

### Review-flow roles

The categories above cover general work. The [`/k-deep-review`](reviews/deep-review-topology.md) flow has role stages with model needs distinct from the general taxonomy:

| Stage                        | What it does                                                                                                                                                                           | Model tier                                                                                                           | Placement                                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Review (angle-lane)**      | Bounded reviewer roster: one sighted lane for simple single-surface diffs and extra lanes only for scope-evidenced independent risk                                                    | `resolve_review_agent_model`: `review` category by default, sparse override for Claude `inherit` / Antigravity `pro` | Subagent, one per selected angle; concurrent only when multiple lanes apply                    |
| **Findings audit**           | Dedup/audit candidate findings after live UI or explicit live-UI skip; inlined when trivial, delegated to `findings-auditor` when non-trivial                                          | Top-tier                                                                                                             | Subagent when non-trivial (2+ findings, HIGH/CRITICAL, lane disagreement); inline when trivial |
| **Adversarial verification** | The one lane where model identity is deliberately pinned — refutes audited candidate findings, preferring a different model **family** than the lane/session model at equal capability | Top-tier; prefer cross-family from the lane model; harnesses with no second family report `families=same (degraded)` | Subagent, isolated read-only                                                                   |
| **Post-act verification**    | Fix-diff re-review after edits land — the flow's "re-review," there is no separately named re-review stage                                                                             | Top-tier                                                                                                             | Main/orchestrating session (fix-authorized, runs quality gates + Post-Review Stage)            |

## Per-harness picks

Every harness names models differently and sets effort differently — there is no universal spelling or universal mechanism. When calibrating a harness, verify the model exists in that harness's real catalog/whitelist and pick the first working model from the preference order (do not mass-assign ids across harnesses). The table below is the calibrated default; `home/.chezmoidata/ai_models/tiering.yaml`'s `category_models` section is the source of truth if this page and the registry ever drift.

**Effort-setting mechanism per harness** (confirmed live, 2026-07-27):

| Harness     | Mechanism                                                                                                                                               | Evidence                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Cursor      | Baked into the model-ID suffix (`gpt-5.6-terra-high`, `glm-5.3-high`)                                                                                   | `cursor-agent models` live catalog                                                                          |
| Claude Code | Separate `--effort <level>` flag (`low, medium, high, xhigh, max`), model ID stays plain                                                                | `claude --help`; live-tested `claude --model sonnet --effort max`                                           |
| Copilot CLI | Separate `--effort`/`--reasoning-effort <level>` flag (`none, minimal, low, medium, high, xhigh, max`)                                                  | `copilot --help` on Copilot CLI 1.0.80                                                                      |
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

Claude Code turns thinking off through the settings file, not an env var, and the chain is visible in the 2.1.220 binary. `Hye()` returns `false` when `alwaysThinkingEnabled === false`, which makes `thinkingConfig` resolve to `{type:"disabled"}` rather than `{type:"adaptive"}`, and the request builder then sends `thinking: {type:"disabled"}` under `r.type==="disabled" && xn()==="firstParty" && !bn`. Both `settings.personal.json` and `settings.work.json` already set `alwaysThinkingEnabled: false`, so conclusion-forming Fable 5 categories are genuinely non-thinking on the native route. That guard keys on the settings flag, not on the model id, so it holds across a category model change.

Two conditions in that guard are easy to break. `xn()==="firstParty"` means the guarantee holds only on the native Anthropic route; a gateway route such as `,claude-openrouter` falls through to omitting the parameter, and adaptive-reasoning models may still think. `!bn` means `CLAUDE_CODE_DISABLE_THINKING=1` _defeats_ the hard disable rather than reinforcing it — it forces the omit path. It is correct in `,claude-openrouter`, whose route is not first-party, but it must never be set for a native session.

The env var that does not help is `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`: it is gated to `f.includes("opus-4-6") || f.includes("sonnet-4-6")`, so it never applies to Opus 5. `alwaysThinkingEnabled: false` is the lever that does.

### Claude Code

| Category                                         | Model               | Effort | Thinking | Context | Verifier status |
| ------------------------------------------------ | ------------------- | ------ | -------- | ------- | --------------- |
| `lookup`                                         | `claude-fable-5`    | low    | off      | short   | —               |
| `mechanical`                                     | `claude-sonnet-4-6` | high   | off      | short   | —               |
| `research`, `implement`, `orchestrate`, `review` | `claude-fable-5`    | medium | off      | short   | —               |
| `refute`                                         | `claude-fable-5`    | medium | off      | short   | degraded        |

Claude Code cannot take a cross-vendor counter: it accepts only Claude-family selectors, and an unknown id is not remapped — it reaches the API and returns `API model not found`. `refute` therefore resolves to Fable 5 and reports `degraded`. Fable 5 carries lookup and conclusion-forming categories (user call, 2026-08-05, following the Cursor GPT-5.6 exit); mechanical work uses Claude Sonnet 4.6 at high effort. The Claude Code selector is `claude-sonnet-4-6`, while Copilot uses dotted `claude-sonnet-4.6`. The 2026-08-03 opus-ban exemption for this harness is superseded — Opus is no longer an active pick here. `claude-fable-5` is verified inside the installed 2.1.222 bundle and `fable` is a first-class Agent-tool alias there; the API-key route short-circuits on billing before model validation, so a live `-p` probe cannot prove id validity on this machine. `alwaysThinkingEnabled: false` keeps the pick non-thinking.

The gate can only clamp Claude to a family alias (`sonnet`, `opus`, `haiku`, `fable`), not to a full id, so it compares alias _rank_ and acts only when the caller asked for something more capable than the category's alias. An unqualified `Agent` call is left alone, which keeps the profile's more precise id rather than promoting a category pick to whatever `ANTHROPIC_DEFAULT_SONNET_MODEL` resolves to.

Spelling matters on this harness alone: Claude Code hyphenates point versions, and its own 404 troubleshooting text names `claude-sonnet-4.6` as the typo for `claude-sonnet-4-6`. Copilot and Cursor use the dotted form for the same model, so the id cannot be normalized across harnesses.

Context stays short: bare `claude-fable-5` is the short-window selector, and the `[1m]` suffix is what would swap it onto the 1M window. Nothing in the category matrix asks for it, and `,claude-openrouter` passes bare OpenRouter ids for the same reason.

### Codex

| Category                                                             | Model     | Effort | Verifier status    |
| -------------------------------------------------------------------- | --------- | ------ | ------------------ |
| `mechanical`                                                         | `gpt-5.4` | high   | —                  |
| `lookup`, `research`, `implement`, `orchestrate`, `review`, `refute` | `gpt-5.5` | xhigh  | `refute`: degraded |

Codex is single-vendor (OpenAI only); there is no cross-family split to make here, so `refute` reports `degraded`. Native Codex 0.149.0 lists `gpt-5.5` with `xhigh` and `gpt-5.4` with `high` among supported reasoning levels (`codex debug models --bundled`; native default is `low`). The bundled `gpt-5.4` row is hidden and carries an upgrade note to `gpt-5.6-terra`; `mechanical` still uses it as deliberate user policy. Every other Codex category, root profile, and named role pins `gpt-5.5` at xhigh effort (user call 2026-08-24), and every profile pins `service_tier = "default"`. Codex carries effort per profile as `model_reasoning_effort`, and the gate rewrites both model fields on `spawn_agent`. Codex exposes no context-tier dial, so every category is short by construction.

### Copilot CLI

| Category                                                   | Model               | Effort                                                         | Verifier status |
| ---------------------------------------------------------- | ------------------- | -------------------------------------------------------------- | --------------- |
| `lookup`, `research`, `implement`, `orchestrate`, `review` | `gpt-5.5`           | xhigh                                                          | —               |
| `mechanical`                                               | `claude-sonnet-4.6` | high (non-thinking via `COPILOT_DISABLE_ANTHROPIC_THINKING=1`) | —               |
| `refute`                                                   | `claude-fable-5`    | high (non-thinking via `COPILOT_DISABLE_ANTHROPIC_THINKING=1`) | cross_family    |

Copilot's captured catalog includes `gpt-5.5`, `claude-sonnet-4.6`, and `claude-fable-5`; Copilot CLI 1.0.80 accepts `xhigh` as a reasoning effort. User call 2026-08-24: Copilot defaults categories to `gpt-5.5`/xhigh, with `mechanical` on `claude-sonnet-4.6`/high and `refute` on `claude-fable-5`/high. Effort is not an agent _frontmatter_ field, but `~/.copilot/settings.json` carries `subagents.agents.<name>.effortLevel`, so per-lane effort is pinnable there. That file is source JSON the merge script reads and the artifact ledger records as a `json-declared` baseline path, so it cannot be a template; `scripts/generate_subagent_models.py` writes it from the category registry instead and an invariant fails when the two drift. Model IDs stay catalog-native: Copilot uses dotted 4.x IDs such as `claude-opus-4.8`, but the Opus 5 ID is `claude-opus-5`.

Copilot is the only harness with a live context dial: `subagents.agents.<name>.contextTier` takes `default` or `long_context`, and every subagent is pinned to `default` under the short-context policy. `explore` binds to `research`; `task` binds to `implement`.

### Cursor

| Category                                                   | Model                   | Effort | Context | Verifier status |
| ---------------------------------------------------------- | ----------------------- | ------ | ------- | --------------- |
| `lookup`, `research`, `implement`, `orchestrate`, `review` | `gpt-5.6-sol-xhigh`     | xhigh  | long    | —               |
| `mechanical`                                               | `cursor-grok-4.6-xhigh` | xhigh  | short   | —               |
| `refute`                                                   | `claude-opus-5-high`    | high   | long    | cross_family    |

Cursor's categories are read by the gate alone, because `cursor-agent` does not discover home-level agent files. That matters for which ids are legal: the `Task` tool has historically taken a far narrower whitelist than the ids `cursor-agent models` lists. The captured Task enum in Cursor IDE on 2026-08-14 includes `gpt-5.6-sol-xhigh`, `cursor-grok-4.6-xhigh`, and `claude-opus-5-high`; category rows stay inside that list while the live Task enum is not locally inspectable. No category names `composer-2.8-fast`: Cursor prices Composer 2.8 at $0.5/$2.8 and describes the fast variant as "A faster variant with the same intelligence" at $3/M input and $15/M output, so `-fast` buys speed at 6x, never a cheaper rung. An invariant keeps `-fast` ids out of every category.

User call 2026-08-24: Cursor mirrors Copilot's category shape on spawnable Cursor-native ids. Primary categories run GPT-5.6 SOL Extra High, mechanical stays on Cursor Grok 4.6 Extra High, and refute runs Opus 5 High, so review-vs-refute is cross-family again. The primary/refute rows use long-context Task ids; `cursor-grok-4.6-xhigh` is not a 1M-only id ("Cursor Grok 4.6 Extra High"), so mechanical stays short. The effort/thinking split is a real Cursor id-scheme fact — `claude-opus-5-high` (plain) and `claude-opus-5-thinking-high` are distinct, real model IDs — Cursor is the one harness where "non-thinking" is selected by picking a different model ID outright, not a flag.

### Antigravity

| Category                                                             | Model                    | Effort | Context | Verifier status    |
| -------------------------------------------------------------------- | ------------------------ | ------ | ------- | ------------------ |
| `lookup`, `research`, `implement`, `orchestrate`, `review`, `refute` | `gemini-3.1-pro-preview` | high   | long    | `refute`: degraded |
| `mechanical`                                                         | `gemini-3.7-flash`       | high   | long    | —                  |

Google-only catalog, so `refute` reports `degraded`: there is no second family inside Antigravity. User call 2026-08-24: use Gemini 3.1 Pro with long context everywhere except mechanical, which stays on Gemini 3.7 Flash and also requests long context. Antigravity 1.1.18 exposes Gemini 3.1 Pro as the selector `gemini-3.1-pro-preview` in `agy models`. The `,ai` launcher reads the generated `agent-bands.v1.json` default and passes `--model gemini-3.1-pro-preview --effort high`; dynamic review subagents expose only abstract model tiers, so `review_model_overrides.gemini.{lanes,verifier}` stores `pro` and the controller passes it to `invoke_subagent`.

### Pi

| Category                                                   | Model                                          | Effort | Verifier status |
| ---------------------------------------------------------- | ---------------------------------------------- | ------ | --------------- |
| `lookup`, `research`, `implement`, `orchestrate`, `review` | `openrouter/openai/gpt-5.5:xhigh`              | xhigh  | —               |
| `mechanical`                                               | `openrouter/deepseek/deepseek-v4-flash:xhigh`  | xhigh  | —               |
| `refute`                                                   | `openrouter/anthropic/claude-sonnet-4.6:xhigh` | xhigh  | cross_family    |

User call 2026-08-24: Pi runs primary categories on OpenRouter GPT-5.5 at xhigh thinking, keeps mechanical on DeepSeek V4 Flash at xhigh, and moves refute to Claude Sonnet 4.6 at xhigh. Kimi and GLM-5.2 remain selectable Pi models, but they are not category defaults.

Pi has no hook system, so profiles are the only lever and the gate never runs there. Pi's default model/thinking is config-file based, but Pi also supports `--model`, `--thinking`, and model strings suffixed with `:<thinking>`. The `,ai` OpenRouter route reads the generated Pi mirror and pins the recommended route to `openrouter/openai/gpt-5.5` at thinking `xhigh`. `pi-subagents` has per-task/per-agent `model` but no separate per-task `thinking`; use the suffix form `openrouter/openai/gpt-5.5:xhigh` for subagent pins. That suffix is a thinking level, not a separate effort dial: `pi-subagents` 0.38.0 parses it with `splitKnownThinkingSuffix` against `THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]` (`src/shared/model-info.ts`), and `@earendil-works/pi-agent-core` declares the same union in `dist/types.d.ts:254`. So `claude-sonnet-5:high` means thinking high, and `off` is the only non-thinking value — Pi cannot express "high effort, non-thinking" because both live on one dial. The `:<level>` suffix is a thinking dial, not a context tier — Pi exposes no context selector, so every row is short by construction.

### OMP

OMP is the one harness with native role indirection, so category rows are spelled as `@role` tokens and [`readonly_config.yml.tmpl`](../../../home/dot_omp/private_agent/readonly_config.yml.tmpl)'s `modelRoles` prices them per profile. Installed `omp/18.0.3` reports `default`, `smol`, `vision`, `slow`, `plan`, `task`, and `advisor` from `omp config get modelRoles`; the repo uses those role names as local implementation detail, not as the portable taxonomy.

| Category                              | Token      | Work profile                                   | Personal profile                               |
| ------------------------------------- | ---------- | ---------------------------------------------- | ---------------------------------------------- |
| `lookup`                              | `@smol`    | `openrouter/deepseek/deepseek-v4-flash:xhigh`  | `openrouter/deepseek/deepseek-v4-flash:xhigh`  |
| `mechanical`, `research`, `implement` | `@task`    | `openrouter/openai/gpt-5.5:xhigh`              | `openrouter/openai/gpt-5.5:xhigh`              |
| `orchestrate`                         | `@plan`    | `openrouter/openai/gpt-5.5:xhigh`              | `openrouter/openai/gpt-5.5:xhigh`              |
| `review`, `refute`                    | `@advisor` | `openrouter/anthropic/claude-sonnet-4.6:xhigh` | `openrouter/anthropic/claude-sonnet-4.6:xhigh` |

Verified on 17.2.4: a profile carrying `model: "@smol"` runs on `modelRoles.smol`, and an unknown token fails loudly with `Error: No model selected.` rather than falling back. Provider and model are separated by `/`, never `:` — `cursor:` parses as a bogus provider. Like Pi, OMP's `:<level>` suffix is a single thinking dial the runtime maps straight onto `reasoning`, so "high effort, non-thinking" is not expressible here. User call 2026-08-24: both OMP profiles route default/vision/slow/plan/task to OpenRouter GPT-5.5 xhigh, `smol` to DeepSeek V4 Flash xhigh, and `advisor` to Sonnet 4.6 xhigh.

`modelRoles.advisor` is enabled for primary turns and spawned agents. Review and refute both resolve `@advisor` (same-family Sonnet 4.6), and `verifier_status: reduced_independence` makes that reporting explicit.

## Native subagent takeover risk

Every harness that can spawn subagents has its own **native** default model for that path — separate from anything this repo's registry declares — and an unpinned harness silently falls back to whatever that native default is. This is the risk this taxonomy exists to close, not just document. `agent_bindings` therefore lists built-in names (Copilot's `explore`, Codex's `worker`, Antigravity's `generalist`, Cursor's `generalPurpose`) next to the repo-authored profiles, and the gate covers the call sites that no profile can reach.

| Harness         | Takeover risk                                                                                                                                                                                                         | Status                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cursor**      | Omitted/default Cursor subagents are unsafe: local CLI shows `auto`, and user-verified expenditure data shows Cursor-served defaults can resolve to `composer-2.8-fast`                                               | **Mitigated by the gate**, which is the only mechanism available: `cursor-agent` does not read `~/.cursor/agents`, and same-name profiles cannot shadow native enum agents in a workspace either. The `preToolUse` hook rewrites `Task.model` for every bound `subagent_type`, within the Task tool's own model whitelist. Cursor `worker`/cloud `requested_models` omission remains an open risk unless launched with explicit models. |
| **Codex**       | `multi_agent` `spawn_agent`/`wait`; omitted models fall back to native/default metadata that is not auditable enough for this policy                                                                                  | **Mitigated** — Codex profiles carry an explicit `model` plus `model_reasoning_effort`, each registered through an `[agents.<name>] config_file` entry, and the `spawn_agent` gate rewrites both fields when a call omits or overrides them.                                                                                                                                                                                            |
| **Copilot CLI** | `--agent` flag, `subagents.agents.*` config; stale target-only nested settings can otherwise preserve old model overrides                                                                                             | **Mitigated** — profile frontmatter and generated `~/.copilot/settings.json` subagent entries both pin resolver-aligned models, and the `agent-memory` extension's `onPreToolUse` returns `modifiedArgs` for the `task` tool.                                                                                                                                                                                                           |
| **Claude Code** | `Task` tool w/ `subagent_type`, embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`), plus a separate `claude agents`/background-agent surface with its own `--model` default flag | **Mitigated for the OpenRouter route**: repo-owned same-name profiles shadow high-risk builtins, and `,claude-openrouter` maps Pi's OpenRouter backend categories onto Claude aliases whose defaults point to GPT-5.5, DeepSeek V4 Flash, or Sonnet 4.6 preset wire ids. The root invocation remains the selected OpenRouter session model.                                                                                             |
| **Antigravity** | Dynamic `define_subagent` / `invoke_subagent`; omitted model tiers inherit the parent/default route                                                                                                                   | **Mitigated by controller instructions** — review roles are defined from the shared role contracts and invoked with the registry's `pro` tier. Antigravity exposes no global per-role profile files or pre-delegation model-rewrite hook.                                                                                                                                                                                               |
| **Pi**          | `~/.pi/agent/agents/*.md`; subagent runner accepts model strings and encodes thinking as a suffix                                                                                                                     | **Mitigated for repo-owned profiles** — Pi review profiles render through `review-agent-model.partial`; non-review profiles use `agent-model.partial`. Lanes use `category_models.pi.review.model` and the verifier uses `category_models.pi.refute.model`. Pi has no hook, so future profiles must either pin `model` or document why they intentionally use `defaultProvider`/`defaultModel`.                                         |
| **OMP**         | `~/.omp/agent/agents/*.md`; omitted profile models can fall back to the harness's native subagent default outside the repo registry                                                                                   | **Mitigated for repo-owned profiles** — OMP profiles carry `@role` tokens resolved by `modelRoles`, so both profiles price the same categories. Future profiles must either pin `model` or document why they intentionally use the native default.                                                                                                                                                                                      |

## Related

- [Subagents](subagents.md) — cross-harness subagent discovery and profile topology
- [Model registry & routing](model-registry.md) — the underlying `.chezmoidata/ai_models/` sections and generators
- [Scenarios](scenarios.md) — when to reach for which skill/flow; this page's buckets refine that page's "smallest flow that fits" default with model/placement specifics
