---
sidebar_position: 5
---

# Model tiering

Which model/effort a task should run on, and whether that task belongs inline in the orchestrating session or in a dedicated subagent, are the same decision. This page is the taxonomy that decision uses, the per-harness picks it resolves to, and the native-subagent-takeover risks that can silently bypass it.

Canonical data lives in [`home/.chezmoidata/ai_models.yaml`](../../../home/.chezmoidata/ai_models.yaml)'s `model_tier_map` section, the same [`agent_review_models`](model-registry.md) pattern already proven for `/k-deep-review` lanes.

**How much of it is wired.** Only 12 of the 57 rows are read by a chezmoi template: `claude_code`'s `gruntwork`, `routine_edit`, and `orchestration_{personal,work}`, plus `gruntwork`, `routine_edit`, `review`, and `post_act_verification` on Pi and OMP. Cursor, Codex, Copilot, and Gemini read nothing from it — their review roles render from `agent_review_models` and the rest lives in each harness's own config file. The remaining rows are policy, not configuration, and a row that looks authoritative but is unwired can silently disagree with the value the harness actually uses.

That gap is closed by assertion rather than by wiring. `scripts/tests/test_invariants.py` pins the review buckets to `agent_review_models`, pins `findings_audit` and `post_act_verification` to the `review` pick, pins the orchestration rows to Claude's `settings.*.json` and Codex's `private_config.*.toml`, pins each harness's `gruntwork` pick to what its catalog actually carries, requires every `claude_code` model to be a Claude-family selector, requires gpt-5.5 to be at high effort in all six places effort is expressed, and requires `context: short` on every row except the Cursor ids that exist only at 1M. Change a row here and the test tells you which real config now disagrees.

**Two standing policies keep the option space small.** Every model runs short context unless the harness publishes no short variant, and gruntwork takes the cheap codex tier (`gpt-5.3-codex` at high effort) on every harness whose catalog carries it. Claude Code and Gemini are single-vendor and keep their own cheap pick; native Codex has no `gpt-5.3-codex-spark`, so it runs `gpt-5.4`. The resulting option space is two distinct models on Claude Code, Codex, and Gemini, three on Pi and OMP, and four on Copilot and Cursor — those two are the only harnesses that carry a codex gruntwork tier, a Sonnet routine-edit tier, and a cross-family review split at once.

## Work-type buckets

Classification is example-anchored judgment, not a countable metric — there is no formula that decides "is this gruntwork or design work," only recognizable examples. Each bucket names both the model tier to reach for **and** whether the work belongs inline in the orchestrating session or delegated to a subagent.

| Bucket                     | Example tasks                                                                                                                           | Model tier                                                   | Placement                                                                                                                                                              |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gruntwork / mechanical** | grep-and-report, mechanical rename across files, apply a known-shape edit, run and parse a single command, fetch-and-summarize a doc    | Cheapest capable model for the harness                       | Usually delegate to a subagent — keeps the main session's context clean of verbose intermediate output the orchestrator doesn't need verbatim                          |
| **Routine-edit**           | Normal implementation work with a clear shape: add a function, wire an existing pattern into a new call site, fix a well-understood bug | Mid-tier model                                               | Inline in the main session, or a subagent when the edit is large/isolated enough to benefit from a fresh context                                                       |
| **Orchestration / review** | Judging subagent findings, adversarial verification, synthesizing across independent lanes, deciding keep/drop on candidate findings    | Top-tier model                                               | Stays in the main/orchestrating session — this is the judgment the orchestrator exists to make; a subagent doing this needs the same top-tier pin, never a demoted one |
| **Design / ambiguous**     | Novel abstractions, unclear requirements needing interview/fork-closing, architecture decisions with no single correct shape            | Top-tier model, often the harness's highest available effort | Stays in the main/orchestrating session — ambiguity resolution is not delegable without losing the context needed to resolve it                                        |

The orchestrating session is always the one deciding which bucket a piece of work falls into and whether to delegate — it is the driver, subagents are dispatched, not the other way around.

### Review-flow rows

The four buckets above cover general work. The [`/k-deep-review`](reviews/deep-review-topology.md) flow has role stages with model needs distinct from the general taxonomy:

