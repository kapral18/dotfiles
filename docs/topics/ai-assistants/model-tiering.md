---
sidebar_position: 5
---

# Model tiering

Which model/effort a task should run on, and whether that task belongs inline in the orchestrating session or in a dedicated subagent, are the same decision. This page is the taxonomy that decision uses, the per-harness picks it resolves to, and the native-subagent-takeover risks that can silently bypass it.

Canonical data lives in [`home/.chezmoidata/ai_models/tiering.yaml`](../../../home/.chezmoidata/ai_models/tiering.yaml), split across portable routing tables, per-harness category rows, and sparse review overrides:

| Table              | Dimension   | Says                                                                                                              |
| ------------------ | ----------- | ----------------------------------------------------------------------------------------------------------------- |
| `agent_categories` | portable    | What a kind of work means: `{family, contract}` for each category                                                 |
| `agent_bindings`   | portable    | Which category each delegable agent name belongs to, built-ins included                                           |
| `category_models`  | per harness | What each category resolves to in that harness, including verifier status for `refute`                            |
| `session_models`   | per harness | The root/main-session pick the user talks to; generated into every repo-owned root config; never a binding target |

Whether a findings audit needs review-grade reasoning is a fact about the job, not about the harness; only `category_models` knows Codex's catalog. Merging the two is what made the previous single `model_tier_map` need 57 rows to carry roughly 21 facts. Categories are chosen before the model: the SOP delegation section and the `k-*` skills name a category, and then `category_models` resolves that category to a harness-native id.

**Categories are the routing unit.** Cost labels such as `cheap`/`standard`/`max` collapsed distinct risks: exact lookup, deterministic edits, semantic investigation, implementation, orchestration, review, and refutation are different jobs. The matrix prices each category explicitly per harness.

**Two standing policies keep the option space small.** Exact caller-scoped retrieval is `mechanical`; semantic discovery is `research`. Context is an explicit tier in every category row. The registry key for Google's coding harness is `antigravity`; `gemini` remains only the deployed mirror/review-harness name where those consumers require it.

## Categories

Categories select capability, not mandatory agent launches. The session and strong research/review/refute handle judgment. Substantial settled implementation uses the implementation band; mechanical packets isolate substantial settled retrieval, execution, extraction, transformation, compression and reporting; tiny operations use direct tools. Automatic memory recall and learning remain; admission is bounded and persistence is batched. Keep raw evidence in task contexts and compact decisions in the strong root. Do not spend the expensive root on routine implementation by default. Model/effort values below remain registry-owned; no model migration is part of the staged-workflow change.

## Tiers

Within a harness the categories collapse onto three price tiers (user call 2026-09-07). The tier is the routing shorthand; the category is still what a packet names.

| Tier | Categories             | What it is                                                                                                                    |
| ---- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| T1   | `research`, `review`   | The orchestration-grade category set; the session row is priced at T1                                                         |
| T2   | `implement`            | One tier below T1; settled steps with stated acceptance and unwritten code go to the implementation band                      |
| T3   | `mechanical`, `memory` | Settled procedure/output work, or bounded memory operations; command returns include actual exit status and full-log pointers |

`refute` sits outside the ladder: it is priced at T1 capability on the counter family where the harness has one.

The SOP §3.7 routes settled implementation with stated acceptance and unwritten code to T2; explicit user no-delegation keeps work inline. The root owns decomposition, stage-sized packets, integration, and one final Verify. Known commands run directly through deterministic tools, not a separate model check runner. Research/production workers do not verify. After final failure, the root may make an evidence-backed repair within existing authority and rerun failed or affected checks; workers cannot start that recovery. The tier ladder is a price shape, not a promise that every category uses a distinct model. A category may share a model with another category when its harness-literal effort differs.

## Session model (root)

`session_models` is the root/main-session pick the user talks to. It is generated into every repo-owned root config and is never a binding target.

