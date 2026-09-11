# Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-deep-review` uses those native mechanisms plus the role-specific contracts in `~/.agents/skills/k-review/references/`.

Read this file only for capability caveats that affect orchestration.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.

### Model policy

- Model selection is **registry-driven and deterministic**: every repo-owned review profile's `model` frontmatter is rendered through `review-agent-model.partial`, which derives from `agent_bindings`, `agent_categories`, `category_models`, and sparse `review_model_overrides` in `home/.chezmoidata/ai_models/tiering.yaml`.
  Updating a derivable review model is a one-line category row edit plus `chezmoi apply`;
  model ids never live hand-written in profile files.
- Resolver slots per harness: `lanes` (angle lanes, auditors, controller, named fresh-eyes profiles, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — prefer a **different model family than `lanes`** at equal capability per SOP §3.7; never trade capability for family diversity — a strong same-family verifier beats a weaker cross-family one.
  Same-family runs keep refutation framing and report the reduced independence, never hidden).
  Named profiles carry their resolved model/effort controls; do not override those fields merely to repeat the profile.
  A supported generic fallback receives the resolved category controls through that harness's actual fields.
  Codex/Copilot use model plus reasoning effort; Cursor uses its model selector. Do not invent fields on another harness.
- Empty resolved value = the profile omits the field and the harness config default applies; `inherit` = harness-native parent inheritance.
  Empty is allowed only for a deliberately documented default path.
  Current review-lane resolved values are concrete for Cursor, Copilot, Codex, Antigravity, Pi, and OMP;
  Named profile pins satisfy that requirement without per-call overrides. Generic fallbacks must preserve the same category.
  Claude uses `inherit` intentionally because Claude sessions are launched on a deliberate model and the installed Task resolver has been verified to inherit from the parent.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

### Final judgment selection

Choose the applicable strong review/refute category and its resolved model/effort before launching a substantial final packet.
Use a reachable named profile, or a native generic type with the same explicit registry category model where supported.
Do not silently fall back to a weaker or more expensive model.
A missing capability is a reported limitation, not authority to bypass the category.
Fresh-eyes, criteria, hygiene, and adversarial profiles are optional task framings, not mandatory extra stages.
No child owns orchestration, verification of another reviewer, or a convergence loop.

### Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Review override: `lanes: inherit` — Claude sessions run a deliberately chosen model, and review profiles use `model: inherit`.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` uses the Pi backend matrix through session-projected native `--agents` definitions.
  Each managed profile carries its exact preset selector, including refute's distinct effort, while its prompt and skill preloads remain unchanged.
  The hook requires the fresh `AGENT_BAND_CLAUDE_ROUTES` role/pair map and removes call-level model overrides so the profile wins.
  Do not delegate with missing or stale profiles, conflicting inherited controls, a resume request, or a full-history fork.
  Do not substitute implementation effort for refutation. The caller's `--agents` cannot replace the managed projection.
- Adversarial verifier, criteria verifier, and fresh-eyes are repo-owned named profiles (`k-agent-adversarial-verifier`, `k-agent-criteria-verifier`, `k-agent-fresh-eyes`) whose resolver-rendered frontmatter emits `inherit` today; launch them by name — a named final packet when that framing is selected.
  The model surface is still one family, so keep reporting `families=same (degraded)`.

### Codex

Native Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Subscription wrappers use the backend matrix and the subscription boundary below instead of these native model pins.
Launch angle lanes as `k-agent-review-worker` agents; the verifier as the `k-agent-adversarial-verifier` agent.
Registry: both values are concrete (`gpt-6-astra` at `high` effort via profile `model` + `model_reasoning_effort`) —
review and refute are the only Codex roles Astra is priced for; orchestrate/research ride `gpt-5.6-sol` and implement/mechanical/memory ride `gpt-5.6-terra`.
Every Codex role also pins `service_tier = "default"`. Named Codex profiles retain their declared model/effort.
A native generic `worker` carrying another category must pass both resolved `model` and `reasoning_effort`.
Do not select a lane from model membership alone when one model serves multiple category efforts.

### Antigravity CLI

Run `/k-deep-review` in the main Antigravity session. Dynamic subagents cannot invoke further subagents.
Antigravity has no repo-owned profile-file surface; define each needed role with `define_subagent`, point its system prompt at the matching shared role contract, then launch it through `invoke_subagent`.
Every dynamically defined repo-owned role MUST use its `k-agent-<role>` identifier.
The `invoke_subagent` model field accepts only `inherit`, `flash_lite`, `flash`, or `pro`, so the registry stores `pro` for both lanes and verifier.
Use `pro` for review, audit, and refutation lanes.
Use `flash` for the cheap lanes: `k-agent-mechanical` (edit or exact-retrieval packets) and `k-agent-smol` (memory);
it is the tier the registry's `gemini-3.8-flash` mechanical/memory rows map onto. Do NOT launch either on `inherit` or `pro`.
The model surface is Gemini-only, so report `families=same (degraded)` for adversarial verification.