| Stage                        | What it does                                                                                                                                                | Model tier                                                                                                                       | Placement                                                                                      |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Review (angle-lane)**      | Bounded reviewer roster: one sighted lane for simple single-surface diffs and extra lanes only for scope-evidenced independent risk                         | Registry lane model from `agent_review_models.<harness>.lanes`; Claude may use `inherit` as its degraded/session-model exception | Subagent, one per selected angle; concurrent only when multiple lanes apply                    |
| **Findings audit**           | Dedup/audit candidate findings after live UI or explicit live-UI skip; inlined when trivial, delegated to `findings-auditor` when non-trivial               | Top-tier                                                                                                                         | Subagent when non-trivial (2+ findings, HIGH/CRITICAL, lane disagreement); inline when trivial |
| **Adversarial verification** | The one lane where model identity is deliberately pinned — refutes audited candidate findings from a different model **family** than the lane/session model | Top-tier, cross-family from the lane model; harnesses with no second family report `families=same (degraded)`                    | Subagent, isolated read-only                                                                   |
| **Post-act verification**    | Fix-diff re-review after edits land — the flow's "re-review," there is no separately named re-review stage                                                  | Top-tier                                                                                                                         | Main/orchestrating session (fix-authorized, runs quality gates + Post-Review Stage)            |

## Per-harness picks

Every harness names models differently and sets effort differently — there is no universal spelling or universal mechanism. The table below is the calibrated default; `home/.chezmoidata/ai_models.yaml`'s `model_tier_map` section is the source of truth if this page and the registry ever drift.

**Effort-setting mechanism per harness** (confirmed live, 2026-07-27):

| Harness     | Mechanism                                                                                                                                 | Evidence                                                                                              |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Cursor      | Baked into the model-ID suffix (`gpt-5.5-high`, `glm-5.2-high`)                                                                           | `cursor-agent models` live catalog                                                                    |
| Claude Code | Separate `--effort <level>` flag (`low, medium, high, xhigh, max`), model ID stays plain                                                  | `claude --help`; live-tested `claude --model sonnet --effort max`                                     |
| Copilot CLI | Separate `--effort`/`--reasoning-effort <level>` flag (`none, minimal, low, medium, high, xhigh, max`)                                    | `copilot --help`; live-tested `copilot --model gpt-5.5 --effort medium`                               |
| Codex CLI   | `-c model_reasoning_effort=<level>` config override, no dedicated flag                                                                    | `codex --help`; live-tested `codex exec -m gpt-5.5` (model accepted, only hit an unrelated spend cap) |
| Pi          | `--thinking <level>` or model-string suffix (`provider/model:<thinking>`); subagents carry `model` strings, not a separate thinking field | `pi --help`; installed Pi 0.82.1 and `pi-subagents` 0.37.0 source; safe resolver probes               |
| OMP         | Profile frontmatter `model` string; repo registry uses provider-qualified IDs plus `:<thinking>` suffix for pinned profiles               | `home/.chezmoidata/ai_models.yaml`; `.omp/agent/agents/*.md` templates                                |

Do not assume one mechanism works across harnesses — a suffix that means "max effort" in Cursor is not a valid model ID anywhere else.

**Where "Opus 5, high effort, non-thinking" is actually reachable** (verified 2026-08-01):

| Harness     | Reachable? | Why                                                                                                                                      |
| ----------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Cursor      | yes        | Effort and thinking are separate ID families: `claude-opus-5-high` vs `claude-opus-5-thinking-high`                                      |
| Copilot CLI | yes        | `COPILOT_DISABLE_ANTHROPIC_THINKING=1` suppresses the thinking budget while reasoning effort still ships; set by the `,copilot` launcher |
| Claude Code | yes        | `alwaysThinkingEnabled: false` in `settings.json` yields `thinking: {type:"disabled"}` on first-party; already set in both profiles      |
| Pi / OMP    | no         | One dial: `:high` is thinking-high and `:off` surrenders the effort level                                                                |
| Codex       | n/a        | OpenAI-only harness, no Opus                                                                                                             |
| Gemini      | n/a        | Google-only harness, no Opus                                                                                                             |

Cursor, Copilot, and Claude Code all reach the combination, by three different mechanisms.

