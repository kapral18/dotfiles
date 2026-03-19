---
name: kibana-console-monaco
description: |-
  Interact with the Kibana Dev Tools Console Monaco editor via Playwright /
  Playwriter. Use when automating or testing the Console editor in a real
  browser. Only for elastic/kibana repos.
---

# Kibana Dev Tools Console — Monaco Editor Interaction

Use when: automating, testing, or verifying behavior of the Kibana Dev Tools
Console editor in a headed browser via Playwright or Playwriter.

## Navigation

`http://<host>:5601/app/dev_tools#/console`

If the instance requires login, authenticate first or reuse an already-logged-in
tab via `context.pages()`.

## Editor Layers & Clicking

The Console editor is a Monaco instance wrapped in Kibana's `EuiCodeEditor`.
Three layers can intercept pointer events:

1. **`codeEditorHint`** — a "Code Editor, activate edit mode" overlay
   (`[data-test-subj="codeEditorHint"]`). Appears when the editor loses focus.
2. **`.view-lines`** — Monaco's rendered text layer. Always sits on top of the
   underlying `<textarea>`.
3. **`<textarea role="textbox">`** — the actual input element. Hidden behind
   `.view-lines`; direct clicks always time out.

### How to click into the editor reliably

```js
// Use force: true on the .monaco-editor container.
// This bypasses the overlay checks that Playwright enforces.
await state.page.locator(".monaco-editor").first().click({ force: true });
```

**Never** try to click the `<textarea>` directly — the `.view-lines` overlay
will always intercept and Playwright will time out.

If the `codeEditorHint` overlay is visible and you want to click it
specifically, it too sits behind `.view-lines`, so `{ force: true }` is needed:

```js
await state.page
  .locator('[data-test-subj="codeEditorHint"]')
  .click({ force: true });
```

## Setting Content

### Import button (preferred for multi-line content)

Interactive typing triggers Monaco auto-close (`{` becomes `{}`, Enter is
consumed by brace handling, etc.). Use the hidden file input to bypass this:

```js
const fs = require("node:fs");
fs.writeFileSync(
  "/tmp/console_input.txt",
  `GET _search
{
  "query": {
    "match_all": {}
  }
}`,
);

const fileInput = state.page.locator("#importConsoleFile");
await fileInput.setInputFiles("/tmp/console_input.txt");
await state.page.waitForTimeout(500);
await state.page.locator('role=button[name="Import and replace"]').click();
await state.page.waitForTimeout(1000);
```

**Notes:**

- The import confirmation modal always appears — click "Import and replace" to
  confirm.
- Trailing whitespace on lines may be stripped by the import.

### Clear editor

```js
await state.page.locator(".monaco-editor").first().click({ force: true });
await state.page.keyboard.press("Meta+a"); // Cmd+A on macOS
await state.page.keyboard.press("Backspace");
await state.page.waitForTimeout(500);
```

### Interactive typing (simple one-liners only)

Only use for content where auto-close won't interfere (no braces, no quotes):

```js
await state.page.keyboard.type("GET _search", { delay: 30 });
```

For multi-line or JSON content, always use the import button approach above.

## Cursor Positioning

### Clicking on a specific line

The `.view-line` elements are 0-indexed in DOM order. Find the right one:

```js
const lines = state.page.locator(".view-line");
const count = await lines.count();
for (let i = 0; i < count; i++) {
  console.log(`${i}: "${await lines.nth(i).textContent()}"`);
}
```

Then click on the target line. **Critical:** each `.view-line` spans the full
editor width. Clicking near the right edge puts the cursor past all content
(often jumping to a different logical line). Click near the actual text:

```js
const targetLine = lines.nth(4);
const box = await targetLine.boundingBox();
// Click ~160-200px from left edge (near end of typical indented JSON key)
await state.page.mouse.click(box.x + 160, box.y + box.height / 2);
await state.page.waitForTimeout(300);
await state.page.keyboard.press("End");
```

### Keyboard navigation

After clicking into the editor:

