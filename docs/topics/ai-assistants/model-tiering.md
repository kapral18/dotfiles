---
sidebar_position: 5
---

# Model tiering

Which model/effort a task should run on, and whether that task belongs inline in the orchestrating session or in a dedicated subagent, are the same decision. This page is the taxonomy that decision uses, the per-harness picks it resolves to, and the native-subagent-takeover risks that can silently bypass it.

Canonical data lives in [`home/.chezmoidata/ai_models.yaml`](../../../home/.chezmoidata/ai_models.yaml)'s `model_tier_map` section — declared once, consumed by every harness's templated subagent profile and by the orchestrator's own settings files, the same [`agent_review_models`](model-registry.md) pattern already proven for `/k-agent-review` lanes.

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

The four buckets above cover general work. The [`/k-agent-review`](reviews/agent-review-topology.md) flow has its own four stages, each with its own model needs distinct from the general taxonomy:

| Stage                        | What it does                                                                                                                                                 | Model tier                                                                                                    | Placement                                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Review (angle-lane)**      | Phase 2: parallel reviewer angle lanes, fan-out                                                                                                              | Registry lane model from `agent_review_models.<harness>.lanes`; Claude may use `inherit` as its degraded/session-model exception | Subagent, one per angle, run concurrently                                                      |
| **Adversarial verification** | Phase 3: the one lane where model identity is deliberately pinned — refutes candidate findings from a different model **family** than the lane/session model | Top-tier, cross-family from the lane model; harnesses with no second family report `families=same (degraded)` | Subagent, isolated read-only                                                                   |
| **Findings audit**           | Phase 5: dedup/audit candidate findings, inlined when trivial, delegated to `findings-auditor` when non-trivial                                              | Top-tier                                                                                                      | Subagent when non-trivial (2+ findings, HIGH/CRITICAL, lane disagreement); inline when trivial |
| **Post-act verification**    | Phase 9: fix-diff re-review after edits land — the flow's "re-review," there is no separately named re-review stage                                          | Top-tier                                                                                                      | Main/orchestrating session (fix-authorized, runs quality gates + Post-Review Stage)            |

## Per-harness picks

Every harness names models differently and sets effort differently — there is no universal spelling or universal mechanism. The table below is the calibrated default; `home/.chezmoidata/ai_models.yaml`'s `model_tier_map` section is the source of truth if this page and the registry ever drift.

**Effort-setting mechanism per harness** (confirmed live, 2026-07-27):

| Harness     | Mechanism                                                                                                    | Evidence                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| Cursor      | Baked into the model-ID suffix (`gpt-5.5-medium`, `glm-5.2-high`)                                            | `cursor-agent models` live catalog                                                                    |
| Claude Code | Separate `--effort <level>` flag (`low, medium, high, xhigh, max`), model ID stays plain                     | `claude --help`; live-tested `claude --model sonnet --effort max`                                     |
| Copilot CLI | Separate `--effort`/`--reasoning-effort <level>` flag (`none, minimal, low, medium, high, xhigh, max`)       | `copilot --help`; live-tested `copilot --model gpt-5.5 --effort medium`                               |
| Codex CLI   | `-c model_reasoning_effort=<level>` config override, no dedicated flag                                       | `codex --help`; live-tested `codex exec -m gpt-5.5` (model accepted, only hit an unrelated spend cap) |
| Pi          | `--thinking <level>` or model-string suffix (`provider/model:<thinking>`); subagents carry `model` strings, not a separate thinking field | `pi --help`; installed Pi 0.82.1 and `pi-subagents` 0.37.0 source; safe resolver probes |

Do not assume one mechanism works across harnesses — a suffix that means "max effort" in Cursor is not a valid model ID anywhere else.

### Claude Code

| Bucket                                                                     | Model              | Effort | Thinking | Context |
| -------------------------------------------------------------------------- | ------------------ | ------ | -------- | ------- |
| Gruntwork                                                                  | `claude-sonnet-5`  | high   | off      | long    |
| Routine-edit                                                               | `claude-sonnet-5`  | high   | off      | long    |
| Orchestration                                                              | `gpt-5.5`          | medium | —        | long    |
| Design/ambiguous                                                           | `gpt-5.5`          | medium | —        | long    |
| Review / Adversarial verification / Findings audit / Post-act verification | `claude-opus-4-8`  | high   | off      | long    |

Sonnet 5 is the Claude Code-native gruntwork/routine-edit pick because Claude Code subagent frontmatter only accepts Claude-family model selectors. It is deliberately not used for orchestration. The orchestrator/default orchestration bucket is `gpt-5.5` at medium effort; Fable and GPT-5.6 Sol are excluded from active picks.

