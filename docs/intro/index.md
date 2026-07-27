---
slug: /
title: kapral18/dotfiles
hide_table_of_contents: true
---

# kapral18/dotfiles

These docs are for people who want to read, learn from, or adopt pieces of this setup — IDE-first folks moving toward terminals, anyone after a repeatable macOS dev environment, or anyone using this repo as inspiration for their own.

The real workflow is a tmux workbench: Neovim stays inline, assistants run in neighboring panes, and popups appear only when a workflow asks for them.

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

These docs put the story first and the reference one click away:

- **Introduction** — what this is, how to install it safely, and what the workflow feels like.
- **Reference** — lookup tables, FAQ, and troubleshooting.

When you change something under `home/`, reflect it in the matching topic page so the next reader (human or AI agent) finds it. The agent SOPs in `~/AGENTS.md` and `~/CLAUDE.md` enforce that rule at edit time.
