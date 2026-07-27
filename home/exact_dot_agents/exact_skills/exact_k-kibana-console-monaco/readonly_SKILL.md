---
name: k-kibana-console-monaco
description: "Use when automating/testing Kibana Dev Tools Console Monaco in a headed browser; elastic/kibana only."
---

# Kibana Dev Tools Console — Monaco Editor Interaction

Use for Kibana Dev Tools Console editor automation in a headed browser via Playwright/Playwriter.

## Navigation and auth

- URL: `http://<host>:5601/app/dev_tools#/console`.
- If already logged in, reuse the tab via `context.pages()` when practical.
- Security-enabled local stacks may redirect to `/mock_idp/login`; select **Test User**, click **Log in**, wait for `networkidle`.
  The first click can land mid-redirect with `401 Unauthorized`; if still on `/mock_idp/login`, retry once.
- The default viewer role is enough for read-only autocomplete checks.
- For base/head comparisons, authenticate each host/page separately.

## Editor layers and clicks

Console wraps Monaco in `EuiCodeEditor`. Pointer layers:

1. `[data-test-subj="codeEditorHint"]` — “Code Editor, activate edit mode” overlay after blur.
2. `.view-lines` — rendered Monaco text layer.
3. `<textarea role="textbox">` — hidden input; direct clicks time out because `.view-lines` intercepts.

Reliable focus:

```js
await state.page.locator(".monaco-editor").first().click({ force: true });
```

If clicking `codeEditorHint` directly, use `{ force: true }` too. Never click the textarea directly.

## Setting content

Prefer import for multiline/JSON content. Typing triggers Monaco auto-close and brace handling.

```js
const fs = require("node:fs");
fs.writeFileSync(
  "/tmp/console_input.txt",
  `GET _search\n{\n  "query": { "match_all": {} }\n}`,
);
await state.page
  .locator("#importConsoleFile")
  .setInputFiles("/tmp/console_input.txt");
await state.page.waitForTimeout(500);
await state.page.locator('role=button[name="Import and replace"]').click();
await state.page.waitForTimeout(1000);
```

Notes: the confirmation modal always appears; trailing whitespace may be stripped.

Clear editor:

```js
await state.page.locator(".monaco-editor").first().click({ force: true });
await state.page.keyboard.press("Meta+a");
await state.page.keyboard.press("Backspace");
await state.page.waitForTimeout(500);
```

Interactive typing is for simple one-liners only:

```js
await state.page.keyboard.type("GET _search", { delay: 30 });
```

## Cursor positioning

Read visible line indexes:

```js
const lines = state.page.locator(".view-line");
const count = await lines.count();
for (let i = 0; i < count; i++)
  console.log(`${i}: "${await lines.nth(i).textContent()}"`);
```

To click a target line, avoid the far right edge; each `.view-line` spans full width and right-edge clicks place the cursor past content or on another logical line.

```js
const targetLine = lines.nth(4);
const box = await targetLine.boundingBox();
await state.page.mouse.click(box.x + 160, box.y + box.height / 2);
await state.page.waitForTimeout(300);
await state.page.keyboard.press("End");
```

Keyboard navigation after focus: `Meta+Home`, `Meta+End`, `Home`, `End`, `ArrowDown`, `ArrowUp`.
`Ctrl+G` does not work; Console intercepts it. `Enter` does not reliably create lines; import content instead.

## Autocomplete

```js
await state.page.keyboard.press("Control+Space");
await state.page.waitForTimeout(2500);
```

- Endpoint must be recognized by the Console API spec; unknown endpoints do not produce body suggestions.
- Dismiss with `Escape` before trying again.
- Accept with `Enter`.
- Popup renders as a Monaco widget visible in screenshots.

## Reading and screenshots

Read content from DOM lines; `window.monaco` is not exposed in Kibana.

```js
const lines = state.page.locator(".view-line");
for (let i = 0; i < (await lines.count()); i++)
  console.log(`Line ${i}: "${await lines.nth(i).textContent()}"`);
```

Use `scale: "css"` for screenshots to avoid Retina oversize. Crop focused shots to `.monaco-editor`:

```js
const editorArea = state.page.locator(".monaco-editor").first();
const edBox = await editorArea.boundingBox();
await state.page.screenshot({
  path: "/tmp/console_screenshot.png",
  scale: "css",
  clip: {
    x: edBox.x,
    y: edBox.y,
    width: Math.min(edBox.width, 550),
    height: 300,
  },
});
```

## Pitfalls

| Problem                                      | Fix                                           |
| -------------------------------------------- | --------------------------------------------- |
| `locator.click` timeout on textarea          | Click `.monaco-editor` with `{ force: true }` |
| `codeEditorHint` intercepts clicks           | Click `.monaco-editor` with `{ force: true }` |
| Typed `{` becomes `{}` or Enter is swallowed | Use import button                             |
| Cursor lands on wrong line                   | Click closer to text (~160px from left)       |
| Autocomplete shows HTTP methods              | Put cursor inside JSON body, not after `}`    |
| `Ctrl+G` types text                          | Use ArrowDown/ArrowUp from known position     |
| `window.monaco` is undefined                 | Use DOM `.view-line` elements                 |

Full import/cursor/autocomplete/screenshot example: `~/.agents/skills/k-kibana-console-monaco/references/console-monaco-example.md`.
