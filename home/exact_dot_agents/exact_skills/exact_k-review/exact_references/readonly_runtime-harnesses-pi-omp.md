# Review Runtime Harness Caveats — Pi and OMP

Companion to `~/.agents/skills/k-review/references/runtime-harnesses.md`; read it only for Pi/OMP capability caveats that affect orchestration.

## Root moves

Only the active root/main session follows this section; a delegated leaf skips it and returns findings to its parent.

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
- OMP task dispatch mechanics. When delegation is permitted, use `task` with explicit managed profile names and ready stage-sized packets; task packets must name the profile explicitly, including every batch item.
  Pass large packets with `local://`; inspect returned artifacts through `agent://`, `history://`, and `artifact://`.
  Use `hub` only for authorized named-process lifecycle operations. Do not use peer messages to wake or resume workers.
  Do not dispatch unattended workers in native plan mode or restricted SDK sessions; those children omit the managed extensions.
  Keep the registry's category model/effort and the SOP's single final Verify stage. Honor no-delegation requests inline.
- Pi and OMP launch subagents through named profiles; profile model controls determine the lane.
  Pi profiles render `model:` from `category_models.pi` and a separate `thinking:` line from the row's `effort` (`agent-thinking.partial`); OMP resolves profile role tokens through `modelRoles`.
- Resolved `lanes` and `verifier` are concrete.
  Pi review workers, fresh-eyes, and the adversarial/criteria verifiers all resolve from `category_models.pi.review` / `category_models.pi.refute` in `home/.chezmoidata/ai_models/tiering.yaml`;
  read the live ids from `subagent({action:"list", capabilities:true})`, not from this file.
  Pi review rides the Anthropic session route and refute a Meta counter, so `category_models.pi.refute` declares `verifier_status: cross_family`; report the registry status, do not substitute a model.
  OMP resolves review roles through its own `modelRoles`.
  One profile-independent `modelRoles` block in `home/dot_omp/private_agent/readonly_config.yml.tmpl` prices every role (`default` is generated from `session_models.omp`); read the pins there, not here.
  `category_models.omp.*` row efforts mirror `category_models.codex` (implement `medium`, the rest `high`); the `@role` token itself carries the real tier.
  Adversarial and criteria verifiers follow `@advisor`, the same model family as the primaries, so `category_models.omp.refute` marks `verifier_status: degraded`; report the registry status, do not substitute a model.
  Other repo-owned Pi/OMP profiles resolve their model from the review resolver or category registry (`agent_bindings` → `agent_categories` → `category_models`) so they do not fall through to `defaultProvider`/`defaultModel` unless a future profile deliberately omits `model` and documents why.
