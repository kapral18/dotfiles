# Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-deep-review` uses those native mechanisms plus the role-specific contracts in `references/`.

Read this file only for capability caveats that affect orchestration.

## Model policy

- Model selection is **registry-driven and deterministic**: every repo-owned review profile's `model` frontmatter is rendered through `review-agent-model.partial`, which derives from `agent_bindings`, `agent_categories`, `category_models`, and sparse `review_model_overrides` in `home/.chezmoidata/ai_models/tiering.yaml`.
  Updating a derivable review model is a one-line category row edit plus `chezmoi apply`;
  model ids never live hand-written in profile files.
- Resolver slots per harness: `lanes` (angle lanes, auditors, controller, named fresh-eyes profiles, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — prefer a **different model family than `lanes`** at equal capability per SOP §3.7; never trade capability for family diversity — a strong same-family verifier beats a weaker cross-family one.
  Same-family runs keep refutation framing and report the reduced independence, never hidden).
  Generic fresh-eyes launches must pass the resolved lane model as the profile-equivalent model;
  named fresh-eyes profiles carry the same resolver-rendered frontmatter.
  Any harness-served generic/default subagent must also receive that model; always pass the resolved concrete lane value rather than letting the runtime pick an implicit default.
- Empty resolved value = the profile omits the field and the harness config default applies; `inherit` = harness-native parent inheritance.
  Empty is allowed only for a deliberately documented default path.
  Current review-lane resolved values are concrete for Cursor, Copilot, Codex, Antigravity, Pi, and OMP;
  launches that omit a model in those harnesses are a bug because they bypass the matrix.
  Claude uses `inherit` intentionally because Claude sessions are launched on a deliberate model and the installed Task resolver has been verified to inherit from the parent.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

## Verifier launch ladder

One ladder for every refutation/verification lane (`k-agent-adversarial-verifier`, `k-agent-criteria-verifier`, and the blind `k-agent-fresh-eyes`).
Take the first rung the active harness can actually serve, name the rung taken, and never skip the phase:

1. **Named profile.**
   Launch the deployed `k-agent-<role>` profile; its resolver-rendered `model` frontmatter already carries the `refute` value (`lanes`, for fresh-eyes).
   Verifier profiles are fielded on Claude Code, Codex, Copilot, Cursor (project-level `.cursor/agents` only), Pi, and OMP;
   the blind fresh-eyes profile exists on Claude Code, Pi, and OMP (`fresh-eyes.md` owns its per-harness rows).
2. **Generic type + explicit registry refute model.**
   Where the named profile is unreachable, launch the harness's generic subagent type and pass `category_models.<harness>.refute` explicitly: Cursor `generalPurpose`, Codex `worker`, Copilot `task`.
   An omitted model is a matrix bypass, not a default.
3. **Antigravity.**
   `define_subagent` the `k-agent-<role>` identifier from its shared role contract, then `invoke_subagent` it at `pro` (`flash` is for the cheap lanes only).
4. **Inline-degraded.**
   Only when the harness exposes no isolated spawn at all: run the Candidate Refutation Ladder (`judging_core.md`) in the controller and report `adversarial=inline-degraded`.

Report the resolver's family status (`families=cross` / `families=same (degraded)`) with the rung, never silently.
A delegated leaf never spawns a verifier and never verifies its own claims (SOP §3.7); it returns the fork to its controller as a blocker.

## Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Review override: `lanes: inherit` — Claude sessions run a deliberately chosen model, and review profiles use `model: inherit`.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` keeps the root session on the selected OpenRouter wire model and, because Claude Code's Agent schema accepts aliases only, routes delegated lanes through a 4-alias map along the tier ladder: `fable` → `anthropic/claude-fable-5.1@preset/effort-high` (T1 orchestrate/research/review), `opus` → `openai/gpt-5.6-sol@preset/effort-high` (T2 implement, also the `CLAUDE_CODE_SUBAGENT_MODEL` default), `sonnet` → `deepseek/deepseek-v4-flash@preset/effort-xhigh` (mechanical), `haiku` → `google/gemini-3.8-flash@preset/effort-low` (memory).
  Four aliases cannot carry five tiers: Pi's refute pick (`openrouter/openai/gpt-5.6-sol:xhigh`) has no alias of its own, and the gate maps every `gpt`/`openai` backend id to `opus`, so a refute launch on this route runs the T2 SOL wire model at high instead of xhigh.
  That substitute is still a different family than the Anthropic T1 lanes: report `cross_family (T2 substitute)` in the launch line;
  do not redesign the wrapper to add a tier.
- Adversarial verifier, criteria verifier, and fresh-eyes are repo-owned named profiles (`k-agent-adversarial-verifier`, `k-agent-criteria-verifier`, `k-agent-fresh-eyes`) whose resolver-rendered frontmatter emits `inherit` today; launch them by name — rung 1 of the Verifier launch ladder, not a generic task.
  The model surface is still one family, so keep reporting `families=same (degraded)`.

## Codex

Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Launch angle lanes as `k-agent-review-worker` agents; the verifier as the `k-agent-adversarial-verifier` agent.
Registry: both values are concrete (`gpt-6-astra` at `high` effort via profile `model` + `model_reasoning_effort`) —
review and refute are the only Codex roles Astra is priced for; orchestrate/research ride `gpt-5.6-sol` and implement/mechanical/memory ride `gpt-5.6-terra`.
Every Codex role also pins `service_tier = "default"`.
Always pass an explicit model when launching a native Codex `spawn_agent`/generic subagent (the generic type is `worker`):
the installed catalog does not make omitted defaults auditable, and uncataloged slugs can pass through with fallback metadata.

## Antigravity CLI

Run `/k-deep-review` in the main Antigravity session. Dynamic subagents cannot invoke further subagents.
Antigravity has no repo-owned profile-file surface; define each needed role with `define_subagent`, point its system prompt at the matching shared role contract, then launch it through `invoke_subagent`.
Every dynamically defined repo-owned role MUST use its `k-agent-<role>` identifier.
The `invoke_subagent` model field accepts only `inherit`, `flash_lite`, `flash`, or `pro`, so the registry stores `pro` for both lanes and verifier.
Use `pro` for review, audit, and refutation lanes.
Use `flash` for the cheap lanes: `k-agent-mechanical` (edit or exact-retrieval packets) and `k-agent-smol` (memory);
it is the tier the registry's `gemini-3.8-flash` mechanical/memory rows map onto. Do NOT launch either on `inherit` or `pro`.
The model surface is Gemini-only, so report `families=same (degraded)` for adversarial verification.

## Cursor

- Transcript exports label the delegation tool `Subagent` (2026-09-04 export), while the cursor-agent 2026.09.02 bundle still names the call type `taskToolCall`; the `tool_name` the preToolUse hook receives is unverified.
  The band gate therefore matches both `Task` and `Subagent`; a launch that passes a non-registry `model` is rewritten to the subagent type's band either way.
- Generic adversarial-verifier launch: `subagent_type: generalPurpose` with `model:` set to the registry refute value.
  The gate leaves a registry counter model untouched on a generic type, so the cross-family verifier survives the rewrite;
  any other explicit model does not.
- Generic cheap-lane launch (`k-agent-mechanical`, `k-agent-smol` are undiscoverable at user level):
  `subagent_type: generalPurpose` with `model:` set to the registry mechanical/memory value (`auto`).
  The gate passes a registry cheap-lane model through on the generic type exactly like a counter model.
- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads **project-level** `.cursor/agents` profile files only;
  user-level `~/.cursor/agents` is never scanned (probed 2026-08-30, cursor-agent 2026.08.28-a7f9513), so home-deployed profiles are unreachable.
  Where a workspace carries `k-agent-review-worker`/`k-agent-adversarial-verifier` profiles, launch lanes through them;
  both carry resolver-rendered `model` frontmatter.
