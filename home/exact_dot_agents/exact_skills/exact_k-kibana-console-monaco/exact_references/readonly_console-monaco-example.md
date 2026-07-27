# Kibana Console Monaco Full Example

Load when you need a complete Playwright/Playwriter script shape for importing Console content, positioning the cursor, triggering autocomplete, and capturing the result.

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
