# Tmux: popups and tools

Back: [`docs/categories/tmux/index.md`](index.md)

This setup includes a few tmux-native popups and helpers to keep your workflow inside tmux.

## Command palette

- Binding: `prefix` then `r`
- Purpose: unified fuzzy launcher that surfaces all custom tooling from a single
  keystroke — the "Cmd+K" for your terminal.

Sources indexed (in display order, with recency boost):

1. **`~/bin/,*` commands** — every executable `,*` script; descriptions are
   extracted from `# Description:` header comments when present.
2. **Tmux prefix keybindings** — parsed from `tmux list-keys -T prefix` (and
   the `k18` swap table) with human-readable labels.
3. **Git aliases** — global `git config` aliases shown as `git <alias>`.
4. **Drop-in extras** — any `.tsv` files in `~/.config/tmux/palette.d/` are
   appended verbatim (three tab-separated columns: display, key, exec).

Recency tracking:

- Each executed entry is timestamped in `~/.cache/tmux/palette_history.tsv`.
- On next open, recently used entries float to the top.

Execution model:

- **`,*` commands and git aliases**: sent to the active pane via
  `tmux send-keys … Enter` so the command runs in your shell with full
  environment context.
- **Tmux bindings**: re-invoked via `tmux send-keys C-Space <key>` so the
  binding fires exactly as if you pressed it.

Options (tmux `set -g`):

- `@command_palette_popup_height` (default `60`)
- `@command_palette_popup_width` (default `70`)

Extensibility:

- Drop a `.tsv` file into `~/.config/tmux/palette.d/` with three tab-separated
  columns per line: `<display>\t<unique-key>\t<exec-command>`. Entries appear
  automatically on next palette open.

Popup spawn temporarily overrides `default-shell` to `/bin/sh` via
`command_palette_popup.sh` to avoid heavy-shell initialization overhead (~1s
with fish).

## Persistent `gh-dash` popup

- Binding: `prefix` then `G`
- Hide without quitting: `q`, `Ctrl-C`, or `prefix` + `G`
- Restart the persistent instance: `prefix` + `C-g`

Implementation notes:

- The popup attaches to a **nested tmux server** (separate socket) running `gh dash`.
- Hiding the popup detaches from that nested tmux client; the `gh-dash` process stays alive for fast reopen.
- **Fast path**: when the nested session already exists, the popup skips all dependency checks (`gh`, `gh dash --version`) and jumps straight to `display-popup`. This saves ~80ms on every subsequent open.
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` to avoid heavy-shell initialization overhead (~1s with fish).

## Repo bootstrap popup (`owner/repo` -> `,gh-tfork`)

- Binding: `prefix` then `B`
- Prompts for a GitHub repo spec like `elastic/kibana`, then runs `,gh-tfork`.
- `,gh-tfork` decides the destination:
  - `~/work` for owner `elastic`
  - `~/code` for everything else
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` to avoid heavy-shell initialization overhead (~1s with fish).

## Lowfi (music in tmux)

This setup includes an integration that runs `lowfi` inside a dedicated tmux session.

- Command: `home/exact_bin/executable_,tmux-lowfi` (installs as `,tmux-lowfi`)
- Global keys (no tmux prefix): `F10` play/pause, `F11` skip, `F12` next tracklist

Tracklist data is pulled via externals into:

- `~/Library/Application Support/lowfi`

See `home/.chezmoiexternal.toml`.

## Verification and troubleshooting

```bash
tmux -V
tmux list-sessions
command -v ,w
command -v ,tmux-run-all
command -v ,tmux-lowfi
gh dash --version
```

If tmux config changes are not reflected:

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

## Related

- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../../recipes/worktree-workflow.md)