`COPILOT_DISABLE_ANTHROPIC_THINKING` is undocumented — `copilot help environment` does not list it. It is real in 1.0.77: `Q3e()` injects `copilotDisableAnthropicThinkingEnv: process.env.COPILOT_DISABLE_ANTHROPIC_THINKING` into the options passed to `nativeModelClientDefaultOptionsJson`, whose result carries `thinkingBudget`. Reasoning effort travels a separate path (`supportedReasoningEfforts` / `reasoningPickerType: "effort"`), so `effortLevel: high` is still sent as `reasoning_effort` with thinking suppressed. Verifying this needs the real bundle: the shipped binary is a Node SEA whose payload is a gzipped tar in the `NODE_SEA` segment, so plain `strings` on it finds nothing, and `~/.copilot/pkg` may hold only an older extracted version.

Claude Code turns thinking off through the settings file, not an env var, and the chain is visible in the 2.1.220 binary. `Hye()` returns `false` when `alwaysThinkingEnabled === false`, which makes `thinkingConfig` resolve to `{type:"disabled"}` rather than `{type:"adaptive"}`, and the request builder then sends `thinking: {type:"disabled"}` under `r.type==="disabled" && xn()==="firstParty" && !bn`. Both `settings.personal.json` and `settings.work.json` already set `alwaysThinkingEnabled: false`, so Opus 5 review lanes are genuinely non-thinking on the native route.

Two conditions in that guard are easy to break. `xn()==="firstParty"` means the guarantee holds only on the native Anthropic route; a gateway route such as `,claude-litellm` falls through to omitting the parameter, and adaptive-reasoning models may still think. `!bn` means `CLAUDE_CODE_DISABLE_THINKING=1` _defeats_ the hard disable rather than reinforcing it — it forces the omit path. It is correct in `,claude-litellm`, whose route is not first-party, but it must never be set for a native session.

The env var that does not help is `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`: it is gated to `f.includes("opus-4-6") || f.includes("sonnet-4-6")` and never applies to Opus 5.

### Claude Code

| Bucket                                                                     | Model               | Effort | Thinking | Context |
| -------------------------------------------------------------------------- | ------------------- | ------ | -------- | ------- |
| Gruntwork                                                                  | `claude-sonnet-4-6` | high   | off      | short   |
| Routine-edit                                                               | `claude-sonnet-5`   | high   | off      | short   |
| Orchestration                                                              | `claude-opus-5`     | high   | off      | short   |
| Design/ambiguous                                                           | `claude-opus-5`     | high   | off      | short   |
| Review / Adversarial verification / Findings audit / Post-act verification | `claude-opus-5`     | high   | off      | short   |

Sonnet 4.6 is the gruntwork pick and Sonnet 5 the routine-edit pick; neither is used for orchestration. Claude Code is the one harness that cannot take the cross-harness GPT-5.5 orchestration default: it accepts only Claude-family selectors, and an unknown id is not remapped — it reaches the API and returns `API model not found`. Orchestration therefore runs Opus 5, which is also the main-driver pick; `alwaysThinkingEnabled: false` keeps it non-thinking at high effort. Fable and GPT-5.6 Sol are excluded from active picks. `gpt-5.3-codex` is not in the Anthropic-only catalog, so gruntwork takes the cheapest capable Claude instead of the cross-harness codex-tier pick.

Spelling matters on this harness alone: Claude Code hyphenates point versions, and its own 404 troubleshooting text names `claude-sonnet-4.6` as the typo for `claude-sonnet-4-6`. Copilot and Cursor use the dotted form for the same model, so the id cannot be normalized across harnesses.

Context stays short: bare `claude-opus-5`/`claude-sonnet-5` are the short-window selectors, and the `[1m]` suffix is what would swap them onto the 1M window. Nothing in the tier map asks for it, and `,claude-litellm` passes bare gateway ids for the same reason.

### Codex

| Bucket                                                                     | Model     | Effort |
| -------------------------------------------------------------------------- | --------- | ------ |
| Gruntwork                                                                  | `gpt-5.4` | high   |
| Routine-edit                                                               | `gpt-5.5` | high   |
| Orchestration / Design-ambiguous                                           | `gpt-5.5` | high   |
| Review / Adversarial verification / Findings audit / Post-act verification | `gpt-5.5` | high   |

