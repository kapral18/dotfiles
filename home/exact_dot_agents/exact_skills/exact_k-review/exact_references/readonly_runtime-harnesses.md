# Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-deep-review` uses those native mechanisms plus the role-specific contracts in `references/`.

Read this file only for capability caveats that affect orchestration.

## Model policy

- Model selection is **registry-driven and deterministic**: every repo-owned profile's `model` frontmatter is rendered from the single `agent_review_models` block in the chezmoi model registry (`home/.chezmoidata/ai_models/tiering.yaml`).
  Updating a model is a one-line registry edit plus `chezmoi apply`; model ids never live hand-written in profile files.
- Registry values per harness: `lanes` (angle lanes, auditors, controller, named fresh-eyes profiles, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — prefer a **different model family than `lanes`** at equal capability per SOP §3.7; never trade capability for family diversity — a strong same-family verifier beats a weaker cross-family one.
  Same-family runs keep refutation framing and report the reduced independence, never hidden).
  Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model;
  named fresh-eyes profiles carry the same registry-rendered frontmatter.
  Any harness-served generic/default subagent must also receive that model; always pass the registry's concrete lane value rather than letting the runtime pick an implicit default.
- Empty registry value = the profile omits the field and the harness config default applies; `inherit` = harness-native parent inheritance.
  Empty is allowed only for a deliberately documented default path.
  Current review-lane registry values are concrete for Cursor, Copilot, Codex, Antigravity, Pi, and OMP;
  launches that omit a model in those harnesses are a bug because they bypass the matrix.
  Claude uses `inherit` intentionally because Claude sessions are launched on a deliberate model and the installed Task resolver has been verified to inherit from the parent.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

## Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Registry: `lanes: inherit` — Claude sessions run a deliberately chosen model, and review profiles use `model: inherit`.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` pins `CLAUDE_CODE_SUBAGENT_MODEL` and all family defaults to `deepseek/deepseek-v4-flash-0731@preset/effort-max`; the `effort-max` slug carries max reasoning effort.
- Adversarial verifier: single-family surface, always `families=same (degraded)`;
  launch a general-purpose `Task` carrying `adversarial-verifier.md`.

## Codex

Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Launch angle lanes as `review-worker` agents; the verifier as the `adversarial-verifier` agent.
Registry: both values are concrete (`gpt-5.6-sol` at xhigh effort via profile `model` + `model_reasoning_effort`);
every Codex role also pins `service_tier = "default"`.
Always pass an explicit model when launching a native Codex `spawn_agent`/generic subagent:
the installed catalog does not make omitted defaults auditable, and uncataloged slugs can pass through with fallback metadata.

## Antigravity CLI

Run `/k-deep-review` in the main Antigravity session. Dynamic subagents cannot invoke further subagents.
Antigravity has no repo-owned profile-file surface; define each needed role with `define_subagent`, point its system prompt at the matching shared role contract, then launch it through `invoke_subagent`.
The `invoke_subagent` model field accepts only `inherit`, `flash_lite`, `flash`, or `pro`, so the registry stores `pro` for both lanes and verifier.
Use `pro` for review, audit, and refutation lanes.
The model surface is Gemini-only, so report `families=same (degraded)` for adversarial verification.

## Cursor

- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads `.cursor/agents` profile files.
  Launch angle lanes through the `review-worker` profile and the verifier through the `adversarial-verifier` profile;
  both carry registry-rendered `model` frontmatter.
- Registry `lanes` and `verifier` are both `cursor-grok-4.6-xhigh`.
  `model_bands.cursor.max` carries no counter, so the adversarial verifier runs `families=same (reduced independence)`;
  keep refutation framing and report that, never skip the phase and never present it as a cross-family pass.
  Omitted/default Cursor subagents can resolve to `composer-2.8-fast`; the CLI default selector is `auto`.
  Treat any omitted Cursor subagent model as a matrix bypass.
- Same-name custom profiles do **not** shadow native Cursor enum agents (`explore`, `debug`, `cursor_guide`, `unspecified`):
  custom profiles are carried as a separate `custom` oneof with a `name`, while native cases are distinct empty oneof variants.
  Same-name templates will leave native Explore in place, so rely on distinct custom profile names instead.
- When the active Task schema exposes only generic subagent types, pass the same registry values as explicit `model` arguments —
  the registry stays the single source either way.
  Generic fresh-eyes launches pass the registry lane model; never let Cursor `auto` choose the model for review workers.
- Cursor's `readonly` flag is a hard tool restriction, not the `/k-deep-review` behavior-level read-only boundary.
  Cursor source shows `readonly: true` blocks shell, write, delete, and MCP operations.
  Keep Cursor profile frontmatter and Task launches at `readonly: false`; the worker contracts enforce no-mutation behavior.
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/Playwriter, discard that launch result and rerun with `readonly: false` before accepting `verification_needed`.
- If Cursor cannot await background subagent ids, wait through the native paths below instead of looping blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Keep reviewer, PR-necessity, live-UI, and findings-audit workers as real Cursor background subagents;
  use Cursor Task `run_in_background=true` when the active Task schema exposes it. Wait through a Cursor-native subagent completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.

## Copilot CLI

- Copilot profiles carry registry-rendered `model` frontmatter (`lanes` on workers/auditors/controller, `verifier` on `adversarial-verifier`).
  The managed `~/.copilot/settings.json` subagent entries also include registry-aligned `model`/`effortLevel`/`contextTier` so stale target-only model overrides cannot survive Copilot's settings merge.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent registry lane value.
- Launch angle lanes as the `review-worker` agent type (model-invocable, not user-invocable).
  Use `general-purpose` only when a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.

## Pi and OMP

- Pi and OMP launch subagents through named profiles; per-task/per-profile `model` is honored over the worker default, and Pi thinking is encoded as a `:<thinking>` suffix on the model string.
- Registry: both `lanes` and `verifier` are concrete.
  Pi review workers and fresh-eyes run `openrouter/deepseek/deepseek-v4-flash-0731:max`;
  adversarial/criteria verifiers run `openrouter/openai/gpt-5.6-terra:max`, keeping refutation cross-family.
  OMP resolves review roles through its own `modelRoles`.
  Work prices primary roles to `openrouter/deepseek/deepseek-v4-flash-0731:max` and keeps `vision` on `openrouter/moonshotai/kimi-k3:high`.
  Personal pins `default` and `advisor` to `cursor/cursor-grok-4.6-xhigh`, so `model_bands.omp.max` carries no counter.
  Adversarial and criteria verifiers follow `@default` with the review lanes, so refutation is same-family on both profiles (reduced independence).
  Personal `smol` stays on `cursor/composer-2.8:high`.
  Other repo-owned Pi/OMP profiles resolve their model from the band registry (`agent_bindings` → `agent_categories` → `model_bands`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
