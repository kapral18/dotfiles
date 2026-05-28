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
- Strips invisible Unicode formatting characters (zero-width space `U+200B`, ZWJ/ZWNJ, BOM, bidi marks, etc.) from captured pane content before URL extraction. These commonly leak in via copy-paste from web pages and would otherwise be appended to URLs (the bash extractor's `[^[:space:]]+` regex doesn't treat them as whitespace), causing 404s.

## Related

- [Session picker](session-picker.md)
- [GitHub picker](github-picker.md)
- [Popups + tools](popups-and-tools.md)