### Cursor

- Transcript exports label the delegation tool `Subagent` (2026-09-04 export), while the cursor-agent 2026.09.02 bundle still names the call type `taskToolCall`; the `tool_name` the preToolUse hook receives is unverified.
  The band gate therefore matches both `Task` and `Subagent`; a launch that passes a non-registry `model` is rewritten to the subagent type's band either way.
- Generic adversarial-verifier launch: `subagent_type: generalPurpose` with `model:` set to the registry refute value.
  The gate leaves a registry counter model untouched on a generic type, so the cross-family verifier survives the rewrite;
  Other exact registry lane selectors also survive; unregistered selectors are clamped to the type's band.
- Generic cheap-lane launch (`k-agent-mechanical`, `k-agent-smol` are undiscoverable at user level):
  `subagent_type: generalPurpose` with `model:` set to the registry mechanical/memory value (`auto`).
  The gate passes a registry cheap-lane model through on the generic type exactly like a counter model.
  These `auto` rows intentionally omit effort; do not add a separate reasoning-effort field.
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
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/Playwriter, report the blocked capability;
  do not automatically relaunch a completed worker. Choose required permissions before launch.
- If Cursor cannot await background subagent ids, do not loop blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Background dispatch is optional, not a role requirement.
  Use it only for independent ready root packets when the active Task schema exposes `run_in_background` and a native completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.

### Copilot CLI

- Copilot profiles carry resolver-rendered `model` frontmatter (`lanes` on workers/auditors/controller, `verifier` on `k-agent-adversarial-verifier`).
  The managed `~/.copilot/settings.json` subagent entries also include resolver-aligned `model`/`effortLevel`/`contextTier` so stale target-only model overrides cannot survive Copilot's settings merge.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent resolved lane value.
- Launch angle lanes as the `k-agent-review-worker` agent type (model-invocable, not user-invocable).
  Do not use the generic `task` type unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.
  A supported fallback passes the registry model and reasoning effort explicitly; it is not permission to change category.

### Subscription wrapper boundary

Resolve the backend matrix, not the frontend catalog, on subscription wrappers.
Claude managed `--agents` definitions carry exact adapter-local lane tags and preserve their prompt/skill preloads.
The hook requires a fresh `AGENT_BAND_CLAUDE_ROUTES` role/pair map and removes the call's model override.
Do not delegate through a missing/unavailable profile, conflicting inherited controls, resume, or fork.
The projected tools exclude `Agent`, `Task`, and `SendMessage`; this does not prove terminal-wakeup prevention by the root.

`,codex-copilot` supports fresh native leaves only with its launch-projected `AGENT_BAND_CODEX_ROUTES`, entitled model catalog, and managed profile copies.
Those copies omit native model/effort pins, retain leaf instructions, and disable `multi_agent`.
The band gate must admit the role and exact `model@lane-<effort>` pair; the adapter strips the tag and applies lane effort instead of root controls.
Do not delegate with missing, malformed, stale, or unavailable session projections; relaunch the wrapper when its launch projection is missing.
Do not use full-history `fork_context`, conflicting provider controls, or child-originated delegation.
Native child-tag transport does not certify live provider acceptance or successful refuter completion.
A backend route map or adapter-only translation test is not evidence that the frontend transports child selectors.

Child-tag transport is verified absent on `,copilot-codex`: the per-subagent `~/.copilot/settings.json` model wins over the band hook's call-level rewrite, so delegation there runs unpinned.
`,cursor-codex` and `,cursor-copilot` remain unverified.
Do not bypass a denial by dropping effort, using a raw backend model, invoking another harness, or substituting the root model.
Report the limitation. Root sessions and native harness routes remain separate capabilities.

### Codex on OpenRouter

`,codex-openrouter` requires its own fresh `AGENT_BAND_CODEX_ROUTES` and model-free managed role copies.
The catalog retains exact `@preset/effort-<level>` ids; the gate admits only projected roles and exact backend pairs.
Do not send a separate native reasoning field on this route; the admitted preset selector carries the assigned effort.
Do not delegate from an old session without that projection or use a full-history fork to bypass it.
A scripted native transport check does not establish paid-provider acceptance, cache hits, or terminal-wakeup prevention.

### Pi and OMP

