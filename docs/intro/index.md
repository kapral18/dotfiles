---
slug: /
title: kapral18/dotfiles
hide_table_of_contents: true
---

# kapral18/dotfiles

These docs cover a macOS development environment built around Fish, tmux, Neovim, and CLI assistants. Use them to install the setup, learn its workflow, or adapt individual pieces.

Neovim and assistants run in neighboring tmux panes. Popups hold pickers and other temporary tools.

## Where to start

| If you want to...                         | Start here                                          |
| ----------------------------------------- | --------------------------------------------------- |
| Install or preview safely                 | [Getting Started](./getting-started.md)             |
| Understand source → rendered `$HOME` flow | [Architecture](./architecture.md)                   |
| See the day-to-day terminal workflow      | [A Day in the Life](./day-in-the-life.md)           |
| Learn the system gradually                | [Learning Paths](./learning-paths.md)               |
| Bootstrap a fresh Mac                     | [New machine bootstrap](./new-machine-bootstrap.md) |

## Visual map

| Surface                                                     | What it shows                                               |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| [Tmux](../topics/workflow/tmux/index.md)                    | Session layout, command palette, URL/session/GitHub popups  |
| [Session picker](../topics/workflow/tmux/session-picker.md) | Sessions, worktrees, directories, dirty/PR/review/CI badges |
| [Neovim](../topics/editor/neovim/index.md)                  | Inline editor workflow and `vim.pack` dashboard             |

## How these docs are organised

- **Introduction** — what this is, how to install it safely, and what the workflow feels like.
- **Topics** — configuration and commands by subsystem.
- **Reference** — lookup tables, FAQ, and troubleshooting.

When a change under `home/` affects behavior, update the matching topic page. The repository's [`AGENTS.md`](../../AGENTS.md) requires this for agent edits.
