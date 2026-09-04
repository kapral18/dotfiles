# Generated Artifacts

The generated-artifact chrome starts with only a fixed Feedback button at the top right.
Feedback mode is hidden and capture is disabled by default, so artifact controls remain interactive without selection highlights or interception.
Opening Feedback reveals the dock and enables a cursor-following hover highlight;
users then click or select content to pin a stronger highlight.
Cmd-click toggles additional targets into a multi-selection (teal highlight) so one prompt can address several pinned targets at once;
a plain click returns to single-anchor mode, and multi-target items reach `poll` with a `targets` array alongside the first target's fields.
Text selections promote the highlight to the surrounding card, section, list item, or table row.
Repeated Alt-clicks expand the pinned highlight upward through ancestor elements, up to the top `html` element.
Closing Feedback hides the chrome and highlights again while preserving queued feedback.
The open dock expands upward into an anchor card and attaches that context when users add feedback to the tray.

Author generated artifacts with semantic feedback metadata whenever the artifact contains distinct things a user may point at.
Tag meaningful regions with `data-artifact-id`, plus optional `data-artifact-kind`, `data-artifact-label`, `data-artifact-title`, `data-artifact-summary`, and `data-artifact-parent`.
Embed a compact manifest in `<script type="application/json" id="agent-artifact-manifest">` with `artifactId`, `entities`, and `relations` or `edges`.
Use IDs for meaning and relationships for context; CSS selectors remain a fallback locator.
When a user clicks or Cmd-clicks tagged content, `poll` returns `entity_id`, `entity_kind`, `entity_label`, `entity`, `entity_ancestors`, and `relations` alongside the selector/text fields.
Choose IDs that are stable inside the artifact and readable by an agent, such as `entity.section.auth-options.option.jwt` or `chart.latency.series.p95`.

`write` and `open` inject a low-specificity ambient theme by default.
The theme is inferred from broad local worktree signals such as dotfiles, docs, web app, or codebase markers.
Use `,artifact theme` or `,artifact theme --json` before authoring when you need to understand the current style vocabulary.

## Workflow

1. Run `,artifact theme` to see the detected ambient style.
2. Generate original standalone HTML in `/tmp` or stream it directly to `,artifact write <name> --open`.
   Add semantic metadata to selectable sections, cards, table rows, graph nodes, chart series, options, risks, claims, or other entities that feedback may target.
3. Tell the user the browser artifact is open and that its Feedback button enables annotation mode.
   Keep the agent running `,artifact poll <name>` when waiting for feedback.
4. When `poll` returns feedback, read the returned `batches`/`prompts` and apply the whole batch.
   Update the cached artifact with `,artifact write <name> --open`, then poll again if more feedback is expected.
5. Run `,artifact poll-stop <name>` when you are no longer waiting for that artifact's feedback.
   Run `,artifact stop` when the local review session is no longer needed.
