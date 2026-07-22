---
name: k-artifact
description: "Use when creating cache-only HTML artifacts, visual review/report/diagram surfaces, or already-open live-page feedback overlays without worktree writes."
---

# Agent Artifact

Use `,artifact` to create a local browser review surface without polluting the current worktree.

Artifacts and runtime state live under `~/.cache/agent-artifacts` (or `$XDG_CACHE_HOME/agent-artifacts`).
The current cwd/git root and tmux session are identity metadata only; do not create `.agent-artifacts/` in the repo and do not edit `.gitignore`.

The generated-artifact chrome starts with only a fixed Feedback button at the top right.
Feedback mode is hidden and capture is disabled by default, so artifact controls remain interactive without selection highlights or interception.
Opening Feedback reveals the dock and enables a cursor-following hover highlight;
users then click or select content to pin a stronger highlight.
Text selections promote the highlight to the surrounding card, section, list item, or table row.
Repeated Alt-clicks expand the pinned highlight upward through ancestor elements, up to the top `html` element.
Closing Feedback hides the chrome and highlights again while preserving queued feedback.
The open dock expands upward into an anchor card and attaches that context when users add feedback to the tray.

The live overlay mode injects the same feedback idea into an already-open real page through Playwriter. It does not iframe the target app.
It adds a namespaced Shadow DOM dock, intercepts page clicks while capture is active, has a pause/resume button for normal app use, and can be removed without changing app source.
Live feedback captures minimal DOM context: URL, title, selector, role/label, compact text or selection, bounding rect, and ancestor hints.

Feedback is sent as batches, so treat `poll` output as a grouped set of requested changes.
`poll` also returns an `archive` path for the delivered JSONL so feedback can be recovered if the agent crashes after receiving it.
Do not copy the visual language of Lavish or any other third-party artifact tool.
Design artifact contents with an original look that fits the task.

`write` and `open` inject a low-specificity ambient theme by default.
The theme is inferred from broad local worktree signals such as dotfiles, docs, web app, or codebase markers.
Use `,artifact theme` or `,artifact theme --json` before authoring when you need to understand the current style vocabulary.

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

## Workflow

1. Run `,artifact theme` to see the detected ambient style.
2. Generate original standalone HTML in `/tmp` or stream it directly to `,artifact write <name> --open`.
3. Tell the user the browser artifact is open and that its Feedback button enables annotation mode.
   Keep the agent running `,artifact poll <name>` when waiting for feedback.
4. When `poll` returns feedback, read the returned `batches`/`prompts` and apply the whole batch.
   Update the cached artifact with `,artifact write <name> --open`, then poll again if more feedback is expected.
5. Run `,artifact poll-stop <name>` when you are no longer waiting for that artifact's feedback.
   Run `,artifact stop` when the local review session is no longer needed.

## Live Overlay Workflow

1. Load and follow the Playwriter skill first; live overlay injection depends on a real browser page.
2. Navigate or attach to the target page with Playwriter and verify it is the intended local/dev target.
3. Run `,artifact live script <name>` and inject the returned JavaScript into the Playwriter page with `page.evaluate`.
4. Tell the user the overlay is armed.
   Capture mode intercepts page clicks; use the overlay's Pause button when normal page interaction is needed.
5. Keep `,artifact poll <name>` running. Apply returned feedback batches as usual, using the live context fields when they are present.
6. If a strict page CSP blocks posting to the local artifact server, retrieve retained batches with `window.__agentArtifactLiveOverlay.drain()` through Playwriter.
   Report the blocker/fallback.
7. Remove the overlay with its Remove button, or call `window.__agentArtifactLiveOverlay.destroy()` from Playwriter.

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