### Codex

| Bucket                                                                                                        | Model           | Effort |
| ------------------------------------------------------------------------------------------------------------- | --------------- | ------ |
| Gruntwork                                                                                                     | `gpt-5.6-luna`  | high   |
| Routine-edit                                                                                                  | `gpt-5.5`       | medium |
| Orchestration / Design-ambiguous / Review / Adversarial verification / Findings audit / Post-act verification | `gpt-5.5`       | medium |

Codex is single-vendor (OpenAI only); there is no cross-family split to make here. Native Codex 0.145.0 catalog-confirms `gpt-5.6-luna` and `gpt-5.5`, but does not catalog-confirm `gpt-5.3-codex`; therefore native Codex gruntwork uses the fallback, `gpt-5.6-luna` at high effort. Routine-edit and orchestration stay on `gpt-5.5` at medium effort.

### Copilot CLI

| Bucket                                                                     | Model                                                            | Effort              |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------- |
| Gruntwork                                                                  | `gpt-5.3-codex`                                                  | medium              |
| Routine-edit                                                               | `claude-sonnet-5`                                                | high (non-thinking) |
| Orchestration / Design-ambiguous                                           | `gpt-5.5`                                                       | medium              |
| Review / Adversarial verification / Findings audit / Post-act verification | `claude-opus-4.8` (high, non-thinking) **or** `gpt-5.5` (medium) | —                   |

Copilot's live 1.0.75 catalog confirms `gpt-5.3-codex`, so Copilot gruntwork uses it directly. Sonnet 5 remains available for routine editing, but orchestration/design use `gpt-5.5` at medium effort. Copilot uses dot-version Claude IDs (`claude-opus-4.8`, `claude-haiku-4.5`), not Anthropic API hyphen-version IDs.

### Cursor

| Bucket                                                                     | Model                                                         | Effort              |
| -------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------- |
| Gruntwork                                                                  | `gpt-5.3-codex`                                              | medium              |
| Routine-edit                                                               | `claude-sonnet-5-high`                                        | high (non-thinking) |
| Orchestration / Design-ambiguous                                           | `gpt-5.5-medium`                                           | medium              |
| Review / Adversarial verification / Findings audit / Post-act verification | `claude-opus-4-8-high` (non-thinking) **or** `gpt-5.5-medium` | —                   |

Cursor's live catalog confirms `gpt-5.3-codex`, so Cursor gruntwork uses it directly. `glm-5.2-high`/`glm-5.2-max` are still real model IDs, but they are no longer the default gruntwork pick. `claude-opus-4-8-high` (plain) and `claude-opus-4-8-thinking-high` are distinct, real model IDs — Cursor is the one harness where "non-thinking" is selected by picking a different model ID outright, not a flag.

### Gemini (as consumed via each harness)

| Bucket                                                                                                                       | Model                                                                           | Effort |
| ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------ |
| Gruntwork                                                                                                                    | `gemini-3.6-flash`                                                              | high   |
| Routine-edit / Orchestration / Design-ambiguous / Review / Adversarial verification / Findings audit / Post-act verification | `gemini-3.1-pro` (Cursor) / `gemini-3.1-pro-preview` (LiteLLM, Vertex, Copilot) | high   |

Naming is genuinely inconsistent across sources, confirmed live: Cursor's own catalog calls it plain `gemini-3.1-pro` with no `-preview` suffix and no visible effort-tier suffixes; `litellm_models`/`provider_models` (Vertex)/`copilot_models` all call it `gemini-3.1-pro-preview`. Do not normalize to one spelling — record both.

`gemini-3.6-flash` is a different, newer model than `gemini-3.5-flash` (which is what's actually in `litellm_models`/`provider_models`/`copilot_models` today). Use `gemini-3.6-flash` where the harness exposes it (confirmed live in Cursor, and defined in the Vertex `provider_models` block); fall back to `gemini-3.5-flash` explicitly where a harness's catalog doesn't yet have 3.6 (e.g. Copilot's snapshot, the LiteLLM gateway) rather than treating the two as interchangeable.

### Pi

| Bucket                                                                     | Model                                                            | Effort              |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------- |
| Gruntwork                                                                  | `openrouter/openai/gpt-5.3-codex:medium`                        | medium              |
| Routine-edit                                                               | `openrouter/anthropic/claude-sonnet-5:high`                     | high (non-thinking) |
| Orchestration / Design-ambiguous                                           | `openrouter/openai/gpt-5.5:medium`                              | medium              |
| Review / Adversarial verification / Findings audit / Post-act verification | `claude-opus-4.8` (high, non-thinking) **or** `gpt-5.5` (medium) | —                   |

