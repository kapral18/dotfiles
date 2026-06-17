# Agent Review Runtime Harnesses

Use the strongest native isolation mechanism the current harness actually exposes.

## Cursor and Copilot

Use the named review lanes:

- `review-gpt-5-5-extra-high`
- `review-opus-4-8-xhigh-non-thinking`
- `findings-auditor`
- `live-ui-review` only when manually requested

## Claude Code

Use the `agent-review` current-session agent when available. It loads this skill, then uses Claude's `Task` tool to invoke:

- `reviewer` twice, with distinct angles and model overrides when available (`opus` and `sonnet`)
- `findings-auditor` over the combined candidate findings
- `live-ui-review` only when manually requested

Claude model overrides are limited by the installed SDK schema to `sonnet`, `opus`, `haiku`, and `fable`; do not invent GPT/Opus-4.8 model IDs in Claude frontmatter.

## Codex

Use Codex multi-agent `spawn_agent`/`wait` when available. Prefer configured Codex agent roles:

- `review-worker` for each investigation lane; launch it twice with distinct angles
- `findings-auditor` over the combined candidate findings
- `live-ui-review` only when manually requested

Codex role files live in `$CODEX_HOME/agents/*.toml`. Codex's current OpenAI model surface does not provide a Claude Opus lane here, so model diversity is best-effort; keep the two workers distinct by angle and evidence strategy.

## Gemini CLI

Run `/agent-review` in the main Gemini session. Gemini subagents cannot call other subagents, so do not run the controller itself as a Gemini subagent. The main session should call:

- `review-gemini-pro`
- `review-gemini-flash`
- `findings-auditor`
- `live-ui-review` only when manually requested

Gemini custom subagents live in `~/.gemini/agents/*.md`.

## Amp

Amp exposes generic subagents through the `Task` tool, not named profile files. Use `Task` twice with the `Reviewer worker` section from `runtime-contracts.md`, one assigned angle per task, then use another `Task` with the `Findings auditor` section. Use a direct main-session `live-ui-review` prompt only when manually requested.
