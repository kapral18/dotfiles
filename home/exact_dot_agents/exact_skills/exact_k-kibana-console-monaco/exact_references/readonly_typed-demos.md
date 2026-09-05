# Typed demos

## Enter swallowing: root causes and safeEnter

`Enter` failing to insert a newline has two distinct causes; neither is random:

1. An open suggest widget accepts the highlighted suggestion instead of inserting a newline.
2. Pressing `Escape` while **no** widget is open bubbles out of Monaco and moves focus to an EUI element (`document.activeElement` becomes an Emotion `css-*` node, not `textarea.inputarea`).
   Every later key goes nowhere.

For content setup, use the import procedure in `~/.agents/skills/k-kibana-console-monaco/SKILL.md`.
For typed demos/videos requiring visible keystrokes, use this recipe:

```js
const widgetVisible = (page) =>
  page.evaluate(
    () =>
      document
        .querySelector(".suggest-widget")
        ?.classList.contains("visible") ?? false,
  );
const lineCount = (page) =>
  page.evaluate(() => document.querySelectorAll(".view-line").length);

async function safeEnter(page) {
  for (let i = 0; i < 4; i++) {
    if (await widgetVisible(page)) {
      // Escape ONLY when the widget is open
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
    await page.evaluate(() => {
      // re-focus without moving the cursor
      const ta = document.querySelector("textarea.inputarea");
      if (ta && document.activeElement !== ta) ta.focus();
    });
    const before = await lineCount(page);
    await page.keyboard.press("Enter");
    await page.waitForTimeout(350);
    if ((await lineCount(page)) > before) return; // verify the newline actually landed
  }
  throw new Error("Enter never inserted a newline");
}
```
