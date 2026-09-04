# Live Artifact Overlay

The live overlay mode injects the same feedback idea into an already-open real page through Playwriter. It does not iframe the target app.
It adds a namespaced Shadow DOM dock, intercepts page clicks while capture is active, has a pause/resume button for normal app use, and can be removed without changing app source.
Live feedback captures minimal DOM context: URL, title, selector, role/label, compact text or selection, bounding rect, ancestor hints, and Cmd-click/Ctrl-click multi-target arrays.

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
