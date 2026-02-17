# Terminals And Tmux

Back: [`docs/categories/index.md`](index.md)

This setup is designed around a tmux-driven workflow.

If you are coming from VSCode/JetBrains, you can still use tmux incrementally.
The lowest-disruption path is to use tmux for long-running sessions (servers,
test watchers) while keeping your main editor unchanged.

## Terminal

Default terminal emulator config:

- `home/dot_config/exact_ghostty/config`

## Bat (Better `cat`)

- Config: `home/dot_config/bat/config`

Themes are pulled via externals into:

- `~/.config/bat/themes`

See `home/.chezmoiexternal.toml`.

## Tmux

- Config: `home/dot_config/tmux/tmux.conf`

Notable choices:

- prefix is `Ctrl-Space`
- vi copy-mode
- passthrough bindings for Neovim navigation

## Tmux Cheat Sheet (This Config)

These are implemented in `home/dot_config/tmux/tmux.conf`.

- Prefix: `Ctrl-Space`
- Reload config: `prefix` then `R`
- Toggle zoom (maximize pane): `prefix` then `f`
- Kill pane: `prefix` then `x`
- Kill window: `prefix` then `&`

There is also a popup bound to `prefix` then `r` that runs `,tmux-run-all`.

Custom commands live under `home/exact_bin/`.

If you are new to tmux, learn these first:

- create window/pane
- switch between panes
- copy-mode basics

Then adopt the repo-specific stuff (prefix, plugins, extra keybinds).

## tmux plugin manager (TPM)

TPM is pulled via externals:

- `home/.chezmoiexternal.toml`

The tmux config loads it from:

- `~/.config/tmux/plugins/tpm/tpm`

## Lowfi (Music In tmux)

This setup includes a small integration that runs `lowfi` inside a dedicated
tmux session.

- Command: `home/exact_bin/executable_,tmux-lowfi` (installs as `,tmux-lowfi`)

Tracklist data is pulled via externals into:

- `~/Library/Application Support/lowfi`

See `home/.chezmoiexternal.toml`.

## Verification And Troubleshooting

Basic checks:

```bash
tmux -V
tmux list-sessions
command -v ,w
command -v ,tmux-run-all
command -v ,tmux-lowfi
```

If tmux config changes are not reflected:

```bash
tmux source-file ~/.config/tmux/tmux.conf
```

If plugin behavior is missing:

- confirm TPM exists under `~/.config/tmux/plugins/tpm`.
- open tmux and install/update plugins via TPM.

## Related

- Lowfi in tmux: [`docs/recipes/lowfi-in-tmux.md`](../recipes/lowfi-in-tmux.md)
- Worktree workflow: [`docs/recipes/worktree-workflow.md`](../recipes/worktree-workflow.md)