- OMP managed profiles, including native-name `task`/`sonic`/`scout` shims, require `blocking: true`, no `task` tool, and no `spawns` allowlist.
  Leaf async/task/advisor/hub calls are blocked; explicit async remains a root capability, not a worker default.
  Native reviewer shortcuts are disabled in favor of managed review profiles.
  Task packets must name the profile explicitly, including every batch item.
  The runtime gate checks native discovery against the enabled user-profile path and foreground leaf controls.
  Project/plugin/bundled replacements, settings-level model overrides, worker advisors and prewalk handoffs are blocked.
  Eval admission checks every enabled profile because its agent selection is dynamic;
  ordinary root tools remain available when this blocks non-agent Eval code.
  Passing that outer guard does not admit Eval's `agent()`, `workpool()`, or `completion()` helpers.
  MUST NOT use those helpers or their synthetic bridges for managed model/worker lanes.
  Native `eval/js/tool-bridge.ts` dispatches them before ordinary tool lookup/wrapping.
  `agent()` registers background work and keep-alive execution despite `blocking: true`; `workpool()` creates persistent worker pools.
  `completion()` uses its own tier/effort resolver and starts a model request outside the profile lane.
  Use managed native task packets when delegation is allowed; ordinary Eval code remains available.
  The extension does not intercept those inner helper calls. This instruction restriction is not native enforcement.
- Pi workers use `defaultContext: fresh`, `inheritProjectContext: false`, `inheritGlobalContext: false`, `inheritSkills: false`, and `maxSubagentDepth: 0`.
  The root packet supplies applicable project/safety constraints.
  Explicit named role skills still load separately; the ambient catalog does not.
  Root dispatch requires `agentScope:"user"` and `acceptance:false`; the guard rejects project replacements, per-call model/skill overrides, composite workflows, and revival.
  Do not use forked root history for leaf packets. Select the named profile and omit per-call model/skill fields.
- OMP 18.1.14 forwards context files and skills into native child session construction and adds native Coop/Completion guidance.
  Its parser exposes no Pi-style inheritance flags. Do not invent those fields.
  The managed prompt hook keeps the role, explicit packet/plan, worktree restriction, and yield schema;
  it removes inherited SOP/catalog and private-QA/peer-wakeup guidance. Named skill autoloads remain.
  Unknown or unmanaged frames abort instead of falling back to controller instructions. Supply only task context.
  Do not claim the hook prevents physical SDK discovery, native lifecycle revival, or later third-party prompt rewrites.
  Native plan-mode and restricted SDK children omit extensions entirely, including these guards.
  Do not dispatch unattended workers on those paths.
  The public extension context has no mode getter, and ACP/plan-yolo do not consistently emit the TUI mode entries;
  transcript-only checks do not enforce this restriction. Root planning and the strong `@plan` model role remain available.
  Profile admission does not certify extension loading or prevent edits to user-profile files.
- OMP roots record finalized native task lifecycle events beside the worker transcript as `.k-leaf-terminal` markers.
  Managed leaves reject later prompts, provider requests and tools, including cold reopens of that same session file.
  Provisional yields are not terminal events. The native transcript/result and model lanes remain unchanged.
  Do not resume a completed workpool batch, remove markers to bypass the guard, or claim coverage for pre-existing unmarked workers.
  Missing session persistence or failed marker writes block the guarded operation; do not retry or use another harness to bypass it.
  Native registry retention/session construction still occurs. No-worker pipeline fixtures are not full worker lifecycle evidence.
- Pi and OMP launch subagents through named profiles; profile model controls determine the lane.
  Pi thinking is encoded as a `:<thinking>` suffix in the profile model string; OMP resolves profile role tokens through `modelRoles`.
- Resolved `lanes` and `verifier` are concrete.
  Pi review workers and fresh-eyes run `anthropic/claude-fable-5.1:high` (the Pi session's own T1 model);
  adversarial and criteria verifiers run `openrouter/openai/gpt-5.6-sol:xhigh` —
  the same model as the T2 implement row at a higher effort, but a different family than the Anthropic T1 lanes it audits, so `category_models.pi.refute` carries `verifier_status: cross_family`.
  OMP resolves review roles through its own `modelRoles`.
  One profile-independent `modelRoles` block prices default/vision/slow/plan to `anthropic/claude-fable-5.1:high`, `task` (the T2 implement lane) to `anthropic/claude-opus-5:high`, `smol` to `anthropic/claude-sonnet-5:high` (memory rides `@smol`), `tiny` and `commit` to `anthropic/claude-sonnet-5:medium`, and `advisor` to `openai-codex/gpt-6-astra:high` on both work and personal.
  Every `category_models.omp.*` row carries effort `high`; the `@role` token itself carries the real tier.
  Adversarial and criteria verifiers follow `@advisor`, a different family than the Anthropic lanes, so `category_models.omp.refute` marks `verifier_status: cross_family`.
  Other repo-owned Pi/OMP profiles resolve their model from the review resolver or category registry (`agent_bindings` → `agent_categories` → `category_models`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
