---
slug: /
title: kapral18/dotfiles
hide_table_of_contents: true
---

# kapral18/dotfiles

Personal macOS development environment built around an **Agentic Operating System**: Fish, Neovim, and Tmux for the human loop; deterministic AI agent governance, MCP servers, skills, and Ralph on top. Everything is declarative and applied with [chezmoi](https://www.chezmoi.io/).

These docs are for people who want to read, learn from, or adopt pieces of this setup — IDE-first folks moving toward terminals, anyone after a repeatable macOS dev environment, or anyone using this repo as inspiration for their own.

The real workflow is a tmux workbench: Neovim stays inline, assistants run in neighboring panes, and popups appear only when a workflow asks for them.

![Full terminal layout with Neovim in the left pane and an assistant workflow pane on the right](../topics/editor/assets/natural-neovim-layout.png)

## Where to start

| If you want to...                         | Start here                                          |
| ----------------------------------------- | --------------------------------------------------- |
| Install or preview safely                 | [Getting Started](./getting-started.md)             |
| Understand source → rendered `$HOME` flow | [Architecture](./architecture.md)                   |
| See the day-to-day terminal workflow      | [A Day in the Life](./day-in-the-life.md)           |
| Learn the system gradually                | [Learning Paths](./learning-paths.md)               |
| Bootstrap a fresh Mac                     | [New machine bootstrap](./new-machine-bootstrap.md) |

## Visual map

| Surface                                                     | What it shows                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------- |
| [Tmux](../topics/workflow/tmux/index.md)                    | Session layout, command palette, URL/session/GitHub popups    |
| [Session picker](../topics/workflow/tmux/session-picker.md) | Sessions, worktrees, directories, dirty/PR/review/CI badges   |
| [GitHub picker](../topics/workflow/tmux/github-picker.md)   | PRs, issues, epics, backports, review/CI state, Ralph handoff |
| [Neovim](../topics/editor/neovim/index.md)                  | Inline editor workflow and `vim.pack` dashboard               |
| [Ralph](../topics/ai-assistants/ralph/index.md)             | Multi-run planner/executor/reviewer control plane             |

## How these docs are organised

These docs put the story first and the reference one click away:

- **Introduction** — what this is, how to install it safely, and what the workflow feels like.
- **Domain sections** — the sidebar exposes the real systems directly: Chezmoi and packages first, then the **Agentic OS** (SOP governance, skills, spec/build/Ralph flows, reviews, subagents, memory — start at [Choose your flow](../topics/ai-assistants/scenarios.md)), then the human loop it drives: Git & identity, Fish shell, Terminals, Tmux, Custom commands, Neovim, macOS, Security, and Code quality.
- **Reference** — lookup tables, FAQ, and troubleshooting.

When you change something under `home/`, reflect it in the matching topic page so the next reader (human or AI agent) finds it. The agent SOPs in `~/AGENTS.md` and `~/CLAUDE.md` enforce that rule at edit time.
