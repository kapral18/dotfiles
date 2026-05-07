---
slug: /
title: kapral18/dotfiles
hide_table_of_contents: true
---

# kapral18/dotfiles

Personal macOS development environment built around an **Agentic Operating System**: classical dotfiles (Fish, Neovim, Tmux) on the bottom, deterministic AI agent governance (MCP servers, SOPs, skills) on top. Everything is declarative and applied with [chezmoi](https://www.chezmoi.io/).

These docs are for people who want to read, learn from, or adopt pieces of this setup — IDE-first folks moving toward terminals, anyone after a repeatable macOS dev environment, or anyone using this repo as inspiration for their own.

## Where to start

- **[Getting Started](./getting-started.md)** — preview and apply changes safely without breaking your machine.
- **[Architecture](./architecture.md)** — how the repo is structured and how data flows through `chezmoi`, hooks, externals, and the AI layer.
- **[New machine bootstrap](./new-machine-bootstrap.md)** — what to expect the first time you run this end-to-end.
- **[A Day in the Life](./day-in-the-life.md)** — what a typical workflow with these tools looks like.
- **[Learning Paths](./learning-paths.md)** — incremental on-ramps for each subsystem after install.

## How these docs are organised

- **Introduction** — what this is and how to install it safely.
- **Topics** — concept + how-to for each domain (chezmoi, packages, git, fish, terminals, tmux, formatting, neovim, macOS automation, security & AI). Recipes (e.g. _add a Homebrew package_) live next to the topic they belong to, not in a separate tree.
- **Reference** — cheat sheets, FAQ, troubleshooting.

When you change something under `home/`, reflect it in the matching topic page so the next reader (human or AI agent) finds it. The agent SOPs in `~/AGENTS.md` and `~/CLAUDE.md` enforce that rule at edit time.
