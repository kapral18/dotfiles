# Agent Review Runtime Harness Caveats

This file is not a subagent registry.

- The active harness owns discovery and invocation for its configured agents, tasks, or native isolation tools.
- `/agent-review` uses those native mechanisms plus `runtime-contracts.md`.

Read this file only for capability caveats that affect orchestration.

## Claude Code

Claude model overrides are limited by the installed SDK schema:

- `sonnet`
- `opus`
- `haiku`
- `fable`

Do not invent GPT or exact Opus model IDs in Claude frontmatter. Preserve reviewer diversity with supported model overrides and distinct review angles.

## Codex

Codex's current OpenAI model surface does not provide a Claude Opus lane here, so model diversity is best-effort. Keep the two workers distinct by angle and evidence strategy.

## Gemini CLI

Gemini subagents cannot call other subagents, so run `/agent-review` in the main Gemini session. Do not run the controller itself as a Gemini subagent.

## Amp

Amp has no verified custom profile directory in the local interface. Use generic `Task` prompts with `runtime-contracts.md` instead of inventing profile files.
