---
sidebar_position: 7
---

# Tmux: popups and tools

This setup includes a few tmux-native popups and helpers to keep your workflow inside tmux.

## Command palette

- Binding: `prefix` then `r`
- Purpose: unified fuzzy launcher that surfaces all custom tooling from a single keystroke — the "Cmd+K" for your terminal.

Sources indexed (in display order, with recency boost):

1. **`~/bin/,*` commands** — every executable `,*` script; descriptions are extracted from `# Description:` header comments when present.
2. **Tmux prefix keybindings** — parsed from `tmux list-keys -T prefix` (and the `k18` swap table) with human-readable labels.
3. **Git aliases** — global `git config` aliases shown as `git <alias>`.
4. **Drop-in extras** — any `.tsv` files in `~/.config/tmux/palette.d/` are appended verbatim (three tab-separated columns: display, key, exec).

Recency tracking:

- Each executed entry is timestamped in `~/.cache/tmux/palette_history.tsv`.
- On next open, recently used entries float to the top.

Execution model:

- **`,*` commands and git aliases**: inserted into the active pane with a trailing space; press Enter to run them.
- **Tmux bindings**: the selected tmux action runs immediately.

Options (tmux `set -g`):

| Option                          | Default |
| ------------------------------- | ------- |
| `@command_palette_popup_height` | `60`    |
| `@command_palette_popup_width`  | `70`    |

Extensibility:

- Drop a `.tsv` file into `~/.config/tmux/palette.d/` with three tab-separated columns per line: `<display>\t<unique-key>\t<exec-command>`. Entries appear automatically on next palette open.

Popup launchers pass `/bin/bash` and the script path directly to `display-popup`. They leave the server’s `default-shell` unchanged, including while another client opens a pane. Command previews read the script’s first 40 source lines; they never execute `--help`.

The separate `gh-dash` dashboard starts its nested session with a Bash login shell and restarts the dashboard after exit. Its config path, outer socket and client name pass as arguments, so spaces, quotes and shell metacharacters remain literal data.

## GitHub picker popup

- Binding: `prefix` then `G`
- Switch to session picker: `alt-g`

A standalone fzf-based PR/issue picker. It reads PR and issue sections from its own YAML config (`~/.config/tmux/scripts/pickers/github/gh-picker.yml`) and displays them in `fzf` with rich preview, worktree markers, and review status badges. gh-dash is not a dependency.

Implementation notes:

- Single `fzf` popup (no nested tmux server). Popup opens at 95%×95%.
- Items are fetched by `gh_items.sh` / `lib/gh_items_main.py`, which parses the gh-picker config file and runs GitHub Search API queries.
- `alt-g` closes the popup and reopens the session picker at its configured dimensions (and vice versa). The close-and-reopen loop lives in the outer wrapper scripts (`popup.sh` / `gh_popup.sh`).
- Popup launch passes the script directly to `/bin/bash` without changing the server’s `default-shell`.

For full keybindings and details, see [Tmux GitHub picker](github-picker.md).

## Repo bootstrap popup (`owner/repo` -> `,gh-tfork`)

- Binding: `prefix` then `B`
- Prompts for a GitHub repo spec like `owner/repo`, then runs `,gh-tfork`.
- `,gh-tfork` clones under `~/code`.
- Popup launch passes the script directly to `/bin/bash` without changing the server’s `default-shell`.

## Lowfi (music in tmux)

This setup includes an integration that runs `lowfi` inside a dedicated tmux session.

- Command: [`home/exact_bin/executable_,tmux-lowfi`](../../../../home/exact_bin/executable_,tmux-lowfi) (installs as `,tmux-lowfi`)
- Global keys (no tmux prefix): `F10` play/pause, `F11` skip, `F12` next tracklist

Tracklist data is pulled via externals into:

- `~/Library/Application Support/lowfi`

See [`home/.chezmoiexternal.toml`](../../../../home/.chezmoiexternal.toml).

## Verification and troubleshooting

```bash
tmux -V
tmux list-sessions
command -v ,w
command -v ,tmux-run-all
command -v ,tmux-lowfi
command -v gh
command -v fzf
```

If tmux config changes are not reflected:

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

## Related

- [Worktree workflow](../git-identity/worktrees.md)