Pi's default model/thinking is config-file based, but Pi also supports `--model`, `--thinking`, and model strings suffixed with `:<thinking>`. `pi-subagents` has per-task/per-agent `model` but no separate per-task `thinking`; use the suffix form (for example, `openrouter/openai/gpt-5.3-codex:medium`) for subagent pins. The local Pi/OpenRouter catalog confirms both `openrouter/openai/gpt-5.3-codex` and the fallback `openrouter/openai/gpt-5.6-luna`; Gemini 3.6 Flash is available only where the Pi/OpenRouter catalog exposes a matching route.

## Native subagent takeover risk

Every harness that can spawn subagents has its own **native** default model for that path — separate from anything this repo's registry declares — and an unpinned harness silently falls back to whatever that native default is. This is the risk this taxonomy exists to close, not just document.

| Harness         | Takeover risk                                                                                                                                                                                                                   | Status                                                                                                                                                                                                                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Cursor**      | Omitted/default Cursor subagents are unsafe: local CLI shows `auto`, and user-verified expenditure data shows Cursor-served defaults can resolve to `composer-2.5-fast` | **Mitigated** for repo-owned custom profiles via explicit `agent_review_models` pins. Same-name `.cursor/agents` profiles cannot shadow native enum agents like `explore`, `debug`, or `cursor_guide`; they are a separate `custom` oneof case. Generic/default Cursor subagent launches must pass the matrix model explicitly (`gpt-5.3-codex`, `gpt-5.5-medium`, or `claude-opus-4-8-high` by role); do not let Cursor `auto` choose. Cursor `worker`/cloud `requested_models` omission remains an open risk unless launched with explicit models. |
| **Codex**       | `multi_agent` `spawn_agent`/`wait`; omitted models fall back to native/default metadata that is not auditable enough for this policy                                                                                             | **Mitigated** — Codex profiles now carry explicit `model = "{{ .agent_review_models.codex.* }}"` plus `model_reasoning_effort = "medium"`. Generic `spawn_agent` launches must pass the same registry model explicitly; do not rely on native defaults.                                                                                                      |
| **Copilot CLI** | `--agent` flag, `subagents.agents.*` config; stale target-only nested settings can otherwise preserve old model overrides                                                                                                      | **Mitigated** — profile frontmatter and `~/.copilot/settings.json` subagent entries both pin registry-aligned models. `agent_review_models.copilot.lanes` is `gpt-5.5`; verifier is `claude-opus-4.8`; gruntwork uses catalog-confirmed `gpt-5.3-codex`.                                                                                                      |
| **Claude Code** | `Task` tool w/ `subagent_type`, embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`), plus a separate `claude agents`/background-agent surface with its own `--model` default flag | **Mitigated for normal Task agents**: repo-owned same-name profiles shadow high-risk builtins, and `,claude-litellm` defaults `CLAUDE_CODE_SUBAGENT_MODEL=inherit` so frontmatter/Task model args are not globally overridden. `claude agents` background omitted defaults remain unknown unless launched/probed; dispatch them with explicit `--model`/`--effort`. |
| **Gemini**      | `.gemini/agents/*.md` + `@name` forced invocation                                                                                                                                                                               | **Mitigated** — Gemini profiles now carry registry-rendered `model` frontmatter (`gemini-3.1-pro-preview`). Do not rely on the configured Gemini default for review workers.                                                                                                                                                                                   |
| **Pi**          | `~/.pi/agent/agents/*.md`; subagent runner accepts model strings and encodes thinking as a suffix                                                                                                                                                                                                       | **Mitigated for repo-owned profiles** — Pi profiles are explicitly pinned from `model_tier_map`/`agent_review_models`; review lanes use `openrouter/anthropic/claude-opus-4.8:high`, verifier uses `openrouter/openai/gpt-5.5:medium`. Future profiles must either pin `model` or document why they intentionally use `defaultProvider`/`defaultModel`. |

## Related

- [Subagents](subagents.md) — cross-harness subagent discovery and profile topology
- [Model registry & routing](model-registry.md) — the underlying `ai_models.yaml` sections and generators
- [Scenarios](scenarios.md) — when to reach for which skill/flow; this page's buckets refine that page's "smallest flow that fits" default with model/placement specifics
