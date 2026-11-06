---
sidebar_position: 7
---

# herdr: popups and tools

Popups are `[[keys.command]]` entries with `type = "popup"` in [`config.toml`](../../../../home/dot_config/herdr/readonly_config.toml). herdr runs the command in a session-modal terminal, passes `HERDR_ACTIVE_PANE_ID` / `HERDR_ACTIVE_WORKSPACE_ID` for the pane underneath, and closes the popup when the command exits.

## Command palette

- Binding: `prefix` then `r`
- Purpose: one fuzzy launcher for custom tooling.

Sources (with recency boost):

1. **`~/bin/,*` commands** — descriptions come from `# Description:` header comments when present.
2. **herdr custom commands** — every `[[keys.command]]` in `config.toml`, labelled with its key and `description`.
3. **Git aliases** — global `git config` aliases shown as `git <alias>`.
4. **Drop-in extras** — `.tsv` files in `~/.config/herdr/palette.d/` (three tab-separated columns: display, key, exec).

Execution:

- `,*` commands and git aliases are typed into the pane under the popup with a trailing space; press Enter to run them.
- herdr popup and shell commands run inside the palette's popup; plugin actions run through `herdr plugin action invoke`.

Recency is stored in `~/.cache/herdr-pickers/palette_history.tsv`.

## GitHub picker popup

- Binding: `prefix` then `G`; `alt-g` switches to the session picker in the same popup.

See [GitHub picker](github-picker.md).

## Repo bootstrap popup (`owner/repo` -> `,gh-tfork`)

- Binding: `prefix` then `B`
- Prompts for `owner/repo`, runs `,gh-tfork` (clone under `~/code`), and focuses the new workspace: two tabs, each with two panes side by side.

## Pane tools

- `prefix` + `t`: pick a pane from another workspace with fzf and move it to the right of the current pane (`herdr pane move`).
- `prefix` + `C-t`: the same picker, but the pane lands below the current pane.
- `prefix` + `@`: move the current pane into a new workspace.
- `prefix` + `s`, then one key: `h/j/k/l` swaps the current pane with its on-screen neighbor (`herdr pane swap`); `H/L` moves the tab left/right, wrapping at the ends (`tab.move` over the socket API). The tmux `s` table swapped by pane order instead.
- `prefix` + `!`: move every pane of the current tab into a new workspace, named after the tab when it has a name (needs another tab to stay behind). herdr cannot move a whole tab, so the panes land side by side.
- `,herdr-run-all [--all] <pattern> [exclude] <command>`: run a command in the first idle pane (or every idle pane) of each workspace whose label matches.

## Plugins

`chezmoi apply` links two local plugins (`herdr plugin link`):

- `k18.workspace-history` records `workspace.focused` and powers `prefix` + `S` (last workspace).
- `k18.pickers` records frecency on focus, refreshes the picker cache on `workspace.created` / `workspace.renamed`, keeps the workspace path registry current (relabels on `workspace.renamed`, drops closed workspaces on `workspace.closed` and at startup), and reports the sidebar badge tokens (`$dirty`, `$pr`, `$review`, `$ci`) on startup and focus.

## Agent integrations

`chezmoi apply` also runs `herdr integration install` for pi, OMP, Claude Code, Codex, and OpenCode, so each agent reports its state (working, blocked, idle) to the herdr sidebar. It runs only when the herdr version changes or `07-merge-claude-code-settings` reinstalls `~/.claude/settings.json`, which drops herdr's hook entry; an apply that changes neither leaves herdr's files untouched.

## Lowfi

See [Lowfi](lowfi.md).

## Verification and troubleshooting

```bash
herdr --version
herdr config check
herdr plugin list
herdr workspace list
```

After editing `config.toml`, press `prefix` + `R` (or run `herdr server reload-config`).

## Related

- [Worktree workflow](../git-identity/worktrees.md)