| Harness       | Model                            | Effort | Context | Generated into                                                             |
| ------------- | -------------------------------- | ------ | ------- | -------------------------------------------------------------------------- |
| `claude_code` | `claude-opus-5-5[1m]`            | high   | long    | `home/dot_claude/settings.{work,personal}.json`                            |
| `codex`       | `gpt-6-sol`                      | high   | short   | `home/dot_codex/private_config.{work,personal}.toml`                       |
| `cursor`      | `claude-opus-5-5`                | high   | long    | none (user-config-owned, informational)                                    |
| `antigravity` | `gemini-3.8-flash`               | high   | long    | `home/dot_gemini/antigravity-cli/readonly_settings.policy.json`            |
| `pi`          | `openrouter/meta/muse-spark-1.3` | xhigh  | long    | `home/dot_pi/agent/readonly_settings.{work,personal}.json`                 |
| `omp`         | `openai-codex/gpt-6-sol`         | high   | short   | `home/dot_omp/private_agent/readonly_config.yml.tmpl` `modelRoles.default` |

Cursor: user-config-owned, informational.

## Per-harness picks

Every harness names models differently and sets effort differently — there is no universal spelling or universal mechanism. When calibrating a harness, verify the model exists in that harness's real catalog/whitelist and pick the first working model from the preference order (do not mass-assign ids across harnesses). The table below is the calibrated default; `home/.chezmoidata/ai_models/tiering.yaml`'s `category_models` section is the source of truth if this page and the registry ever drift.

**Effort-setting mechanism per harness** (confirmed live, 2026-07-27):

| Harness     | Mechanism                                                                                                                            |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Cursor      | Task receives only a base catalog name. Effort comes from the user's saved Cursor config and is not encodable in the Task id.        |
| Claude Code | Separate effort (`low`, `medium`, `high`, `xhigh`, `max`); point versions use hyphens and `[1m]` selects the 1M window.              |
| Codex CLI   | `model_reasoning_effort` alongside the model.                                                                                        |
| Pi          | Managed profile `model` contains no `:level`; `thinking:` is rendered separately from the category row's `effort`.                   |
| OMP         | Category `@role` tokens resolve through `modelRoles`; those role values carry provider/model and the OMP thinking suffix.            |
| Antigravity | Category rows use the `antigravity` key; `invoke_subagent` takes only abstract tiers, and every row is Flash, so lanes pass `flash`. |

Do not assume one mechanism works across harnesses — a suffix that means "max effort" in Cursor is not a valid model ID anywhere else.

**Where "high effort, non-thinking" is actually reachable** (verified 2026-08-01):

| Harness     | Reachable?   | Why                                                                                                                                        |
| ----------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Cursor      | not per call | Task accepts only the base id; saved user config, not the delegation payload, owns effort/thinking.                                        |
| Claude Code | yes          | `alwaysThinkingEnabled: false` in `settings.json` yields `thinking: {type:"disabled"}` on first-party; already set in both profiles        |
| Pi / OMP    | no           | Pi renders `thinking: high` separately from its model; OMP carries `:high` in `modelRoles`, but each is still one thinking/reasoning dial. |
| Codex       | n/a          | OpenAI-only harness, no Opus                                                                                                               |
| Antigravity | n/a          | Google-only harness, no Opus                                                                                                               |

Claude Code can request the combination directly. Cursor delegation cannot encode it; Pi and OMP expose one combined thinking/reasoning dial.

Claude Code turns thinking off through the settings file, not an env var, and the chain is visible in the 2.1.220 binary. `Hye()` returns `false` when `alwaysThinkingEnabled === false`, which makes `thinkingConfig` resolve to `{type:"disabled"}` rather than `{type:"adaptive"}`, and the request builder then sends `thinking: {type:"disabled"}` under `r.type==="disabled" && xn()==="firstParty" && !bn`. Both `settings.personal.json` and `settings.work.json` already set `alwaysThinkingEnabled: false`, so conclusion-forming Opus 5.5 categories are genuinely non-thinking on the native route. That guard keys on the settings flag, not on the model id, so it holds across a category model change.