Codex is single-vendor (OpenAI only); there is no cross-family split to make here. Native Codex 0.146.0 catalog-confirms `gpt-5.3-codex`, `gpt-5.4`, and `gpt-5.5`, but has no `gpt-5.3-codex-spark`; gruntwork therefore runs `gpt-5.4` at high effort. Routine-edit, orchestration, and the review-flow buckets all run `gpt-5.5` at high effort, because gpt-5.5 is only ever used at high effort; Codex carries that per profile as `model_reasoning_effort`, so it is pinnable per agent here unlike on Claude Code or Copilot. Codex exposes no context-tier dial, so every row is short by construction.

### Copilot CLI

| Bucket                                          | Model             | Effort                                                         |
| ----------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| Gruntwork                                       | `gpt-5.3-codex`   | high                                                           |
| Routine-edit                                    | `claude-sonnet-5` | high (non-thinking)                                            |
| Orchestration / Design-ambiguous                | `gpt-5.5`         | high                                                           |
| Review / Findings audit / Post-act verification | `claude-opus-5`   | high (non-thinking via `COPILOT_DISABLE_ANTHROPIC_THINKING=1`) |
| Adversarial verification                        | `gpt-5.5`         | high                                                           |

Copilot's live 1.0.75 catalog confirms `gpt-5.3-codex` and `claude-opus-5`, so Copilot uses them directly for gruntwork and review respectively. Sonnet 5 remains available for routine editing, while orchestration/design use `gpt-5.5` at high effort. Opus 5 drives the review lanes and gpt-5.5 is the cross-family refuter. Effort is not an agent _frontmatter_ field, but `~/.copilot/settings.json` carries `subagents.agents.<name>.effortLevel`, so per-lane effort is pinnable there; that file is hand-synced rather than templated, because the merge script reads it as source JSON and the artifact ledger records it as a `json-declared` baseline path, so an invariant test pins its review models to `agent_review_models` instead. Model IDs stay catalog-native: Copilot uses dotted 4.x IDs such as `claude-opus-4.8`, but the Opus 5 ID is `claude-opus-5`.

Copilot is the only harness with a live context dial: `subagents.agents.<name>.contextTier` takes `default` or `long_context`, and every subagent is pinned to `default` under the short-context policy. The `explore` and `task` subagents are Copilot's deployed gruntwork lanes, so they carry `gpt-5.3-codex` at high effort.

### Cursor

| Bucket                                          | Model                  | Effort              |
| ----------------------------------------------- | ---------------------- | ------------------- |
| Gruntwork                                       | `gpt-5.3-codex-high`   | high                |
| Routine-edit                                    | `claude-sonnet-5-high` | high (non-thinking) |
| Orchestration / Design-ambiguous                | `gpt-5.5-high`         | high                |
| Review / Findings audit / Post-act verification | `claude-opus-5-high`   | high (non-thinking) |
| Adversarial verification                        | `gpt-5.5-high`         | high                |

Cursor is the one harness that cannot honor the short-context policy for its review picks: it publishes Opus 5, Sonnet 5, and GPT-5.5 exclusively as 1M ids (`claude-opus-5-high — Opus 5 1M`), with no short variant to select. Those rows record `context: long` because that is the window they actually get. The Codex 5.3 ids carry no 1M label, so gruntwork is genuinely short.

Cursor's live catalog confirms `gpt-5.3-codex-high`, so Cursor gruntwork uses it directly; effort rides in the id here, which is why the gruntwork pick is spelled with the `-high` suffix. `glm-5.2-high`/`glm-5.2-max` are still real model IDs, but they are no longer the default gruntwork pick. `claude-opus-5-high` (plain) and `claude-opus-5-thinking-high` are distinct, real model IDs — Cursor is the one harness where "non-thinking" is selected by picking a different model ID outright, not a flag. That makes Cursor the only harness that can express "Opus 5, high effort, non-thinking" exactly, which is why its review lanes pin `claude-opus-5-high` and its verifier pins `gpt-5.5-high`.

### Gemini (as consumed via each harness)

