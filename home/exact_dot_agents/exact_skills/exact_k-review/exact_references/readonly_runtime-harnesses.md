# Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-deep-review` uses those native mechanisms plus the role-specific contracts in `references/`.

Read this file only for capability caveats that affect orchestration.

## Model policy

- Model selection is **registry-driven and deterministic**: every repo-owned profile's `model` frontmatter is rendered from the single `agent_review_models` block in the chezmoi model registry (`home/.chezmoidata/ai_models/tiering.yaml`).
  Updating a model is a one-line registry edit plus `chezmoi apply`; model ids never live hand-written in profile files.
- Registry values per harness: `lanes` (angle lanes, auditors, controller, named fresh-eyes profiles, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — ideally a **different model family than `lanes`**, but policy may choose same-family and accept degraded refutation).
  Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model;
  named fresh-eyes profiles carry the same registry-rendered frontmatter.
  Any harness-served generic/default subagent must also receive that model; never let the runtime pick an implicit default when the registry has a concrete lane value.
- Empty registry value = the profile omits the field and the harness config default applies; `inherit` = harness-native parent inheritance.
  Empty is allowed only for a deliberately documented default path.
  Current review-lane registry values are concrete for Cursor, Copilot, Codex, Gemini, Pi, and OMP;
  launches that omit a model in those harnesses are a bug because they bypass the matrix.
  Claude uses `inherit` intentionally because Claude sessions are launched on a deliberate model and the installed Task resolver has been verified to inherit from the parent.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

## Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Registry: `lanes: inherit` — Claude sessions run a deliberately chosen model, and review profiles use `model: inherit`.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` pins `CLAUDE_CODE_SUBAGENT_MODEL` and all family defaults to `openai/gpt-5.2` at `high`;
  this is the deliberate global override for that strict route.
- Adversarial verifier: single-family surface, always `families=same (degraded)`;
  launch a general-purpose `Task` carrying `adversarial-verifier.md`.

## Codex

Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Launch angle lanes as `review-worker` agents; the verifier as the `adversarial-verifier` agent.
Registry: both values are concrete (`gpt-5.6-terra` at high effort via profile `model` + `model_reasoning_effort`).
Never launch a native Codex `spawn_agent`/generic subagent without a model: the installed catalog does not make omitted defaults auditable, and uncataloged slugs can pass through with fallback metadata.

## Gemini CLI

Gemini subagents cannot call other subagents, so run `/k-deep-review` in the main Gemini session.
Do not run the controller itself as a Gemini subagent.
The model surface is Gemini-only: the adversarial verifier is `families=same (degraded)`; launch it as the `adversarial-verifier` profile.
Registry: both values are concrete (`gemini-3.1-pro-preview`).
Profiles carry registry-rendered `model` frontmatter; do not rely on the configured Gemini default for review workers.

## Cursor

- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads `.cursor/agents` profile files.
  Launch angle lanes through the `review-worker` profile and the verifier through the `adversarial-verifier` profile;
  both carry registry-rendered `model` frontmatter.
- The registry pins concrete Cursor lane/verifier models deliberately, and both are now `gpt-5.6-terra-max` (the cost-driven ban closed 2026-08-03 moved the lanes off `claude-opus-5-high`, which had made this pairing cross-family).
  `model_bands.cursor.max` therefore carries no counter and the adversarial verifier is `families=same (degraded)`;
  report the degradation, never present it as a real cross-family pass.
  The user verified via expenditure dashboard that Cursor-served omitted/default subagents can resolve to `composer-2.5-fast`;
  local safe probes also show the CLI default selector as `auto` and `composer-2.5-fast` as an available legacy alias target.
  Treat any omitted Cursor subagent model as a matrix bypass.
- Same-name custom profiles do **not** shadow native Cursor enum agents (`explore`, `debug`, `cursor_guide`, `unspecified`):
  custom profiles are carried as a separate `custom` oneof with a `name`, while native cases are distinct empty oneof variants.
  Do not add same-name templates expecting them to override native Explore.
- When the active Task schema exposes only generic subagent types, pass the same registry values as explicit `model` arguments —
  the registry stays the single source either way.
  Generic fresh-eyes launches pass the registry lane model; never let Cursor `auto` choose the model for review workers.
- Cursor's `readonly` flag is a hard tool restriction, not the `/k-deep-review` behavior-level read-only boundary.
  Cursor source shows `readonly: true` blocks shell, write, delete, and MCP operations.
  Keep Cursor profile frontmatter and Task launches at `readonly: false`; the worker contracts enforce no-mutation behavior.
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/SCSI/Playwriter, discard that launch result and rerun with `readonly: false` before accepting `verification_needed`.
- If Cursor cannot await background subagent ids, do not loop blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Keep reviewer, PR-necessity, live-UI, and findings-audit workers as real Cursor background subagents;
  use Cursor Task `run_in_background=true` when the active Task schema exposes it. Wait through a Cursor-native subagent completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.

## Copilot CLI

- Copilot profiles carry registry-rendered `model` frontmatter (`lanes` on workers/auditors/controller, `verifier` on `adversarial-verifier`).
  The managed `~/.copilot/settings.json` subagent entries also include registry-aligned `model`/`effortLevel`/`contextTier` so stale target-only model overrides cannot survive Copilot's settings merge.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent registry lane value.
- Launch angle lanes as the `review-worker` agent type (model-invocable, not user-invocable).
  Do not use `general-purpose` unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.

## Pi and OMP

- Pi and OMP launch subagents through named profiles; per-task/per-profile `model` is honored over the worker default, and Pi thinking is encoded as a `:<thinking>` suffix on the model string.
- Registry: both `lanes` and `verifier` are concrete.
  Pi review workers, fresh-eyes, and adversarial/criteria verifiers all use `openrouter/openai/gpt-5.2:high`:
  Pi reaches models only through OpenRouter, so no second family is available to refute with.
  OMP resolves review roles through its own `modelRoles`, and both profiles pin `default` and `advisor` to the same `cursor/gpt-5.2-high:high`.
  There is therefore no second family to refute with: the registry names `@default` for both lanes and verifier, `model_bands.omp.max` carries no counter, and the adversarial verifier is `families=same (degraded)` — same posture as Pi, Codex, Gemini, Cursor, and Claude Code.
  `smol` stays on the cursor/openai-codex codex tier.
  An invariant asserts that OMP carries a counter only while `modelRoles.advisor` differs from `modelRoles.default`, so restoring cross-family refutation means changing the role pin first, not the band.
  The cost-driven ban on opus-5/gpt-5.5 (closed 2026-08-03) moved the lanes off those models.
  Other repo-owned Pi/OMP profiles resolve their model from the band registry (`agent_bindings` → `agent_categories` → `model_bands`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