Two conditions in that guard are easy to break. `xn()==="firstParty"` means the guarantee holds only on the native Anthropic route; a gateway route such as `,claude-openrouter` falls through to omitting the parameter, and adaptive-reasoning models may still think. `!bn` means `CLAUDE_CODE_DISABLE_THINKING=1` _defeats_ the hard disable rather than reinforcing it — it forces the omit path. It is correct in `,claude-openrouter`, whose route is not first-party, but it must never be set for a native session.

The env var that does not help is `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`: it is gated to `f.includes("opus-4-6") || f.includes("sonnet-4-6")`, so it never applies to Opus 5 or Sonnet 5. `alwaysThinkingEnabled: false` is the lever that does.

### Claude Code

| Category     | Model                 | Effort | Context | Verifier status |
| ------------ | --------------------- | ------ | ------- | --------------- |
| `mechanical` | `claude-sonnet-5`     | high   | long    | —               |
| `research`   | `claude-opus-5-5[1m]` | high   | long    | —               |
| `implement`  | `claude-sonnet-5`     | xhigh  | long    | —               |
| `review`     | `claude-opus-5-5[1m]` | high   | long    | —               |
| `refute`     | `claude-opus-5-5[1m]` | high   | long    | degraded        |
| `memory`     | `claude-sonnet-5`     | medium | short   | —               |

Claude Code accepts hyphenated point versions only: `claude-sonnet-4-6`, `claude-fable-5-1`, and `claude-opus-5-5`. Dotted point versions 404. The `[1m]` suffix selects the 1M context window. Claude's single-vendor catalog cannot provide an independent refute family. Same-family refutation is reduced independence: the report must state the shared family.

### Codex

| Category     | Model        | Effort | Context | Verifier status |
| ------------ | ------------ | ------ | ------- | --------------- |
| `mechanical` | `gpt-6-luna` | high   | short   | —               |
| `research`   | `gpt-6-sol`  | high   | short   | —               |
| `implement`  | `gpt-6-sol`  | medium | short   | —               |
| `review`     | `gpt-6-sol`  | high   | short   | —               |
| `refute`     | `gpt-6-sol`  | high   | short   | degraded        |
| `memory`     | `gpt-6-sol`  | high   | short   | —               |

Codex is OpenAI-only, so refutation is degraded; `refute` uses the same `gpt-6-sol` pick and effort as review (user call 2026-09-23), so it adds no model diversity and reports reduced independence. Model and effort are separate fields on native profiles and gate rewrites.

### Cursor

| Category     | Task base id      | Recorded effort | Context | Verifier status |
| ------------ | ----------------- | --------------- | ------- | --------------- |
| `mechanical` | `grok-4.6`        | medium          | long    | —               |
| `research`   | `claude-opus-5-5` | high            | long    | —               |
| `implement`  | `muse-spark-1.3`  | high            | long    | —               |
| `review`     | `claude-opus-5-5` | high            | long    | —               |
| `refute`     | `muse-spark-1.3`  | max             | long    | cross_family    |
| `memory`     | `grok-4.6`        | medium          | short   | —               |

Cursor Task accepts only base catalog names. Legacy slugs such as `cursor-grok-4.6-high` and bracketed selectors silently fall back to the parent model, so the gate writes only `model=<base>`. Effort comes from the user's saved Cursor configuration, not from the id. `-fast` ids are a price tier and are never category picks. `cursor_task_base_models` captures the Task resolver's accepted names. Refute shares the implement base id (`muse-spark-1.3`) with only effort differing (`max` vs `high`), and Task ids cannot carry effort, so the refute lane is indistinguishable from implement on the wire; the `max` effort is recorded, not enforced.

### Antigravity

| Category     | Model              | Effort | Context | Verifier status |
| ------------ | ------------------ | ------ | ------- | --------------- |
| `mechanical` | `gemini-3.8-flash` | low    | long    | —               |
| `research`   | `gemini-3.8-flash` | high   | long    | —               |
| `implement`  | `gemini-3.8-flash` | medium | long    | —               |
| `review`     | `gemini-3.8-flash` | high   | long    | —               |
| `refute`     | `gemini-3.8-flash` | high   | long    | degraded        |
| `memory`     | `gemini-3.8-flash` | low    | long    | —               |

