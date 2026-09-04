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

## Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Review override: `lanes: inherit` — Claude sessions run a deliberately chosen model, and review profiles use `model: inherit`.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` keeps the root session on the selected OpenRouter wire model and maps delegated lanes through Pi's OpenRouter schema: GPT-5.5 xhigh for primary categories, DeepSeek V4 Flash xhigh for mechanical, and Sonnet 4.6 xhigh for refute.
  Claude Code's Agent schema accepts aliases only, so the wrapper points `fable`/`opus`, `haiku`, and `sonnet` at those OpenRouter preset wire ids.
- Adversarial verifier: single-family surface, always `families=same (degraded)`;
  launch a general-purpose `Task` carrying `adversarial-verifier.md`.

## Codex

Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Launch angle lanes as `k-agent-review-worker` agents; the verifier as the `k-agent-adversarial-verifier` agent.
Registry: both values are concrete (`gpt-5.5` at xhigh effort via profile `model` + `model_reasoning_effort`);
every Codex role also pins `service_tier = "default"`.
Always pass an explicit model when launching a native Codex `spawn_agent`/generic subagent:
the installed catalog does not make omitted defaults auditable, and uncataloged slugs can pass through with fallback metadata.

## Antigravity CLI

Run `/k-deep-review` in the main Antigravity session. Dynamic subagents cannot invoke further subagents.
Antigravity has no repo-owned profile-file surface; define each needed role with `define_subagent`, point its system prompt at the matching shared role contract, then launch it through `invoke_subagent`.
Every dynamically defined repo-owned role MUST use its `k-agent-<role>` identifier.
The `invoke_subagent` model field accepts only `inherit`, `flash_lite`, `flash`, or `pro`, so the registry stores `pro` for both lanes and verifier.
Use `pro` for review, audit, and refutation lanes.
The model surface is Gemini-only, so report `families=same (degraded)` for adversarial verification.

## Cursor

- Transcript exports label the delegation tool `Subagent` (2026-09-04 export), while the cursor-agent 2026.09.02 bundle still names the call type `taskToolCall`; the `tool_name` the preToolUse hook receives is unverified.
  The band gate therefore matches both `Task` and `Subagent`; a launch that passes a non-registry `model` is rewritten to the subagent type's band either way.
- Generic adversarial-verifier launch: `subagent_type: generalPurpose` with `model:` set to the registry refute value.
  The gate leaves a registry counter model untouched on a generic type, so the cross-family verifier survives the rewrite;
  any other explicit model does not.
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
  Do not use `general-purpose` unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.

## Pi and OMP

- Pi and OMP launch subagents through named profiles; per-task/per-profile `model` is honored over the worker default, and Pi thinking is encoded as a `:<thinking>` suffix on the model string.
- Resolved `lanes` and `verifier` are concrete.
  Pi review workers and fresh-eyes run `openrouter/openai/gpt-5.5:xhigh`; adversarial/criteria verifiers run `openrouter/anthropic/claude-sonnet-4.6:xhigh`, keeping refutation cross-family.
  OMP resolves review roles through its own `modelRoles`.
  The work profile prices default/vision/slow/plan/task to `cursor/gpt-5.5:xhigh`, `smol` to `cursor/default` (Cursor's Auto router), and `advisor` to `cursor/claude-opus-5-high:high`.
  The personal profile prices default/vision/slow/plan/task and `advisor` to `openai-codex/gpt-5.5:xhigh` (OpenAI-only catalog), and `smol` to `cursor/default`.
  Adversarial and criteria verifiers follow `@advisor`; `category_models.omp.refute` marks `verifier_status: reduced_independence`.
  Other repo-owned Pi/OMP profiles resolve their model from the review resolver or category registry (`agent_bindings` → `agent_categories` → `category_models`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
