---
name: playwriter
description: "Control a real browser with Playwriter for browsing, UI checks, screenshots, automation, and live app verification."
---

# Playwriter

Use Playwriter for real browser work.
Do not wait for the user to name `playwriter` explicitly when the task involves browsing, browser automation,
rendered UI verification, visual inspection, screenshots, authenticated pages, SPAs, localhost web apps, form flows,
console/network inspection, or interactive browser behavior.

## REQUIRED: Read Full Documentation First

**Before using playwriter, you MUST run this command:**

```bash
playwriter skill
```

This outputs the complete documentation including:

- Session management and timeout configuration
- Selector strategies (and which ones to AVOID)
- Rules to prevent timeouts and failures
- Best practices for slow pages and SPAs
- Context variables, utility functions, and more

**Do NOT skip this step.** The quick examples below will fail without understanding timeouts, selector rules, and
common pitfalls from the full docs.

**Read the ENTIRE output.** Do NOT pipe through `head`, `tail`, or any truncation command.
The skill output must be read in its entirety — critical rules about timeouts, selectors, and
common pitfalls are spread throughout the document, not just at the top.

## Minimal Example (after reading full docs)

```bash
playwriter session new
playwriter -s 1 -e 'await page.goto("https://example.com")'
```

**Always use single quotes** for the `-e` argument.
Single quotes prevent bash from interpreting `$`, backticks, and backslashes inside your JS code.
Use double quotes or backtick template literals for strings inside the JS.

If `playwriter` is not found, use `npx playwriter@latest` or `bunx playwriter@latest`.
