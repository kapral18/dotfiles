---
name: k-artifact
description: "Use for cache-only HTML artifacts, visual reports/diagrams, or live-page overlays without worktree writes."
---

# Agent Artifact

Use `,artifact` to create a local browser review surface without polluting the current worktree.

Artifacts and runtime state live under `~/.cache/agent-artifacts` (or `$XDG_CACHE_HOME/agent-artifacts`).
The current cwd/git root and tmux session are identity metadata only; keep the worktree clean —
artifacts live in the cache dir, never in a repo `.agent-artifacts/`, and `.gitignore` stays untouched.

## Generated artifacts

Before authoring, writing, opening, or updating a generated artifact, MUST load and follow `~/.agents/skills/k-artifact/references/generated-artifacts.md`.
It owns generated feedback behavior, semantic metadata, ambient theming, and the generated-artifact workflow.

## Live overlays

Before injecting or using a live-page overlay, MUST load and follow `~/.agents/skills/k-artifact/references/live-overlay.md`.
It owns Playwriter attachment, injection, live feedback, CSP fallback, and removal.

## Common behavior

Feedback is sent as batches, so treat `poll` output as a grouped set of requested changes.
`poll` also returns an `archive` path for the delivered JSONL so feedback can be recovered if the agent crashes after receiving it.
Design artifact contents with an original look that fits the task, rather than copying the visual language of Lavish or any other third-party artifact tool.

Do not use:

- routine short answers.
- human-visible publication to external systems.
- storing durable project documentation. If the artifact becomes real documentation, ask before exporting it into the repo.

## Commands

```bash
,artifact theme
,artifact write plan --open < /tmp/plan.html
,artifact open plan
,artifact poll plan
,artifact poll plan --timeout 30
,artifact pollers
,artifact poll-stop plan
,artifact live start live-review
,artifact live script live-review
,artifact path plan
,artifact list
,artifact clean
```

## Poller Lifecycle

Pollers are tracked per artifact session.
A session is scoped by tmux session identity plus resolved worktree root, so parallel sessions/worktrees have independent poller registries.

- Use `,artifact pollers` before cleanup if you need to see active pollers for the current session.
- Use `,artifact poll-stop <name>` when the feedback loop for one artifact is done.
- Use `,artifact stop` only when the whole current artifact session is done; it stops the current session's server and pollers.
- Do not kill pollers from other worktrees or tmux sessions.
- Prefer finite `--timeout` values when waiting opportunistically instead of actively expecting user feedback.

## Rules

- Cache-only: never write generated artifact files into the worktree.
- Use standalone HTML. If local assets are needed, put them under the cached artifact directory printed by `,artifact path <name>`.
- Make the artifact interactive when it helps: filters, toggles, revealable detail, checklists, comparison controls, or highlighted regions are preferred over static walls of text.
- Use live overlay for already-running apps instead of trying to iframe protected pages.
- In live overlay mode, verify the page is local/dev before collecting feedback.
  Do not inject into production, shared cloud, or non-user-approved sites.
- Prefer the built-in ambient primitives for dense artifacts: `.density-compact`, `.card`, `.panel`, `.callout`, `.checklist`, `.pill`, `.metric`, and normal tables.
- Make feedback prompts specific enough to act on without another clarification round.
- Keep the artifact focused: one decision, plan, report, or review surface per artifact.
- Do not leave background pollers running after the task is finalized.
- If the user asks to keep or publish the artifact, ask where it should be exported before writing into the repo.
