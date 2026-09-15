# Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-deep-review` uses those native mechanisms plus the role-specific contracts in `~/.agents/skills/k-review/references/`.

Read this file only for capability caveats that affect orchestration.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.

### Model policy

- Model selection is **registry-driven and deterministic**: every repo-owned review profile's `model` frontmatter is rendered through `review-agent-model.partial`, which derives from `agent_bindings`, `agent_categories`, and `category_models` in `home/.chezmoidata/ai_models/tiering.yaml`.
  Updating a derivable review model is a one-line category row edit plus `chezmoi apply`;
  model ids never live hand-written in profile files.
- Resolver slots per harness: `lanes` (the review packet, auditors, controller, named fresh-eyes profiles, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — prefer a **different model family than `lanes`** at equal capability per SOP §3.7; never trade capability for family diversity — a strong same-family verifier beats a weaker cross-family one.
  Same-family runs keep refutation framing and report the reduced independence, never hidden).
  Named profiles carry their resolved model/effort controls; do not override those fields merely to repeat the profile.
  A supported generic fallback receives the resolved category controls through that harness's actual fields.
  Codex/Copilot use model plus reasoning effort; Cursor uses its model selector. Do not invent fields on another harness.
- Every resolved review-lane value is a concrete category id (Claude Code included since 2026-09-13; its profiles no longer render `inherit`).
  Named profile pins satisfy that requirement without per-call overrides. Generic fallbacks must preserve the same category.
  Antigravity has no profile surface; its abstract tier is stated in the Antigravity section below.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

### Final judgment selection

Choose the applicable strong review/refute category and its resolved model/effort before launching a substantial final packet.
Use a reachable named profile, or a native generic type with the same explicit registry category model where supported.
Do not silently fall back to a weaker or more expensive model.
A missing capability is a reported limitation, not authority to bypass the category.
Fresh-eyes, criteria, and hygiene profiles are optional framings; adversarial is required for deep or high-risk work.
No child owns orchestration, verification of another reviewer, or a convergence loop.

### Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Review profiles pin the `category_models.claude_code` id (`review` / `refute` rows) so profile frontmatter and the bands projection name the same model; a session launched on another model does not silently retarget them.
- Built-in shadows: repo-owned same-name profiles override high-risk embedded builtins (`Explore`, `Plan`, `general-purpose`, `claude-code-guide`, `claude`) so normal Task launches use our profile frontmatter instead of embedded defaults.
- Wrapper guard: `,claude-openrouter` uses the Pi backend matrix through session-projected native `--agents` definitions.
  Each managed profile carries its exact preset selector, including refute's distinct effort, while its prompt and skill preloads remain unchanged.
  The hook requires the fresh `AGENT_BAND_CLAUDE_ROUTES` role/pair map and removes call-level model overrides so the profile wins.
  Do not delegate with missing or stale profiles, conflicting inherited controls, a resume request, or a full-history fork.
  Do not substitute implementation effort for refutation. The caller's `--agents` cannot replace the managed projection.
- Adversarial verifier, criteria verifier, and fresh-eyes are repo-owned named profiles (`k-agent-adversarial-verifier`, `k-agent-criteria-verifier`, `k-agent-fresh-eyes`) whose resolver-rendered frontmatter pins the `claude_code` review/refute category ids; launch them by name — a named final packet when that framing is selected.
  The model surface is still one family, so keep reporting `families=same (degraded)`.

### Codex

Native Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Subscription wrappers use the backend matrix and the subscription boundary below instead of these native model pins.
Launch the review packet as a `k-agent-review-worker` agent; the verifier as the `k-agent-adversarial-verifier` agent.
Registry: `lanes` and `verifier` are concrete profile `model` + `model_reasoning_effort` pairs rendered from `category_models.codex`;
read the current ids from `~/.config/ai/agent-bands.v1.json` (`harnesses.codex.agents`), not from this file.
Review and refute are both OpenAI models but may differ; one model can serve several categories at different efforts.
Every Codex role also pins `service_tier = "default"`. Named Codex profiles retain their declared model/effort.
A native generic `worker` carrying another category must pass both resolved `model` and `reasoning_effort`.
Do not select a lane from model membership alone when one model serves multiple category efforts.

### Antigravity CLI