The category registry key is `antigravity`. The mirror continues to publish a `gemini` harness because that is the deployed tool directory/name. Dynamic review lanes use the native abstract `flash` selector, matching the all-Flash category rows.

### Pi

| Category     | Model                            | `thinking` | Context | Verifier status |
| ------------ | -------------------------------- | ---------- | ------- | --------------- |
| `mechanical` | `openrouter/z-ai/glm-5.3-flash`  | high       | long    | —               |
| `research`   | `openrouter/z-ai/glm-5.3`        | max        | long    | —               |
| `implement`  | `openrouter/z-ai/glm-5.3`        | high       | long    | —               |
| `review`     | `openrouter/meta/muse-spark-1.3` | max        | long    | —               |
| `refute`     | `openrouter/x-ai/grok-4.6`       | high       | short   | cross_family    |
| `memory`     | `openrouter/z-ai/glm-5.3-flash`  | high       | short   | —               |

Every Pi row now rides OpenRouter. `review` is the Meta route at max effort and `refute` is the Grok counter, a different vendor family. The earlier `gemini-3.8-flash` refuter produced a false finding and skipped a packet-mandated parser run in the 2026-09-12 PR 4412 convergence session, so the counter moved to a stronger model (user call 2026-09-13). `research` and `implement` share GLM 5.3 but split on effort, which keeps `implement` distinct from both `mechanical` and the session row.

Pi category models never include a `:level` suffix. Every managed profile renders `model:` through the existing model partial and renders a separate `thinking:` line through `agent-thinking.partial`; the line is omitted when effort is empty. `pi-subagents` accepts `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max` in that frontmatter field.

Only Pi rows beginning with `openrouter/` can become OpenRouter wrapper wire models. The deployed `openrouter_presets.py --pi-openrouter-wire-models` helper reads those rows and emits `<model-without-openrouter/>@preset/effort-<effort>`.

#### Pi model profiles

Pi is the one harness with a machine-local alternate pricing. The `pi_model_profiles` section of [`tiering.yaml`](../../../home/.chezmoidata/ai_models/tiering.yaml) holds whole replacement pricings — a full `session` row plus a full `categories` map, never a sparse overlay — and [`,pi-model-profile`](../workflow/custom-commands/catalog.md) selects which one this machine runs.

| Profile           | Session                                           | Lanes                                                                                                                                                                                                                               |
| ----------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `default`         | the table above                                   | the table above                                                                                                                                                                                                                     |
| `local`           | `llama-cpp/qwen3.6-35b-a3b`                       | Qwen3.6 35B-A3B UD-Q5_K_XL with thinking off; root and every lane share one router ID, without mixing the instruct preset; the same-model counter is degraded                                                                       |
| `anthropic`       | `anthropic/claude-opus-5-5`                       | Opus 5.5 for research/review and the degraded same-family counter, Opus 5 for implement, Sonnet 5 cheap lanes                                                                                                                       |
| `codex`           | `openai-codex/gpt-6-sol`                          | GPT-6 Sol for research/review/memory and at medium effort for implement, GPT-6 Luna for mechanical, GPT-6 Sol at review's effort as the degraded same-family counter                                                                |
| `openrouter-free` | `openrouter/deepseek/deepseek-v4-flash-0731:free` | OpenRouter `:free` ids only: DeepSeek V4 Flash for research/review at max, Nex N2.5 Pro for implement and the cross-family counter, Nex N2.5 Mini cheap lanes; rate-limited upstream and only as stable as OpenRouter's free roster |
| `nvidia-free`     | `nvidia/z-ai/glm-5.3-flash`                       | NVIDIA NIM free endpoints only: GLM 5.3 Flash on every lane (research/review at max, the rest at high; the same-model counter is degraded); needs `NVIDIA_API_KEY`                                                                  |

`default` is a reserved name, not a key: it means `session_models.pi` + `category_models.pi` themselves, because those two sections are the shared schema every generator, the committed projection and the OpenRouter wrappers read. `local` runs entirely on the [llama.cpp router](./llama-cpp/index.md), so it needs no subscription provider and no network.