| Bucket                                                                                                                       | Model                                                                           | Effort |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------ |
| Gruntwork                                                                                                                    | `gemini-3.6-flash`                                                              | high   |
| Routine-edit / Orchestration / Design-ambiguous / Review / Adversarial verification / Findings audit / Post-act verification | `gemini-3.1-pro` (Cursor) / `gemini-3.1-pro-preview` (LiteLLM, Vertex, Copilot) | high   |

Naming is genuinely inconsistent across sources, confirmed live: Cursor's own catalog calls it plain `gemini-3.1-pro` with no `-preview` suffix and no visible effort-tier suffixes; `litellm_models`/`provider_models` (Vertex)/`copilot_models` all call it `gemini-3.1-pro-preview`. Do not normalize to one spelling — record both.

`gemini-3.6-flash` is a different, newer model than `gemini-3.5-flash` (which is what's actually in `litellm_models`/`provider_models`/`copilot_models` today). Use `gemini-3.6-flash` where the harness exposes it (confirmed live in Cursor, and defined in the Vertex `provider_models` block); fall back to `gemini-3.5-flash` explicitly where a harness's catalog doesn't yet have 3.6 (e.g. Copilot's snapshot, the LiteLLM gateway) rather than treating the two as interchangeable.

### Pi

| Bucket                                                                     | Model                                       | Effort              |
| -------------------------------------------------------------------------- | ------------------------------------------- | ------------------- |
| Gruntwork                                                                  | `openrouter/openai/gpt-5.3-codex:high`      | high                |
| Routine-edit                                                               | `openrouter/anthropic/claude-sonnet-5:high` | high (non-thinking) |
| Orchestration / Design-ambiguous                                           | `openrouter/openai/gpt-5.5:high`            | high                |
| Review / Findings audit / Post-act verification / Adversarial verification | `openrouter/openai/gpt-5.5:high`            | high                |

Pi's default model/thinking is config-file based, but Pi also supports `--model`, `--thinking`, and model strings suffixed with `:<thinking>`. `pi-subagents` has per-task/per-agent `model` but no separate per-task `thinking`; use the suffix form (for example, `openrouter/openai/gpt-5.3-codex:high`) for subagent pins. That suffix is a thinking level, not a separate effort dial: `pi-subagents` 0.38.0 parses it with `splitKnownThinkingSuffix` against `THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh", "max"]` (`src/shared/model-info.ts`). So `claude-opus-5:high` means thinking high, and `off` is the only non-thinking value — Pi cannot express "high effort, non-thinking" because both live on one dial. Because Opus 5 is only reachable there with thinking on, Pi runs `gpt-5.5:high` for the lanes and the verifier alike and reports `families=same (degraded)`. The local Pi/OpenRouter catalog confirms both `openrouter/openai/gpt-5.3-codex` and the fallback `openrouter/openai/gpt-5.6-luna`; Gemini 3.6 Flash is available only where the Pi/OpenRouter catalog exposes a matching route. The `:<level>` suffix is a thinking dial, not a context tier — Pi exposes no context selector, so every row is short by construction.

### OMP

| Bucket                                                                     | Model                                 | Effort              |
| -------------------------------------------------------------------------- | ------------------------------------- | ------------------- |
| Gruntwork                                                                  | `github-copilot/gpt-5.3-codex:high`   | high                |
| Routine-edit                                                               | `github-copilot/claude-sonnet-5:high` | high (non-thinking) |
| Orchestration / Design-ambiguous                                           | `github-copilot/gpt-5.5:high`         | high                |
| Review / Findings audit / Post-act verification / Adversarial verification | `github-copilot/gpt-5.5:high`         | high                |

OMP repo-owned profiles pin their models through `model_tier_map.omp` or `agent_review_models.omp`. Do not rely on any native OMP subagent default for review workers, fresh-eyes, or verifier lanes. Like Pi, OMP's `:<level>` suffix is a single thinking dial that the runtime maps straight onto `reasoning` (`omp` 17.2.3), so "high effort, non-thinking" is not expressible here either, and OMP makes the same `gpt-5.5:high` choice for both roles. Orchestration previously ran `github-copilot/gpt-5.6-terra:medium`, the only medium-effort row and the only fourth model left on any harness; it now shares the `gpt-5.5:high` pick so OMP carries three models total.

## Native subagent takeover risk