Run `/k-deep-review` in the main Antigravity session. Dynamic subagents cannot invoke further subagents.
Antigravity has no repo-owned profile-file surface; define each needed role with `define_subagent`, point its system prompt at the matching shared role contract, then launch it through `invoke_subagent`.
Every dynamically defined repo-owned role MUST use its `k-agent-<role>` identifier.
The `invoke_subagent` model field accepts only `inherit`, `flash_lite`, `flash`, or `pro`; every `category_models.antigravity` row is Gemini Flash, so the tier to pass is `flash`.
Use `flash`: review, audit, refute, `k-agent-mechanical` procedures, `k-agent-smol` memory.
Do NOT launch any lane on `inherit`; do not use `pro` unless the registry row changes to a Pro model.
The model surface is Gemini-only, so report `families=same (degraded)` for adversarial verification.

### Cursor

- Transcript exports label the delegation tool `Subagent` (2026-09-04 export), while the cursor-agent 2026.09.02 bundle still names the call type `taskToolCall`; the `tool_name` the preToolUse hook receives is unverified.
  The band gate therefore matches both `Task` and `Subagent`; a launch that passes a non-registry `model` is rewritten to the subagent type's band either way.
- Generic adversarial-verifier launch: `subagent_type: generalPurpose` with `model:` set to the registry refute value.
  The gate leaves a registry counter model untouched on a generic type, so the cross-family verifier survives the rewrite;
  Other exact registry lane selectors also survive; unregistered selectors are clamped to the type's band.
- `k-agent-mechanical` (procedures) and `k-agent-smol` (memory) are not user-discoverable.
  `subagent_type: generalPurpose`, `model:` = mechanical/memory base id from `harnesses.cursor.agents` in `agent-bands.v1.json`.
  The gate preserves registered cheap/counter models.
  Effort comes from saved user config, not Task ids; do not add a reasoning-effort field.
  The gate cannot distinguish shared cheap/implement ids; retain the profile/packet category.
- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads **project-level** `.cursor/agents` profile files only;
  user-level `~/.cursor/agents` is never scanned (probed 2026-08-30, cursor-agent 2026.08.28-a7f9513), so home-deployed profiles are unreachable.
  Where a workspace carries `k-agent-review-worker`/`k-agent-adversarial-verifier` profiles, launch the review and refute packets through them;
  both carry resolver-rendered `model` frontmatter.
- Resolved `lanes` and `verifier` are Task base ids from `category_models.cursor` (`review` / `refute`); read them from `harnesses.cursor.agents` in `agent-bands.v1.json`.
  `category_models.cursor.refute` carries `verifier_status: cross_family`, so the adversarial verifier runs as a cross-family lane.
  An omitted Cursor subagent model falls to Cursor's own default (`auto` router; observed `composer-2.5-fast` in 2026-08 probes, unverified since).
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
  Copilot CLI 1.0.83 requires `enabledFeatureFlags.EXTENSIONS=true` before it discovers the managed SDK extension that supplies context, read, band, and worklog hooks.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent resolved lane value.
- Launch the review packet as the `k-agent-review-worker` agent type (model-invocable, not user-invocable).
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

On `,copilot-codex`, Copilot 1.0.83 skipped its band gate without `enabledFeatureFlags.EXTENSIONS`.
Enabling only that flag made the managed SDK extension deny subscription tasks before a child request.
This proves denial, not selector impossibility, successful governed delegation, or full leaf lifecycle.
Cursor `2026.09.08-6caf4ff` local-provider Task configuration (`nhe()`) hardcodes `enableExecuteHookExec:false`.
Authenticated scripted-provider probes under both subscription environments returned child results without user/workspace gate calls.
Both routes bypass configured denial; exact role/model/effort routing and full lifecycle remain uncertified.
The prior `,cursor-codex` live root shell smoke does not certify the live Copilot backend for `,cursor-copilot`.
MUST NOT assign unattended child work to `,copilot-codex`, `,cursor-codex`, or `,cursor-copilot` while those route-specific capabilities remain uncertified. Do not bypass a denial by dropping effort, using a raw backend model, invoking another harness, or substituting the root model.
Report the limitation. Root sessions and native harness routes remain separate capabilities.

### Codex on OpenRouter

`,codex-openrouter` requires its own fresh `AGENT_BAND_CODEX_ROUTES` and model-free managed role copies.
The catalog retains exact `@preset/effort-<level>` ids; the gate admits only projected roles and exact backend pairs.
Do not send a separate native reasoning field on this route; the admitted preset selector carries the assigned effort.
Do not delegate from an old session without that projection or use a full-history fork to bypass it.
A scripted native transport check does not establish paid-provider acceptance, cache hits, or terminal-wakeup prevention.

### Pi and OMP index

Pi and OMP native capability boundaries live in `~/.agents/skills/k-review/references/runtime-harnesses-pi-omp.md` as a packet pointer only; the root does not open it (Contract above).
Pass the applicable section in the packet; a launch failure is reported with its exact error rather than diagnosed by reading harness docs.
