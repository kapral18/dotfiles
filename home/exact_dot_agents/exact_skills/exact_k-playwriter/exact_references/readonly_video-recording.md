# Video recording

## Video Recording: Skip the Extension Path

Use this section only after the capture plan has classified an item as video.
A static state that needs a setup action to reach it stays screenshot-classified when the setup action is not the fixed behavior.

`recording.start/stop` (extension `chrome.tabCapture`) can silently produce empty files:
`start` succeeds, `stop` returns a plausible `duration`, but `size` is ~749 B (mp4 header only) or 0.
Verified on both Dia and real Chrome with the bundled extension (playwriter 0.4.0 / extension 0.0.97);
codec support, activeTab grant, tab focus, and window visibility were all confirmed and did not help.

Rules:

- After every `recording.stop`, check `result.size` before doing anything else.
  Under ~50 KB for a multi-second clip means no frames were captured.
- On an empty file, do not loop on icon clicks, grants, reloads, or another browser — the pipeline is broken;
  switch immediately to Playwright's built-in recorder below.
- The activeTab grant from an icon click survives in-page keyboard/mouse actions but dies on any navigation or reload;
  each re-grant needs a human click. This burns user round-trips — another reason to prefer the built-in recorder for video.

### Reliable path: plain Playwright `recordVideo`

Works headless, needs no extension or user clicks, fully reproducible.
Pass `NODE_PATH` on the same `node` invocation (or `export` it in the shell that will run every recorder) so child processes resolve `playwright-core`:

```bash
NODE_PATH="$PWD/node_modules" node /tmp/record.js   # reuse the repo's playwright-core
```

```js
const { chromium } = require("playwright-core");
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: "/tmp/raw", size: { width: 1280, height: 720 } },
});
const page = await context.newPage();
// Resolve controls from the live a11y/DOM before the scenario; leave proof-visible
// toasts/banners/dialogs up through the clip when they are the delta being proven.
// ...login + scenario...
const video = page.video();
await context.close(); // finalizes the file
const path = await video.path(); // .webm
```

`playwriter` CLI has no `--record` flag — use `Browser.newContext({ recordVideo })` as above (verified playwriter 0.4.0).

Post-process: `ffmpeg -i in.webm -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4`, then trim the login/load lead-in with `-ss <sec>`.
The video starts at page creation, so capture the trim point instead of guessing:
`const t0 = Date.now()` after `newPage()`, then log `(Date.now() - t0) / 1000` when the scenario starts and use it (minus ~0.5s) as `-ss`.
Published clips start at the proving interaction; leave login/welcome/idle load out of the uploaded file.
Verify content by extracting frames (`ffmpeg -vf fps=1 f-%02d.png`) and reading them —
a green status probe is not proof the video shows the behavior.
