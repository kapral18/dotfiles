# Agent Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/k-agent-review` uses those native mechanisms plus the role-specific contracts in `references/`.

Read this file only for capability caveats that affect orchestration.

## Model policy

- Model selection is **registry-driven and deterministic**: every profile's `model` frontmatter is rendered from the single `agent_review_models` block in the chezmoi model registry (`home/.chezmoidata/ai_models.yaml`).
  Updating a model is a one-line registry edit plus `chezmoi apply`; skills and controllers never steer models at runtime, and model ids never live hand-written in profile files.
- Registry values per harness: `lanes` (angle lanes, auditors, controller, and generic fresh-eyes launches) and `verifier` (the adversarial verifier — a **different model family than `lanes`**, paired by human review in the registry, not inferred at launch).
  Generic fresh-eyes launches must pass the registry lane model as the profile-equivalent model;
  never let the runtime pick an implicit default when the registry has a concrete lane value.
- Empty registry value = the profile omits the field and the harness config default applies; `inherit` = harness-native parent inheritance.
  Single-family harnesses leave `verifier` empty/`inherit` and run the verifier degraded on the lane model —
  reported as `families=same (degraded)`, never silent.
- A model unavailable in the active runtime is a fail-visible launch error to surface; fix the registry, never substitute at launch.

## Claude Code

Claude subagent model overrides are limited to the installed SDK schema (`sonnet`, `opus`, `haiku`, `fable`) — one family.

- Registry: `lanes: inherit` — Claude sessions run a deliberately chosen model, and profiles use `model: inherit`.
- Adversarial verifier: single-family surface, always `families=same (degraded)`;
  launch a general-purpose `Task` carrying `adversarial-verifier.md`.

## Codex

Codex's model surface is OpenAI-only, so the adversarial verifier is `families=same (degraded)` here.
Launch angle lanes as `review-worker` agents; the verifier as the `adversarial-verifier` agent.
Registry: both values empty — profiles omit `model` and the configured Codex default applies.
No per-task model mechanism is verified for `spawn_agent`; report the model used when the harness exposes it.

## Gemini CLI

Gemini subagents cannot call other subagents, so run `/k-agent-review` in the main Gemini session.
Do not run the controller itself as a Gemini subagent.
The model surface is Gemini-only: the adversarial verifier is `families=same (degraded)`; launch it as the `adversarial-verifier` profile.
Registry: both values empty — profiles omit `model` and the configured Gemini default applies. No per-task model mechanism is verified.

## Cursor

- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads `.cursor/agents` profile files.
  Launch angle lanes through the `review-worker` profile and the verifier through the `adversarial-verifier` profile;
  both carry registry-rendered `model` frontmatter.
- The registry pins a concrete Cursor lane model deliberately: verified (Cursor subagent docs + cursor-agent 2026.06.04), omitted `model` frontmatter defaults to inherit and the live CLI default is `composer-2.5-fast`, so inheritance would silently run the fan-out on Composer from a default-model session.
- When the active Task schema exposes only generic subagent types, pass the same registry values as explicit `model` arguments —
  the registry stays the single source either way. Generic fresh-eyes launches pass the registry lane model.
- Cursor's `readonly` flag is a hard tool restriction, not the `/k-agent-review` behavior-level read-only boundary.
  Cursor source shows `readonly: true` blocks shell, write, delete, and MCP operations.
  Keep Cursor profile frontmatter and Task launches at `readonly: false`; the worker contracts enforce no-mutation behavior.
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/SCSI/Playwriter, discard that launch result and rerun with `readonly: false` before accepting `verification_needed`.
- If Cursor cannot await background subagent ids, do not loop blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Keep reviewer, PR-necessity, live-UI, and findings-audit workers as real Cursor background subagents;
  use Cursor Task `run_in_background=true` when the active Task schema exposes it. Wait through a Cursor-native subagent completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.

## Copilot CLI

- Copilot profiles carry registry-rendered `model` frontmatter (`lanes` on workers/auditors/controller, `verifier` on `adversarial-verifier`); the `~/.copilot/settings.json` subagent entries own only `effortLevel`/`contextTier`.
  Per-task model overrides are runtime-verified but reserved for fail-visible recovery, not steering, except generic fresh-eyes where the explicit model is the profile-equivalent registry lane value.
- Launch angle lanes as the `review-worker` agent type (model-invocable, not user-invocable).
  Do not use `general-purpose` unless a named launch is proven unavailable in the active Copilot runtime, and state that fallback reason.

## Pi

- Pi launches subagents only through named profiles; per-task `model` is honored over the worker default (previously runtime-verified).
- Registry: `lanes` empty — `reviewer` tasks carry no `model` field and use the configured default provider/model.
- Adversarial verifier: the `adversarial-verifier` profile with the registry verifier model passed per task (Pi resolves models per task, not per profile; the controller template renders the registry value).
