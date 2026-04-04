# Tmux: popups and tools

Back: [`docs/categories/tmux/index.md`](index.md)

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

- **`,*` commands and git aliases**: sent to the active pane via `tmux send-keys … Enter` so the command runs in your shell with full environment context.
- **Tmux bindings**: re-invoked via `tmux send-keys C-Space <key>` so the binding fires exactly as if you pressed it.

Options (tmux `set -g`):

| Option                          | Default |
| ------------------------------- | ------- |
| `@command_palette_popup_height` | `60`    |
| `@command_palette_popup_width`  | `70`    |

Extensibility:

- Drop a `.tsv` file into `~/.config/tmux/palette.d/` with three tab-separated columns per line: `<display>\t<unique-key>\t<exec-command>`. Entries appear automatically on next palette open.

Popup spawn temporarily overrides `default-shell` to `/bin/sh` via `command_palette/popup.sh` to avoid heavy-shell initialization overhead (~1s with fish).

## GitHub picker popup

- Binding: `prefix` then `G`
- Switch work/home: `Tab`
- Switch to session picker: `alt-g`

A standalone fzf-based PR/issue picker. It reads PR and issue sections from its own YAML configs (`~/.config/tmux/scripts/pickers/github/gh-picker-{work,home}.yml`) and displays them in `fzf` with rich preview, worktree markers, and review status badges. gh-dash is not a dependency.

Implementation notes:

- Single `fzf` popup (no nested tmux server). Popup opens at 95%×95%.
- Items are fetched by `gh_items.sh` / `lib/gh_items_main.py`, which parses the gh-picker config files and runs GitHub Search API queries.
- `alt-g` closes the popup and reopens the session picker at its configured dimensions (and vice versa). The close-and-reopen loop lives in the outer wrapper scripts (`popup.sh` / `gh_popup.sh`).
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` to avoid heavy-shell initialization overhead (~1s with fish).

For full keybindings and details, see [`docs/categories/tmux/pickers.md` — GitHub picker](pickers.md#github-picker).

## Repo bootstrap popup (`owner/repo` -> `,gh-tfork`)

- Binding: `prefix` then `B`
- Prompts for a GitHub repo spec like `elastic/kibana`, then runs `,gh-tfork`.
- `,gh-tfork` decides the destination:
  - `~/work` for owner `elastic`
  - `~/code` for everything else
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` to avoid heavy-shell initialization overhead (~1s with fish).

## Lowfi (music in tmux)

This setup includes an integration that runs `lowfi` inside a dedicated tmux session.

- Command: [`home/exact_bin/executable_,tmux-lowfi`](../../../home/exact_bin/executable_,tmux-lowfi) (installs as `,tmux-lowfi`)
- Global keys (no tmux prefix): `F10` play/pause, `F11` skip, `F12` next tracklist

Tracklist data is pulled via externals into:

- `~/Library/Application Support/lowfi`

See [`home/.chezmoiexternal.toml`](../../../home/.chezmoiexternal.toml).

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

- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../../recipes/worktree-workflow.md)
