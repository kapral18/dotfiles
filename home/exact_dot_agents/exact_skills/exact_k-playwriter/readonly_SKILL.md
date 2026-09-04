---
name: k-playwriter
description: "Use for real browser: browsing, UI checks, screenshots, automation, verification, visual QA."
---

# Playwriter

Use Playwriter for real browser work.
Fire without waiting for the user to name `playwriter` explicitly whenever the task needs a real browser.

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

**Do NOT skip this step.**
The quick examples below will fail without understanding timeouts, selector rules, and common pitfalls from the full docs.

**Read the ENTIRE output.** Do NOT pipe through `head`, `tail`, or any truncation command.
The skill output must be read in its entirety — critical rules about timeouts, selectors, and common pitfalls are spread throughout the document, not just at the top.

## Minimal Example (after reading full docs)

```bash
playwriter session new
playwriter -s 1 -e 'await page.goto("https://example.com")'
```

**Always use single quotes** for the `-e` argument.
Single quotes prevent bash from interpreting `$`, backticks, and backslashes inside your JS code.
Use double quotes or backtick template literals for strings inside the JS.

If `playwriter` is not found, use `npx playwriter@latest` or `bunx playwriter@latest`.

## Video Recording: Skip the Extension Path

Use this section only after the capture plan has classified an item as video.
A static state that needs a setup action to reach it stays screenshot-classified when the setup action is not the fixed behavior.
Before recording video, read and follow `~/.agents/skills/k-playwriter/references/video-recording.md` in full, including file-size and frame verification.
