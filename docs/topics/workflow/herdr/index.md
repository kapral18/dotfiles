# herdr

This setup runs everything inside [herdr](https://github.com/herdrdev/herdr), a terminal workspace manager for coding agents, hosted in Ghostty. One terminal window holds persistent workspaces (one per repo or worktree), tabs, and panes; the herdr server keeps them running when the client detaches.

## Mental model

| Layer               | What it does                                                                            |
| ------------------- | --------------------------------------------------------------------------------------- |
| Workspace           | One project or worktree; its label is `<repo>\|<branch>` for `,w` and picker workspaces |
| Sidebar             | Lists workspaces with branch, ahead/behind, and badges for dirty state, PR, review, CI  |
| Agent state         | Every pane running a coding agent shows blocked / working / done / idle                 |
| Cache-first pickers | Popups show cached rows immediately and refresh in the background                       |

## Config location

- [`home/dot_config/herdr/readonly_config.toml`](../../../../home/dot_config/herdr/readonly_config.toml) — keys, theme (catppuccin frappé colors), sidebar rows, custom popup commands
- [`home/dot_config/herdr/exact_scripts/`](../../../../home/dot_config/herdr/exact_scripts/) — picker, palette, URL, and pane scripts
- [`home/dot_config/herdr/exact_scripts/plugins/`](../../../../home/dot_config/herdr/exact_scripts/plugins/) — the `k18.workspace-history` and `k18.pickers` plugins, linked by `chezmoi apply`

`~/.config/herdr` is herdr's own data directory (socket, `session.json`, installed plugins), so only `scripts/` under it is an exact chezmoi directory. Validate edits with `herdr config check`; apply a running server's config with `prefix` + `R`.

## Cheat sheet (this config)

- Prefix: `Ctrl-Space`
- Workspaces: sidebar navigation `prefix` + `w`; goto picker `prefix` + `g`; last workspace `prefix` + `S`; previous/next `prefix` + `(` / `)`; new `prefix` + `C`; rename `prefix` + `$`; close `prefix` + `X`
- Worktrees: new `prefix` + `W`; open existing `prefix` + `O`
- Tabs: new (current pane path) `prefix` + `c`; next/previous `prefix` + `n` / `p` (also `C-n` / `C-p`); move `prefix` + `<` / `>` (or `prefix` + `s` then `H` / `L`); rename `prefix` + `,`; close `prefix` + `&`
- Panes: focus `prefix` + `h/j/k/l` (also `C-h/C-j/C-k/C-l` and arrows); resize `prefix` + `H/J/K/L` (also `C-arrows`, and `M-Up` / `M-Down`: Ghostty sends `M-Left` / `M-Right` as word motion); swap with the neighbor on screen `prefix` + `s` then `h/j/k/l` (left/right also `prefix` + `{` / `}`); last pane `prefix` + `;`; split right `prefix` + `|` / `%`; split down `prefix` + `-` / `"`; zoom `prefix` + `f`; close `prefix` + `x`
- Join a pane from another workspace: `prefix` + `t` (right) / `C-t` (below); move the current pane to a new workspace: `prefix` + `@`; move the current tab to a new workspace: `prefix` + `!`
- Copy mode (vi): `prefix` + `[`; `v` select, `y` copy
- Detach: `prefix` + `d`; next pane `prefix` + `o` (also `tab`); jump to a notification's target `prefix` + `N`; key help: `prefix` + `?`; herdr settings: `prefix` + `.`

tmux keys that changed or have no herdr equivalent. herdr has its own fixed key set: a tmux key that is not on this cheat sheet or in herdr's help (`prefix` + `?`) does nothing, including tmux defaults never set in the old config. The ones you are likely to reach for:

- Moved: your tmux `prefix` + `C-@` (tab to a new session) is `prefix` + `!`, since herdr reserves `prefix` + `C-Space` for sending a literal prefix.
- Changed meaning: `prefix` + `!` moves the tab to a new workspace (break a pane out with `prefix` + `@`); `prefix` + `.` opens herdr settings; `prefix` + `C-r` is resize mode (herdr restores sessions itself); `prefix` + `s` then `h` / `l`, and `prefix` + `{` / `}`, swap with the on-screen neighbor instead of the previous/next pane in order; resize and tab-move keys no longer repeat without the prefix (tmux `-r`), so use resize mode `prefix` + `C-r` to resize repeatedly; `y` in copy mode copies and leaves copy mode (tmux kept it open).
- Not available: full-span splits (`\`, `_`); layouts (`Space`, `M-1..5`, `E` spread evenly) and rotate (`C-o` / `M-o`); mark pane (`m` / `M`); the join-pane direction table (only `prefix` + `t` / `C-t`); paste buffers (`]`, `#`, `=`) and middle-click paste (paste with Cmd+V); copy mode via `PageUp` (herdr keybindings cannot name PageUp); copy-mode keys beyond herdr's set (rectangle `C-v`, `f/F/t/T`, `H/M/L`, `%`, counts — herdr copy mode has exactly: `h/j/k/l` and arrows, `w/b/e`, `W/B/E`, `{` / `}`, `0/$/^`, `Home` / `End`, `g/G`, `C-u` / `C-d`, `C-b` / `C-f`, `PageUp` / `PageDown`, `/` `?` `n` `N`, `v` / `Space`, `V`, `y` / `Enter`, `q` / `Esc`); triple-click line select (double-click word select and drag-to-copy still work); the command prompt (`:`); pane numbers (`q`); and tmux's window/client keys (`'`, `M-n` / `M-p`, `/`, `S-arrows`, `DC`, `D`, `i`, `~`, `C-z`, right-click menus). Window by index works as `prefix` + `1..9`.
- Not needed: tpm (`I` / `U` / `M-u`) and tmux-resurrect save/restore (`C-s` / `C-r`), since herdr saves the session on every change and restores it on start; the root `C-S-h/j/k/l` passthrough, since herdr forwards Ctrl+Shift keys to apps that enable the kitty keyboard protocol.

## Tools and integrations

- Project (session) picker popup: `prefix` + `T`
- GitHub picker popup: `prefix` + `G` (`alt-g` switches between the two pickers in the same popup)
- Command palette popup: `prefix` + `r`
- URL picker popup: `prefix` + `u`
- Repo bootstrap popup (`owner/repo` → `,gh-tfork`): `prefix` + `B`
- Agent board popup: `prefix` + `A` (`,task board`)
- lowfi: `F10` / `F11` / `F12` (no prefix)

For details:

- [Popups + tools](popups-and-tools.md)
- [Pickers overview + URL picker](pickers.md)
- [Session picker](session-picker.md)
- [GitHub picker](github-picker.md)
