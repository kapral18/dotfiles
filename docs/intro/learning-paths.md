---
sidebar_position: 5
---

# Learning Paths

An unrestricted `chezmoi apply` applies the configured files and install hooks. You can keep using your IDE while learning the installed terminal tools one at a time.

If you use VSCode or JetBrains, start with Git and Fish in the integrated terminal, then try tmux and Neovim.

## 1. Git and identity

Keep using your current IDE and terminal.

What you get immediately:

- SSH commit signing
- 1Password-backed SSH agent setup
- Opinionated git defaults (rerere, autosquash, delta, etc.)

Where to read:

- [Git and identity](../topics/workflow/git-identity/index.md)

## 2. Fish

Start using Fish as your default shell inside your IDE's integrated terminal.

What to focus on:

- Fish shell + fzf ergonomics (Ctrl+R for history, etc.)
- Getting used to the prompt and aliases

Where to read:

- [Shell: Fish](../topics/workflow/shell-fish.md)

## 3. Tmux and CLI tools

Move out of the IDE's integrated terminal and into a dedicated terminal app (like Ghostty, Alacritty, or iTerm) running `tmux`.

What to focus on:

- tmux sessions + keybindings
- Isolate work with git worktrees (`,w` commands)
- custom CLI tools under `~/bin`

Where to read:

- [Terminals](../topics/workflow/terminals.md)
- [Tmux](../topics/workflow/tmux/index.md)
- [Custom commands](../topics/workflow/custom-commands/index.md)

## 4. Neovim (optional)

Try Neovim in a tmux pane when you want to explore its editing workflow.

What to focus on:

- Neovim configuration managed like code
- Curated plugins + custom local plugins

Where to read:

- [Editor: Neovim](../topics/editor/neovim/index.md)

## 5. CLI assistants

Run assistants alongside your editor and use the shared instructions, skills, and handoff notes to manage their work.

What to focus on:

- Start a terminal assistant, such as Pi or OpenCode.
- Read the shared operating rules and each repository's instructions.
- Configure MCP tools for the context the task needs.

Where to read:

- [AI assistants](../topics/ai-assistants/index.md) — instructions, skills, subagents
- [MCP servers](../topics/ai-assistants/mcp.md) and [Tool configs](../topics/ai-assistants/tool-configs/index.md) — how tools get context and models
- [Memory and handoffs](../topics/ai-assistants/memory-and-handoffs.md) — `,ai-kb` and `,handoff`