The active name is one line in `${XDG_STATE_HOME:-$HOME/.local/state}/chezmoi/pi-model-profile`, outside the source state: the pick is per machine, not per commit. `pi-model-profile.partial` reads it at apply time, so `agent-model.partial`, `review-agent-model.partial` and `agent-thinking.partial` render the active rows into the 16 Pi agent profiles, and the Pi merge hook patches `defaultProvider`/`defaultModel`/`defaultThinkingLevel` in `~/.pi/agent/settings.json` from the active session row. With no state file everything renders the `codex` profile (user call 2026-09-23); `default` stays selectable by name, and its OpenRouter rows remain the schema the OpenRouter launchers read. An unrecognised name fails the apply instead of falling back, because a silent fallback would restore the rows the profile exists to replace.

Every structural rule that holds for the default Pi rows holds for each profile: six categories, no `:level` suffix, `long` context except `memory`, `implement` distinct from both `mechanical` and the session (except in a single-model profile such as `local` or `nvidia-free`, which has no second pick), and a declared `verifier_status` on `refute`.

Inside a running Pi session the same switch is `/model-profile` ([`pi-model-profile.ts`](../../../home/dot_pi/agent/exact_extensions/pi-model-profile.ts)): it drives the same picker, then re-points only that session's model and thinking level from the profile's session row, because the apply reaches new sessions and subagents rather than the one already running.

`harnesses.pi` in the generated band projection stays the `default` profile regardless of the active name. Nothing in Pi reads it; its readers are the `*-openrouter` wrappers, which filter to `openrouter/` rows and would lose every lane on a non-OpenRouter profile. Read it as "the OpenRouter wrapper lane table", not "what Pi runs now".

### OMP

OMP is the one harness with native role indirection. Native `extendedContext: true` gives the root long context while role pins stay unchanged, so category rows are spelled as `@role` tokens and [`readonly_config.yml.tmpl`](../../../home/dot_omp/private_agent/readonly_config.yml.tmpl)'s `modelRoles` prices them in one profile-independent block. `modelRoles.default` is generated from `session_models.omp`. Installed `omp/18.0.3` reports `default`, `smol`, `vision`, `slow`, `plan`, `task`, and `advisor` from `omp config get modelRoles`; the repo uses those role names as local implementation detail, not as the portable taxonomy.

| Category               | Token      | `modelRoles` (both profiles)    | Tier | Verifier status |
| ---------------------- | ---------- | ------------------------------- | ---- | --------------- |
| `research`, `review`   | `@default` | `openai-codex/gpt-6-sol:high`   | T1   | —               |
| `implement`            | `@task`    | `openai-codex/gpt-6-sol:medium` | T2   | —               |
| `mechanical`, `memory` | `@smol`    | `openai-codex/gpt-6-luna:high`  | T3   | —               |
| `refute`               | `@advisor` | `openai-codex/gpt-6-sol:high`   | —    | degraded        |

Verified on 17.2.4: a profile carrying `model: "@smol"` runs on `modelRoles.smol`, and an unknown token fails loudly with `Error: No model selected.` rather than falling back. Provider and model are separated by `/`, never `:` — `cursor:` parses as a bogus provider. Like Pi, OMP's `:<level>` suffix is a single thinking dial the runtime maps straight onto `reasoning`, so "high effort, non-thinking" is not expressible here. User call 2026-09-23: one profile-independent `modelRoles` block ahead of the `isWork` branch, now entirely on the `openai-codex` provider and mirroring `category_models.codex` — `default` on `gpt-6-sol:high` with `slow`/`plan` at `:max` (T1), `vision` on `gpt-6-luna:high`, `task` on `gpt-6-sol:medium` (T2: the native `task` agent and every implement worker land there), `smol` on `gpt-6-luna:high` (T3), `tiny` and `commit` on `gpt-6-luna:medium`, and `advisor` on `gpt-6-sol:high`; every built-in role is pinned so nothing falls through to the harness default. It replaced the 2026-09-07 `openrouter` block (Muse Spark 1.3 primaries, GLM 5.3 task, GLM 5.3 Flash smol, Grok 4.6 advisor). That block replaced the 2026-08-30 split (work on the Cursor backend with `cursor/gpt-5.5:xhigh` primaries, personal on the Codex backend with `openai-codex/gpt-5.5:xhigh`, both with `smol` on `cursor/default`): every `@smol` lane (bundled `scout`/`sonic`) ran over the `cursor-agent` transport and settled `failed (exit 1)` once Cursor's free-request limit hit mid-run.

