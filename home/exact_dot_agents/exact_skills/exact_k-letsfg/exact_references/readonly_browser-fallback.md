# Browser fallback

1. Use Playwriter only when rendered UI is required, such as visual checks or investigating a website regression.
   Prefer the Homebrew-managed Chrome app already present on this machine:

```bash
playwriter browser list
profile="$(mktemp -d -t playwriter-letsfg.XXXXXX)"
playwriter browser start "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --user-data-dir "$profile"
playwriter browser list
```

If `playwriter session new` reports multiple browsers, select the extension key for the browser you just started.
Record the browser PID from `playwriter browser start` and kill it after the task if no longer needed.

```bash
playwriter session new --browser <extension-key>
playwriter -s <session-id> --timeout 360000 -e 'state.page = await context.newPage(); await state.page.goto("https://letsfg.co", { waitUntil: "domcontentloaded" }); console.log(await state.page.title())'
```

Use single quotes around `-e` snippets unless using a quoted heredoc, so the shell does not expand `$`, backticks, or backslashes.

- Playwriter has a hidden browser launcher: `playwriter browser start --headless`.
  The default browser lookup may miss `/Applications/Google Chrome.app`; pass that binary explicitly when browser fallback is needed.
  This keeps LetsFG out of always-loaded MCP while still allowing rendered UI automation on demand.
