---
sidebar_position: 1
---

# Tmux: pickers

This setup ships three fzf-based pickers designed to run inside tmux popups:

- **URL picker** (`prefix` + `u`) — extract and open URLs from the current pane. Documented below.
- **[Session picker](session-picker.md)** (`prefix` + `T`) — switch/create/kill tmux sessions, worktrees, and directories with git/GitHub status badges.
- **[GitHub picker](github-picker.md)** (`prefix` + `G`) — a PR/issue dashboard with review/CI badges, hierarchy, and inline GitHub actions.

The session and GitHub pickers are siblings: `alt-g` switches between them in place.

---

## URL picker

### Bindings

- `prefix` + `u` — open URL picker popup

### Options

| Option                    | Default                                                  | Description                                 |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------- |
| `@pick_url_history_limit` | `screen`                                                 | How far back to scan for URLs               |
| `@pick_url_popup`         | configured `center,60%,35%` (fallback `center,100%,50%`) | Popup geometry                              |
| `@pick_url_fzf_flags`     | —                                                        | Extra flags passed to `fzf`                 |
| `@pick_url_open_cmd`      | —                                                        | Command used to open selected URL           |
| `@pick_url_extra_filter`  | —                                                        | Additional filter applied to URL candidates |

### Behavior

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