```js
await state.page.keyboard.press("Meta+Home"); // go to top
await state.page.keyboard.press("Meta+End"); // go to bottom
await state.page.keyboard.press("End"); // end of current line
await state.page.keyboard.press("Home"); // start of current line
await state.page.keyboard.press("ArrowDown"); // move down one line
await state.page.keyboard.press("ArrowUp"); // move up one line
```

**Note:** `Ctrl+G` (Go to Line) does NOT work — the Console editor intercepts
it. Use ArrowDown/ArrowUp from a known position instead.

**Note:** `Enter` does NOT reliably create new lines — the Console editor's
brace handling may consume it. This is why importing content is preferred over
typing.

## Triggering Autocomplete

```js
await state.page.keyboard.press("Control+Space");
await state.page.waitForTimeout(2500); // autocomplete needs time to load
```

**Important behaviors:**

- Autocomplete requires the endpoint to be recognized by the Console's API spec.
  Unknown endpoints won't produce body suggestions.
- After triggering, dismiss with `Escape` before trying again.
- Accept a suggestion with `Enter`.
- The autocomplete popup renders as a Monaco widget overlay, visible in
  screenshots.

## Reading Editor Content

```js
const lines = state.page.locator(".view-line");
const count = await lines.count();
for (let i = 0; i < count; i++) {
  const text = await lines.nth(i).textContent();
  console.log(`Line ${i}: "${text}"`);
}
```

**Note:** `window.monaco` is not exposed in Kibana. Do not try to access the
Monaco API via `page.evaluate()`. Use DOM-based approaches instead.

## Screenshots

Always use `scale: 'css'` to avoid oversized images on Retina displays. Crop to
the editor area for focused verification shots:

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

## Common Pitfalls

| Problem                                       | Cause                       | Fix                                             |
| --------------------------------------------- | --------------------------- | ----------------------------------------------- |
| `locator.click: Timeout exceeded` on textarea | `.view-lines` intercepts    | Click `.monaco-editor` with `{ force: true }`   |
| `codeEditorHint` intercepts clicks            | Editor lost focus           | Click `.monaco-editor` with `{ force: true }`   |
| Typed `{` becomes `{}`                        | Monaco auto-close           | Use import button instead of typing             |
| `Enter` doesn't create new line               | Console brace handling      | Use import button instead of typing             |
| Cursor lands on wrong line after click        | Clicked too far right       | Click closer to actual text (~160px from left)  |
| Autocomplete shows HTTP methods               | Cursor is in root context   | Position cursor inside JSON body, not after `}` |
| `Ctrl+G` types text instead of Go-to-Line     | Console intercepts shortcut | Use ArrowDown/ArrowUp navigation                |
| `window.monaco` is undefined                  | Kibana doesn't expose it    | Use DOM `.view-line` elements instead           |

## Full Example: Import Content, Position Cursor, Trigger Autocomplete

```js
// 1. Clear and import
await state.page.locator(".monaco-editor").first().click({ force: true });
await state.page.keyboard.press("Meta+a");
await state.page.keyboard.press("Backspace");
await state.page.waitForTimeout(500);

const fs = require("node:fs");
fs.writeFileSync(
  "/tmp/input.txt",
  'PUT test_index\n{\n  "mappings": {\n    "properties": {\n      "field1": \n    }\n  }\n}',
);
await state.page.locator("#importConsoleFile").setInputFiles("/tmp/input.txt");
await state.page.waitForTimeout(500);
await state.page.locator('role=button[name="Import and replace"]').click();
await state.page.waitForTimeout(1500);

// 2. Click on the "field1" line and go to end
const lines = state.page.locator(".view-line");
const targetLine = lines.nth(4);
const box = await targetLine.boundingBox();
await state.page.mouse.click(box.x + 160, box.y + box.height / 2);
await state.page.waitForTimeout(300);
await state.page.keyboard.press("End");

// 3. Trigger autocomplete
await state.page.keyboard.press("Control+Space");
await state.page.waitForTimeout(2500);

// 4. Screenshot the result
const editorArea = state.page.locator(".monaco-editor").first();
const edBox = await editorArea.boundingBox();
await state.page.screenshot({
  path: "/tmp/result.png",
  scale: "css",
  clip: { x: edBox.x, y: edBox.y, width: 550, height: 400 },
});
```
