---
name: k-playwriter
description: "Use for real browser: browsing, UI checks, screenshots, automation, verification, visual QA."
tool_version: playwriter 0.5.0
---

# Playwriter

Use Playwriter for real browser work.
Fire without waiting for the user to name `playwriter` explicitly whenever the task needs a real browser.

## Documentation contract

Before browser work, run the installed-document reader with `core` plus every already-known operation profile and read its complete output.
For recorder work known at entry, request `recorder` directly: it emits the full document including core.
With no operation profile yet selected:

```bash
python3 ~/.agents/skills/k-playwriter/scripts/read_docs.py core
```

The reader runs `playwriter skill` and selects complete source sections only for the audited installed version and document hash.
`core` contains the common safety, session/page ownership, observation/logging, selectors, navigation, and inspection rules.
Before an operation below, read every applicable profile in full; multiple profiles can share one command. **Do NOT skip this step.**
**Read the ENTIRE selected or fallback output.** Do NOT pipe through `head`, `tail`, or any truncation command.
Do not replace required source sections with remembered examples. After compaction or lost guidance, reload `core` and the active profiles.

```bash
python3 ~/.agents/skills/k-playwriter/scripts/read_docs.py screenshots evaluate
python3 ~/.agents/skills/k-playwriter/scripts/read_docs.py --list
```

| Before using                                                              | Required profile(s)                                                         |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Remote tunnel, direct CDP, headless, or cloud connection                  | `remote`, `direct`, `headless`, or `cloud`, as applicable                   |
| User-action recorder / skill generation                                   | `recorder` (always emits the entire upstream document)                      |
| RTMP streaming or Playwriter-internal failure diagnostics                 | `stream` or `debug`                                                         |
| Clean HTML or article extraction                                          | `html` or `markdown`                                                        |
| Locator conversion, React source/info, or pinned elements                 | `locator`, `react`, or `pinned`                                             |
| CSS inspection, debugger, or live script/CSS editor                       | `styles`, `debugger`, or `editor`; follow their required API-document loads |
| Screenshots, accessibility labels, image resizing, or region captures     | `screenshots`                                                               |
| Video, ghost-cursor customization, or demo postprocessing                 | `video` plus the local recording reference below                            |
| `page.evaluate`, loading file content, or network interception            | `evaluate`, `files`, or `network`                                           |
| Low-level mouse/keyboard, drawing/dragging, scrolling, or viewport resize | `input`                                                                     |
| Ghost Browser identities, proxies, or sessions                            | `ghost`                                                                     |

Operation profiles omit `core`; they require the core contract already loaded for this invocation.
If the installed version/hash is unknown, the reader emits the full document:
read all of it and keep full-document loading until its new content is audited.
If the reader is missing/fails or the needed operation has no mapped profile, run `playwriter skill` and read the entire output before proceeding.

## Conflicting upstream recipes

Recipes never override explicit upstream rules or caller scope limits.
Keep references to registered network handlers and remove only owned handlers with `page.off(event, handler)`;
never copy blanket `removeAllListeners` cleanup.
Use snapshots and grounded locators for DOM inspection; read media attributes through locators or `evaluateAll`.
The upstream late DOM-investigation exception still requires correct interaction patterns to produce no response after 2–3 attempts.
Verified domain overlays own their explicit, narrowly scoped interaction exceptions;
they grant no general force-click or DOM-inspection permission.

## Minimal Example (after reading required docs)

Replace `<session-id>` with the ID returned by `session new`.

```bash
playwriter session new
playwriter -s '<session-id>' -e 'state.page = await context.newPage(); await state.page.goto("https://example.com", { waitUntil: "domcontentloaded" }); console.log(state.page.url()); console.log(await getLatestLogs({ page: state.page, sinceLastCall: true })); console.log(await snapshot({ page: state.page }))'
```

**Always use single quotes** for the `-e` argument.
Single quotes prevent bash from interpreting `$`, backticks, and backslashes inside your JS code.
Use double quotes or backtick template literals for strings inside the JS.

If `playwriter` is not found, use `npx playwriter@latest` or `bunx playwriter@latest`.

## Video Recording: Skip the Extension Path

Use this section only after the capture plan has classified an item as video.
A static state that needs a setup action to reach it stays screenshot-classified when the setup action is not the fixed behavior.
Before recording video, read and follow `~/.agents/skills/k-playwriter/references/video-recording.md` in full, including file-size and frame verification.
