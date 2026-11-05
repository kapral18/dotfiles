---
sidebar_position: 1
---

# herdr: pickers

This setup ships three fzf-based pickers that run in herdr popups:

- **URL picker** (`prefix` + `u`) — extract and open URLs from the current pane. Documented below.
- **[Session picker](session-picker.md)** (`prefix` + `T`) — open, close, and send commands to herdr workspaces, worktrees, and directories with git/GitHub status badges.
- **[GitHub picker](github-picker.md)** (`prefix` + `G`) — a PR/issue dashboard with review/CI badges, hierarchy, and inline GitHub actions.

The session and GitHub pickers are siblings: `alt-g` switches between them in place.

---

## URL picker

### Bindings

- `prefix` + `u` — open URL picker popup

### Options (environment)

| Variable                 | Default  | Description                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PICK_URL_HISTORY_LIMIT` | `screen` | `screen` scans from the top of the shown screen (scrolled back too) down to the latest output, plus a few rows above it when the bottom of the screen is blank; a number scans that many recent rows (herdr caps reads at 1000). Both join soft-wrapped lines so a long URL stays whole, except when the screen rows plus the scroll-back exceed 1000, where the screen is read as shown |
| `PICK_URL_OPEN_CMD`      | `open`   | Command used to open each selected URL                                                                                                                                                                                                                                                                                                                                                   |
| `PICK_URL_EXTRA_FILTER`  | —        | Additional filter applied to URL candidates                                                                                                                                                                                                                                                                                                                                              |

### Behavior

- Reads the pane under the popup with `herdr pane read --source recent-unwrapped --ansi`, sized to the viewport rows plus the scroll offset from `herdr pane get`, or to the numeric limit; past 1000 rows, or when `pane get` gives no size, it reads `--source visible`.
- With no URLs on the pane (or an unreadable pane), the popup says so and closes on any key or after 3 seconds.
- De-duplicates path-prefix URLs: if both `https://site/x` and `https://site/x/y` are detected, it keeps the deeper path entry.
- Runs `fzf` with `FZF_DEFAULT_OPTS` cleared so global defaults don't distort the popup UI.
- Sanitizes captured pane text before extraction: strips ANSI/control sequences, rewrites OSC 8 hyperlinks to their target URL (including wrapped labels), normalizes embedded whitespace and escaped-whitespace corruption (`\\n`, `\\r`, `\\t`) in OSC targets and in each extracted candidate, and strips invisible Unicode format characters (for example zero-width space `U+200B`, ZWJ/ZWNJ, BOM, bidi marks). Visible pane text is left otherwise intact, so a literal `\n` in prose is not silently deleted.
- Rejoins URLs split across a render-time wrap when matching box borders on both adjacent lines prove an arbitrary path break. Without that pair, it joins only stronger URL structure such as an incomplete dotted host or a trailing hyphen/query/fragment marker; a trailing slash alone remains complete. Plain prose, Markdown links, list items, headings, and merely indented lines remain separate.
- Strips trailing Markdown/code punctuation, including backticks, before de-duplicating path-prefix URLs so inline-code examples like `` `https://site/x` `` do not survive as separate broken candidates.
- Validates cleaned candidates with Python's stdlib URL parser after terminal/Markdown boundary cleanup, so malformed leftovers are rejected without adding non-stdlib dependencies.
- Drops display-abbreviated candidates that contain a literal ellipsis (`...` or `…`): these are terminal/pager truncations of a longer URL and cannot be resolved, so they are never offered.
- Canonicalizes GitHub discussion anchors by dropping UI status offsets, leaving the stable `#discussion_r123` anchor. The anchor ends at its numeric id, so any trailing render noise a wrapped pane produces is dropped regardless of separator (`_+13|Resolved`, `-13`, `.+13`, or a bare trailing `-`). Other anchors are untouched: line ranges like `#L10-L20`, slugs ending in `-1`, and GitHub's `#issuecomment-`, `#pullrequestreview-`, and `#diff-` forms.

## Related

- [Session picker](session-picker.md)
- [GitHub picker](github-picker.md)
- [Popups + tools](popups-and-tools.md)