- Resolved `lanes` are `gpt-5.6-sol-high`; resolved `verifier` is `claude-fable-5-1-thinking-high`.
  `category_models.cursor.refute` carries `verifier_status: cross_family`, so the adversarial verifier runs as a cross-family lane.
  Omitted/default Cursor subagents can resolve to `composer-2.5-fast`; the CLI default selector is `auto`.
  Treat any omitted Cursor subagent model as a matrix bypass.
- Same-name custom profiles do **not** shadow native Cursor enum agents (`explore`, `debug`, `cursor_guide`, `unspecified`):
  custom profiles are carried as a separate `custom` oneof with a `name`, while native cases are distinct empty oneof variants.
  Do not add same-name templates expecting them to override native Explore.
- When the active Task schema exposes only generic subagent types, pass the same resolved values as explicit `model` arguments —
  the resolver stays the single source either way.
  Generic fresh-eyes launches pass the resolved lane model; never let Cursor `auto` choose the model for review workers.
- Cursor's `readonly` flag is a hard tool restriction, not the `/k-deep-review` behavior-level read-only boundary.
  Cursor source shows `readonly: true` blocks shell, write, delete, and MCP operations.
  Keep Cursor profile frontmatter and Task launches at `readonly: false`; the worker contracts enforce no-mutation behavior.
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/Playwriter, discard that launch result and rerun with `readonly: false` before accepting `verification_needed`.
- If Cursor cannot await background subagent ids, do not loop blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Keep reviewer, PR-necessity, live-UI, and findings-audit workers as real Cursor background subagents;
  use Cursor Task `run_in_background=true` when the active Task schema exposes it. Wait through a Cursor-native subagent completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.

## Copilot CLI

- Copilot profiles carry resolver-rendered `model` frontmatter (`lanes` on workers/auditors/controller, `verifier` on `k-agent-adversarial-verifier`).
  The managed `~/.copilot/settings.json` subagent entries also include resolver-aligned `model`/`effortLevel`/`contextTier` so stale target-only model overrides cannot survive Copilot's settings merge.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent resolved lane value.
- Launch angle lanes as the `k-agent-review-worker` agent type (model-invocable, not user-invocable).
  Do not use the generic `task` type unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason; a fallback launch passes the registry model explicitly (rung 2 of the Verifier launch ladder).

## Pi and OMP

- Pi and OMP launch subagents through named profiles; per-task/per-profile `model` is honored over the worker default, and Pi thinking is encoded as a `:<thinking>` suffix on the model string.
- Resolved `lanes` and `verifier` are concrete.
  Pi review workers and fresh-eyes run `anthropic/claude-fable-5.1:high` (the Pi session's own T1 model);
  adversarial and criteria verifiers run `openrouter/openai/gpt-5.6-sol:xhigh` —
  the same model as the T2 implement row at a higher effort, but a different family than the Anthropic T1 lanes it audits, so `category_models.pi.refute` carries `verifier_status: cross_family`.
  OMP resolves review roles through its own `modelRoles`.
  One profile-independent `modelRoles` block prices default/vision/slow/plan to `anthropic/claude-fable-5.1:high`, `task` (the T2 implement lane) to `anthropic/claude-opus-5:high`, `smol` to `anthropic/claude-sonnet-5:high` (memory rides `@smol`), `tiny` and `commit` to `anthropic/claude-sonnet-5:medium`, and `advisor` to `openai-codex/gpt-6-astra:high` on both work and personal.
  Every `category_models.omp.*` row carries effort `high`; the `@role` token itself carries the real tier.
  Adversarial and criteria verifiers follow `@advisor`, a different family than the Anthropic lanes, so `category_models.omp.refute` marks `verifier_status: cross_family`.
  Other repo-owned Pi/OMP profiles resolve their model from the review resolver or category registry (`agent_bindings` → `agent_categories` → `category_models`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