Every harness that can spawn subagents has its own **native** default model for that path — separate from anything this repo's registry declares — and an unpinned harness silently falls back to whatever that native default is. This is the risk this taxonomy exists to close, not just document.

| Harness         | Takeover risk                                                                                                                                                                                                         | Status                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cursor**      | Omitted/default Cursor subagents are unsafe: local CLI shows `auto`, and user-verified expenditure data shows Cursor-served defaults can resolve to `composer-2.5-fast`                                               | **Mitigated** for repo-owned custom profiles via explicit `agent_review_models` pins. Same-name `.cursor/agents` profiles cannot shadow native enum agents like `explore`, `debug`, or `cursor_guide`; they are a separate `custom` oneof case. Generic/default Cursor subagent launches must pass the matrix model explicitly (`gpt-5.3-codex-high` for gruntwork, `claude-opus-5-high` for review lanes, or `gpt-5.5-high` for the verifier); do not let Cursor `auto` choose. Cursor `worker`/cloud `requested_models` omission remains an open risk unless launched with explicit models. |
| **Codex**       | `multi_agent` `spawn_agent`/`wait`; omitted models fall back to native/default metadata that is not auditable enough for this policy                                                                                  | **Mitigated** — Codex profiles now carry explicit `model = "{{ .agent_review_models.codex.* }}"` plus `model_reasoning_effort = "high"`. Generic `spawn_agent` launches must pass the same registry model explicitly; do not rely on native defaults.                                                                                                                                                                                                                                                                                                                                         |
| **Copilot CLI** | `--agent` flag, `subagents.agents.*` config; stale target-only nested settings can otherwise preserve old model overrides                                                                                             | **Mitigated** — profile frontmatter and `~/.copilot/settings.json` subagent entries both pin registry-aligned models. `agent_review_models.copilot.lanes` is `claude-opus-5`; verifier is `gpt-5.5`; gruntwork uses catalog-confirmed `gpt-5.3-codex`.                                                                                                                                                                                                                                                                                                                                        |
| **Claude Code** | `Task` tool w/ `subagent_type`, embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`), plus a separate `claude agents`/background-agent surface with its own `--model` default flag | **Mitigated for normal Task agents**: repo-owned same-name profiles shadow high-risk builtins, and `,claude-litellm` defaults `CLAUDE_CODE_SUBAGENT_MODEL=inherit` so frontmatter/Task model args are not globally overridden. `claude agents` background omitted defaults remain unknown unless launched/probed; dispatch them with explicit `--model`/`--effort`.                                                                                                                                                                                                                           |
| **Gemini**      | `.gemini/agents/*.md` + `@name` forced invocation                                                                                                                                                                     | **Mitigated** — Gemini profiles now carry registry-rendered `model` frontmatter (`gemini-3.1-pro-preview`). Do not rely on the configured Gemini default for review workers.                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Pi**          | `~/.pi/agent/agents/*.md`; subagent runner accepts model strings and encodes thinking as a suffix                                                                                                                     | **Mitigated for repo-owned profiles** — Pi profiles are explicitly pinned from `model_tier_map`/`agent_review_models`; review lanes use `openrouter/anthropic/claude-opus-5:high`, lanes and verifier both use `openrouter/openai/gpt-5.5:high`. Future profiles must either pin `model` or document why they intentionally use `defaultProvider`/`defaultModel`.                                                                                                                                                                                                                             |
| **OMP**         | `~/.omp/agent/agents/*.md`; omitted profile models can fall back to the harness's native subagent default outside the repo registry                                                                                   | **Mitigated for repo-owned profiles** — OMP profiles are explicitly pinned from `model_tier_map`/`agent_review_models`; review lanes, fresh-eyes, and the verifier all use `github-copilot/gpt-5.5:high`. Future profiles must either pin `model` or document why they intentionally use the native default.                                                                                                                                                                                                                                                                                  |

## Related

- [Subagents](subagents.md) — cross-harness subagent discovery and profile topology
- [Model registry & routing](model-registry.md) — the underlying `ai_models.yaml` sections and generators
- [Scenarios](scenarios.md) — when to reach for which skill/flow; this page's buckets refine that page's "smallest flow that fits" default with model/placement specifics
