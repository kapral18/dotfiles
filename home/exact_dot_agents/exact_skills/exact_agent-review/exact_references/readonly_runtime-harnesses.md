# Agent Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/agent-review` uses those native mechanisms plus the role-specific contracts in `references/`.

Read this file only for capability caveats that affect orchestration.

## Claude Code

Claude model overrides are limited by the installed SDK schema:

- `sonnet`
- `opus`
- `haiku`
- `fable`

Do not invent GPT or exact Opus model IDs in Claude frontmatter.
Preserve reviewer diversity with supported model overrides and distinct review angles.

## Codex

Codex's current OpenAI model surface does not provide a Claude Opus lane here, so model diversity is best-effort.
Keep the two workers distinct by angle and evidence strategy.

## Gemini CLI

Gemini subagents cannot call other subagents, so run `/agent-review` in the main Gemini session.
Do not run the controller itself as a Gemini subagent.

## Cursor

- Cursor source supports custom subagent types (`SubagentType.custom.name`) and loads `.cursor/agents` profile files.
  Prefer the named agent-review profiles when the active model-facing Task schema exposes those names or a custom subagent-type field.
  If the active Task schema exposes only generic subagent types, use the listed generic worker type with the exact lane model.
  Record `invocation=fallback`.
- Cursor's `readonly` flag is a hard tool restriction, not the `/agent-review` behavior-level read-only boundary.
  Cursor source shows `readonly: true` blocks shell, write, delete, and MCP operations.
  Keep Cursor profile frontmatter and Task launches at `readonly: false`; the worker contracts enforce no-mutation behavior.
- If a Cursor worker reports Ask/read-only mode blocked shell/git/`gh`/SCSI/Playwriter, discard that launch result and rerun with `readonly: false` before accepting `verification_needed`.
- If Cursor cannot await background subagent ids, do not loop blind sleeps.
  Cursor source has a subagent await protocol, but the shell Await/AwaitShell path is for shell tasks and may reject subagent ids.
  Keep reviewer, PR-necessity, live-UI, and findings-audit workers as real Cursor background subagents;
  use Cursor Task `run_in_background=true` when the active Task schema exposes it. Wait through a Cursor-native subagent completion signal.
  If no native completion signal is available, end the controller turn and wait for the completion notification, or do one transcript completion check; never loop fixed-interval sleeps.
- If a required model id is unavailable, fail closed for the affected lane and surface the unavailable id.
  Do not substitute a same-family or faster variant.
  The worker selection line must show `model_required`, `model_used`, and `model_status=exact`;
  a different `model_used` is an invalid launch, not a fallback.