`memory` rides `@smol` again. Between 2026-08-29 and 2026-09-07 it bypassed the role table, pinned directly to `openrouter/google/gemini-3.7-flash:high`: DeepSeek V4 Flash (then `modelRoles.smol`) failed the live scribe probes (stored a known duplicate on Pi; hung as OMP scribe, killed at 9 min, 2026-08-28), while Gemini 3.7 Flash returned the correct `duplicate of <id>` on the same fixture. With `smol` on GPT-6 Luna the role token is the pick, so `mechanical` and `memory` share one T3 role. The `:<level>` suffix in `modelRoles` is load-bearing: [`agent-model.partial`](../../../home/.chezmoitemplates/agent-model.partial) renders only the model string into the agent frontmatter (the registry `effort` field is never rendered for OMP), and OMP's spawn precedence honors an explicit `:level` suffix over its defaults (`task/executor.ts`: effort > `:level` suffix > agent-definition default > pattern-derived).

Background advice is disabled (`advisor.enabled: false`, `advisor.subagents: false`, and `task.agentAdvisor.task: "off"`). The `modelRoles.advisor` selector is retained for explicit final refutation, not automatic advice. `review` rides `@default` (GPT-6 Sol) and `refute` resolves `@advisor` (`openai-codex/gpt-6-sol:high`); the registry declares `verifier_status: degraded` on the refute row, because the advisor is the same OpenAI model as the primaries (same call as `category_models.codex.refute`).

## Native subagent takeover risk

Every harness that can spawn subagents has its own **native** default model for that path — separate from anything this repo's registry declares — and an unpinned harness silently falls back to whatever that native default is. This is the risk this taxonomy exists to close, not just document. `agent_bindings` therefore lists built-in names (Codex's `worker`, Antigravity's `generalist`, Cursor's `generalPurpose`) next to the repo-authored profiles, and the gate covers the call sites that no profile can reach.

| Harness         | Takeover risk                                      | Status                                                                                                                                   |
| --------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Cursor**      | Task children can fall back to the parent model.   | The gate writes only a captured base id. Effort is intentionally absent from the payload because Cursor reads it from saved user config. |
| **Codex**       | Omitted model/effort uses native defaults.         | Profiles and the gate carry model plus effort.                                                                                           |
| **Claude Code** | Built-ins and background agents have own defaults. | Repo profiles and alias-aware gate routing constrain managed agents.                                                                     |
| **Antigravity** | Dynamic subagents inherit without a tier.          | Review roles are invoked with the native `flash` tier; the category key is `antigravity`.                                                |
| **Pi**          | Managed profiles can omit model or thinking.       | Every profile renders a category-backed `model` and separate `thinking` value.                                                           |
| **OMP**         | Profiles can fall through to native defaults.      | Repo profiles carry `@role` tokens resolved by `modelRoles`.                                                                             |

## Related

- [Subagents](subagents.md) — cross-harness subagent discovery and profile topology
- [Model registry & routing](model-registry.md) — the underlying `.chezmoidata/ai_models/` sections and generators
- [Scenarios](scenarios.md) — when to reach for which skill/flow; this page's buckets refine that page's "smallest flow that fits" default with model/placement specifics

## Staged execution

Only the root owns transitions. Research/production workers do not verify. Deep/high-risk final judgment retains review and adversarial lenses on distinct questions against the same candidate, not a reviewer-of-reviewer chain. OMP background advisors remain disabled; async commands and explicit effort controls are preserved. Managed task profiles use blocking returns and no child spawning. Profiles retain registry model selection.
