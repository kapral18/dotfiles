# Tmux: popups and tools

Back: [`docs/categories/tmux/index.md`](index.md)

This setup includes a few tmux-native popups and helpers to keep your workflow inside tmux.

## Command palette popup: `,tmux-run-all`

- Binding: `prefix` then `r`
- Purpose: quick launcher for common commands.
- Popup spawn temporarily overrides `default-shell` to `/bin/sh` via `command_palette_popup.sh` to avoid heavy-shell initialization overhead (~1s with fish).

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

